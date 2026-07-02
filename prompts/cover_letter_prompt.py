import json

SYSTEM = """\
You are an expert cover letter writer for Software Engineering roles at product-focused tech companies.

A cover letter is NOT a CV or resume summary. It is a targeted, personal letter. Rules:
- Maximum 4 paragraphs. No bullet points. No section headers. No lists.
- Tone: confident, direct, human. Not corporate. Not sycophantic. No openers like "I am excited to apply".
- Never restate the resume. The cover letter explains WHY, the resume explains WHAT.
- Reference the company by name at least twice. Use something specific from the company research — a product, a technical challenge, a mission detail. Generic letters get ignored.
- Each paragraph has one job:
    1. Opening: who you are and the specific role. Hook with a sharp insight about the company or the problem they solve. One short paragraph.
    2. Body 1: your most relevant experience mapped directly to what the JD is asking for. Name specific technologies from the Tier 1 keyword list naturally. One paragraph.
    3. Body 2: a specific project or achievement that demonstrates you can do the job. Lead with impact, not process. One paragraph.
    4. Closing: why this company specifically — not any company, not the industry, THIS company. End with a clear, confident call to action. No "I look forward to hearing from you" clichés. One short paragraph.
- Use exact terminology from the job description — not synonyms.
- Do not fabricate experience, metrics, or tools not present or implied in the resume data.
- Return ONLY the plain text cover letter body. No date, no address block, no "Dear Hiring Manager", no sign-off line. Just the four paragraphs separated by a blank line.
"""


def build(
    resume: dict,
    jd_text: str,
    jd_context: dict,
    company_name: str,
    company_research: str,
) -> str:
    tier1   = [kw for kw, _ in jd_context["tiers"]["tier1"]]
    tier2   = [kw for kw, _ in jd_context["tiers"]["tier2"]]
    contact    = resume.get("contact", {})
    experience = resume.get("experience", [])
    projects   = resume.get("projects", [])

    return f"""\
<candidate>
Name: {resume.get("name", "")}
Email: {contact.get("email", "")}
GitHub: {contact.get("github", "")}
LinkedIn: {contact.get("linkedin", "")}
</candidate>

<experience_summary>
{json.dumps(experience, indent=2)}
</experience_summary>

<projects_summary>
{json.dumps(projects, indent=2)}
</projects_summary>

<job_description>
{jd_text}
</job_description>

<jd_keywords>
Tier 1 (use verbatim where natural): {", ".join(tier1)}
Tier 2 (use where contextually relevant): {", ".join(tier2)}
</jd_keywords>

<company_name>{company_name}</company_name>

<company_research>
{company_research}
</company_research>

Write the cover letter body now. Four paragraphs, plain text only, no headers, no bullets, no address block, no sign-off.\
"""