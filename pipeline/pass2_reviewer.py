"""
Pass 2 — LLM quality audit.
Receives both the original and Pass 1 output; returns a structured issue
report for the interactive approval loop.
"""

import json
from openai import OpenAI
from config import settings
from prompts import generic_pass2, jd_pass2

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=settings.github_access_token,
)

_REQUIRED_KEYS = {"overall_quality_score", "summary", "issues"}


def run_pass2(
    original: dict,
    optimized: dict,
    mode: str,
    jd_context: dict | None = None,
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
    """
    if mode == "jd":
        system_prompt = jd_pass2.SYSTEM
        user_prompt   = jd_pass2.build(original, optimized, jd_context)
    else:
        system_prompt = generic_pass2.SYSTEM
        user_prompt   = generic_pass2.build(original, optimized)

    response = client.chat.completions.create(
        model=settings.model,
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )

    report = json.loads(response.choices[0].message.content)

    for key in _REQUIRED_KEYS:
        report.setdefault(
            key,
            [] if key == "issues" else 0 if key == "overall_quality_score" else ""
        )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    report["issues"].sort(
        key=lambda i: severity_order.get(i.get("severity", "low"), 2)
    )

    return report