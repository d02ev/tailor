"""
Pass 2 — LLM quality audit.
Receives both the original and Pass 1 output; returns a structured issue
report for the interactive approval loop.
"""

from pipeline import llm_client
from prompts import generic_pass2, jd_pass2

_REQUIRED_KEYS = {"overall_quality_score", "summary", "issues"}


def run_pass2(
    original: dict,
    optimized: dict,
    mode: str,
    jd_context: dict | None = None,
    ats_scores: dict | None = None,   # Pass 1 ATS score result — used to calibrate quality score
) -> dict:
    """
    Returns a quality report dict:
    {
        "overall_quality_score": 88,
        "summary": "...",
        "issues": [ { ...issue... }, ... ]
    }

    JD mode additionally includes:
    {
        "ats_keyword_coverage": { "tier1_total": N, "tier1_present": N, ... }
    }

    Args:
        original:   Original resume dict before any optimisation.
        optimized:  Resume dict after Pass 1.
        mode:       "generic" or "jd".
        jd_context: Parsed JD context — required when mode="jd".
        ats_scores: Output of scorer.ats_score() on the Pass 1 result.
                    Passed into the JD Pass 2 prompt so the quality score
                    reflects actual keyword hit rate, not a fixed rubric value.
    """
    if mode == "jd":
        system_prompt = jd_pass2.SYSTEM
        user_prompt   = jd_pass2.build(original, optimized, jd_context, ats_scores)
    else:
        system_prompt = generic_pass2.SYSTEM
        user_prompt   = generic_pass2.build(original, optimized)

    report = llm_client.chat_json(
        system_prompt,
        user_prompt,
        temperature=0,          # Fully deterministic — audit must be a consistent judge
        max_tokens=2048,
    )

    # Defensive defaults so downstream code never KeyErrors
    for key in _REQUIRED_KEYS:
        report.setdefault(
            key,
            [] if key == "issues" else 0 if key == "overall_quality_score" else ""
        )

    # Deduplicate issues by (section, item_index, bullet_index, issue_type)
    # Guards against the LLM splitting one problem into two entries across runs
    seen    = set()
    deduped = []
    for issue in report["issues"]:
        key = (
            issue.get("section"),
            str(issue.get("item_index")),
            str(issue.get("bullet_index")),
            issue.get("issue_type"),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(issue)

    # Sort: high → medium → low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(key=lambda i: severity_order.get(i.get("severity", "low"), 2))
    report["issues"] = deduped

    return report