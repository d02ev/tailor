import json

from prompts.resume_standards import STANDARDS, SUMMARY_RULES

SYSTEM = f"""\
You are a Principal-level Technical Recruiter and resume writer rewriting a Software Engineer resume to align with a specific job description. You rewrite the entire resume in a single pass.

SCHEMA RULES — your output must match the input schema exactly:
- experience items: rewrite bullets inside the "description" array. Do not rename or add keys.
- projects items: rewrite "longDescription" (string) and "shortDescription" (string). Do not rename or add keys.
- techStack: you may add specific technologies to the existing sub-lists where they truthfully apply. Do not rename sub-keys or add new ones.
- professionalSummary: (re)write a single string, even if none was supplied.
- Preserve all "id", "jobTitle", "companyName", "location", "startDate", "endDate", "year",
  "repoUrl", "liveUrl", "displayName" fields exactly as-is.

REWRITING PHILOSOPHY:
The goal is not to insert keywords. The goal is to tell the story of someone who can do this job — someone who has solved the same category of problems the JD describes. Keywords emerge naturally from honest, specific storytelling. A recruiter should think "this person has done this before" — not "this resume was written to match our JD."

KEYWORD HANDLING — three types, three rules:
  HARD SKILLS (tools, languages, platforms): mention in techStack where truthfully applicable;
    reference in experience/projects only where genuinely used; do not repeat one hard skill in more than two bullets.
  DOMAIN CONCEPTS (patterns, practices — distributed systems, observability, CI/CD): never name-drop.
    Demonstrate with concrete work, scope, and impact. Max one domain concept per bullet.
  SOFT/PROCESS TERMS (agile, cross-functional, stakeholder): at most once per section, only where natural. Omit if forced.
Expand acronyms to their full JD form on first use only (e.g. "ML" → "machine learning (ML)").

{STANDARDS}

{SUMMARY_RULES}
"""


def build(resume: dict, jd_context: dict) -> str:
    classified   = jd_context.get("classified", {})
    hard_skills  = [kw for kw, _ in classified.get("hard_skill", [])]
    domain       = [kw for kw, _ in classified.get("domain_concept", [])]
    soft_process = [kw for kw, _ in classified.get("soft_process", [])]
    partial      = jd_context.get("gaps", {}).get("partial", [])

    payload = {
        "professionalSummary": resume.get("professionalSummary", ""),
        "experience": resume.get("experience"),
        "projects": resume.get("projects"),
        "techStack": resume.get("techStack"),
    }
    payload = {
        k: v for k, v in payload.items()
        if v is not None or k == "professionalSummary"
    }

    return f"""\
<resume_sections>
{json.dumps(payload, indent=2)}
</resume_sections>

<hard_skills>
Reference only where genuinely used: {", ".join(hard_skills) if hard_skills else "none"}
</hard_skills>

<domain_concepts>
Demonstrate through specific work — do not name-drop: {", ".join(domain) if domain else "none"}
</domain_concepts>

<soft_process_terms>
Use at most once per section if naturally fitting: {", ".join(soft_process) if soft_process else "none"}
</soft_process_terms>

<partial_matches_to_expand>
Expand acronyms to full JD form on first use only: {", ".join(partial) if partial else "none"}
</partial_matches_to_expand>

Rewrite every section. Tell the story of someone who can do this job — let keywords emerge from honest, specific work descriptions.
Return a single JSON object with exactly these keys: {", ".join(payload.keys())}.
Each key must match the original schema of that section.\
"""
