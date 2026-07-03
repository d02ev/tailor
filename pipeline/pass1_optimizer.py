"""
Pass 1 — LLM-powered resume optimisation.

Rewrites the entire resume in a SINGLE LLM call (rather than one call per section).
On the free tier this is the biggest quota saving: a JD run drops from ~6-8 calls to
~3-4. Each returned section is shape-validated before it replaces the original, so a
malformed or missing key falls back to the untouched section instead of corrupting it.
"""

import copy

from pipeline import llm_client
from pipeline.utils import REWRITEABLE_SECTIONS
from prompts import generic_pass1, jd_pass1


def _shape_ok(section_key: str, original, candidate) -> bool:
    """Guard against the model returning null / wrong-typed sections."""
    if candidate is None:
        return False
    if section_key == "professionalSummary":
        return isinstance(candidate, str) and candidate.strip() != ""
    # For structured sections the type must match the original (list ↔ list, dict ↔ dict).
    if original is not None and type(candidate) is not type(original):
        return False
    if section_key in ("experience", "projects"):
        return isinstance(candidate, list) and len(candidate) == len(original or [])
    if section_key == "techStack":
        return isinstance(candidate, dict)
    return True


def run_pass1(
    resume: dict,
    mode: str,
    jd_context: dict | None = None,
) -> dict:
    """
    Returns a mutated copy of the resume with all rewriteable sections
    (plus a generated professionalSummary) optimised in one LLM call.

    Args:
        resume:     Original resume dict from the source API.
        mode:       "generic" or "jd".
        jd_context: Output of jd_parser.parse_jd() — required when mode="jd".
    """
    optimized = copy.deepcopy(resume)

    if mode == "jd":
        system_prompt = jd_pass1.SYSTEM
        user_prompt   = jd_pass1.build(resume, jd_context)
    else:
        system_prompt = generic_pass1.SYSTEM
        user_prompt   = generic_pass1.build(resume)

    result = llm_client.chat_json(
        system_prompt,
        user_prompt,
        temperature=0.1,
        max_tokens=4096,   # whole-resume rewrite needs more headroom than one section
        seed=42,
    )

    # professionalSummary is generated even when absent from the source resume.
    for section_key in [*REWRITEABLE_SECTIONS, "professionalSummary"]:
        candidate = result.get(section_key)
        if _shape_ok(section_key, resume.get(section_key), candidate):
            optimized[section_key] = candidate

    return optimized
