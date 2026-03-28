"""
Project Matcher — JD mode only.

Fetches all projects from the API, uses the LLM to rank them by relevance
to the job description, then injects the top 2 into the resume only if
they differ from the projects already present.
"""

import json
from openai import OpenAI
from config import settings

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=settings.github_access_token,
)

_SYSTEM = """\
You are a technical recruiter selecting the most relevant projects for a Software Engineer resume.

Given a list of projects and a job description context, pick exactly 2 projects that:
1. Best demonstrate skills and technologies explicitly mentioned in the job description.
2. Show measurable impact or technical depth most aligned with the role.
3. Are the most distinct from each other — avoid two projects with identical tech stacks.

Return ONLY valid JSON. No commentary, no markdown fences.
Schema:
{
  "selected_ids": ["<project_id_1>", "<project_id_2>"],
  "reasoning": {
    "<project_id_1>": "<one sentence: why this project matches the JD>",
    "<project_id_2>": "<one sentence: why this project matches the JD>"
  }
}
"""


def _rank_projects(
    all_projects: list[dict],
    jd_context: dict,
    company_name: str,
) -> tuple[list[str], dict[str, str]]:
    """
    Calls the LLM to select the 2 best-matched project IDs.
    Returns (selected_ids, reasoning_map).
    """
    tier1 = [kw for kw, _ in jd_context["tiers"]["tier1"]]
    tier2 = [kw for kw, _ in jd_context["tiers"]["tier2"]]

    slim_projects = [
        {
            "id":               p.get("id"),
            "displayName":      p.get("displayName"),
            "shortDescription": p.get("shortDescription"),
            "longDescription":  p.get("longDescription"),
            "techStack":        p.get("techStack", []),
            "year":             p.get("year"),
        }
        for p in all_projects
    ]

    user_prompt = f"""\
<company>{company_name}</company>

<jd_keywords>
Tier 1 (must-have): {", ".join(tier1)}
Tier 2 (nice-to-have): {", ".join(tier2)}
</jd_keywords>

<all_projects>
{json.dumps(slim_projects, indent=2)}
</all_projects>

Select the 2 projects that best match the job description and company context above.
Return only the JSON schema specified in the system prompt.\
"""

    response = client.chat.completions.create(
        model=settings.model,
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=512,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
    )

    result = json.loads(response.choices[0].message.content)
    return result.get("selected_ids", []), result.get("reasoning", {})


def _ids_differ(existing: list[dict], selected: list[dict]) -> bool:
    """Returns True if the selected project set differs from the existing one."""
    existing_ids = {p.get("id") for p in existing}
    selected_ids = {p.get("id") for p in selected}
    return existing_ids != selected_ids


def match_and_inject(
    resume: dict,
    all_projects: list[dict],
    jd_context: dict,
    company_name: str,
) -> tuple[dict, dict[str, str]]:
    """
    Main entry point.

    1. Asks the LLM to pick the 2 best-matching projects.
    2. Compares selected projects against the resume's current project list.
    3. Replaces resume["projects"] only if the selection differs.

    Returns:
        (updated_resume, reasoning_map)
        reasoning_map is empty {} if no replacement was made.
    """
    import copy
    resume = copy.deepcopy(resume)

    selected_ids, reasoning = _rank_projects(all_projects, jd_context, company_name)

    project_by_id: dict[str, dict] = {
        p["id"]: p for p in all_projects if "id" in p
    }

    selected_projects = [
        project_by_id[pid]
        for pid in selected_ids
        if pid in project_by_id
    ]

    if len(selected_projects) < 2:
        return resume, {}

    existing_projects = resume.get("projects", [])

    if not _ids_differ(existing_projects, selected_projects):
        return resume, {}

    resume["projects"] = selected_projects
    return resume, reasoning