"""
Shared utility functions used across the pipeline.
"""
REWRITEABLE_SECTIONS = ["experience", "projects", "techStack"]

ISSUE_TYPE_LABELS = {
    "weak_verb":          "Weak Action Verb",
    "missing_impact":     "Missing Impact / Metrics",
    "vague_tech":         "Vague Technology Reference",
    "unnatural_phrasing": "Unnatural Phrasing",
    "tense_error":        "Tense Inconsistency",
    "factual_inflation":  "Factual Inflation",
    "grammar":            "Grammar / Spelling",
    "skills_entry":       "Soft Skill in Skills Section",
    "keyword_missing":    "Tier 1 Keyword Missing",
    "keyword_partial":    "Tier 1 Keyword Partial Match",
    "keyword_stuffing":   "Keyword Stuffing",
    "terminology_drift":  "Terminology Drift (JD Mismatch)",
    "regression":         "Pass 1 Regression",
    "ats_formatting":     "ATS-Unsafe Formatting",
}


def extract_all_text(resume: dict) -> str:
    """
    Recursively flatten all string values from the resume dict into a
    single lowercased string for keyword matching and TF-IDF scoring.
    """
    parts = []

    def _walk(node):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                _walk(value)

    _walk(resume)
    return " ".join(parts).lower()


def apply_fix_to_resume(resume: dict, issue: dict) -> None:
    """
    Mutates the resume dict in-place applying the suggested fix from a Pass 2 issue.

    Routing logic per section:
      experience[i].description[j]  — list of bullet strings
      projects[i].longDescription    — plain string  (bullet_index = null)
      projects[i].shortDescription   — plain string  (bullet_index = null)
      techStack.<sub_key>[j]         — list of strings (item_index = sub-key name)
    """
    section_key  = issue.get("section")
    section      = resume.get(section_key)
    if section is None:
        return

    item_index   = issue.get("item_index")
    bullet_index = issue.get("bullet_index")
    fix          = issue.get("suggested_fix", "")

    if section_key == "techStack":
        if item_index is not None and bullet_index is not None:
            sub_list = section.get(str(item_index))
            if isinstance(sub_list, list):
                sub_list[bullet_index] = fix
        return

    if not isinstance(section, list) or item_index is None:
        return

    item = section[item_index]

    if section_key == "experience":
        bullets = item.get("description")
        if isinstance(bullets, list) and bullet_index is not None:
            bullets[bullet_index] = fix

    elif section_key == "projects":
        field = issue.get("field", "longDescription")
        if field in ("longDescription", "shortDescription") and field in item:
            item[field] = fix