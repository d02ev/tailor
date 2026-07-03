import json

from prompts.resume_standards import STANDARDS, SUMMARY_RULES

SYSTEM = f"""\
You are a professional resume writer specialising in Software Engineering resumes at the FAANG and top-tier startup level.

You rewrite an entire resume in a single pass. Your output must match the input schema exactly:
- experience items: rewrite bullets inside the "description" array. Do not rename or add keys.
- projects items: rewrite "longDescription" (string) and "shortDescription" (string). Do not rename or add keys.
- techStack: you may reorder or add specific technologies to the existing sub-lists
  (languages, frameworksAndPlatforms, databases, cloudAndDevOps, others). Do not rename sub-keys or add new ones.
- professionalSummary: (re)write a single string, even if none was supplied.
- Preserve all "id", "jobTitle", "companyName", "location", "startDate", "endDate", "year",
  "repoUrl", "liveUrl", "displayName" fields exactly as-is.

{STANDARDS}

{SUMMARY_RULES}
"""


def build(resume: dict, jd_context=None) -> str:
    """Assemble a single user prompt covering every rewriteable section at once."""
    payload = {
        "professionalSummary": resume.get("professionalSummary", ""),
        "experience": resume.get("experience"),
        "projects": resume.get("projects"),
        "techStack": resume.get("techStack"),
    }
    # Drop absent sections (except professionalSummary, which we always generate).
    payload = {
        k: v for k, v in payload.items()
        if v is not None or k == "professionalSummary"
    }

    return f"""\
<resume_sections>
{json.dumps(payload, indent=2)}
</resume_sections>

Rewrite every section above following all standards.
Return a single JSON object with exactly these keys: {", ".join(payload.keys())}.
Each key must match the original schema of that section.\
"""
