"""
Pass 1 — LLM-powered resume optimisation.
Processes each rewriteable section independently to keep token usage low
and output schema predictable.
"""

import json
from openai import OpenAI
from config import settings
from pipeline.utils import REWRITEABLE_SECTIONS
from prompts import generic_pass1, jd_pass1

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=settings.github_access_token,
)


def _call_llm(system: str, user: str) -> dict:
    response = client.chat.completions.create(
        model=settings.model,
        response_format={"type": "json_object"},
        temperature=0.1,
        seed=42,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return json.loads(response.choices[0].message.content)


def run_pass1(
    resume: dict,
    mode: str,
    jd_context: dict | None = None,
) -> dict:
    """
    Returns a mutated copy of the resume with all rewriteable sections
    optimised by the LLM.

    Args:
        resume:     Original resume dict from the source API.
        mode:       "generic" or "jd".
        jd_context: Output of jd_parser.parse_jd() — required when mode="jd".
    """
    import copy
    optimized = copy.deepcopy(resume)

    system_prompt = jd_pass1.SYSTEM if mode == "jd" else generic_pass1.SYSTEM

    for section_key in REWRITEABLE_SECTIONS:
        if section_key not in resume:
            continue

        if mode == "jd":
            user_prompt = jd_pass1.build(
                section_key=section_key,
                section_data=resume[section_key],
                jd_context=jd_context,
            )
        else:
            user_prompt = generic_pass1.build(
                section_key=section_key,
                section_data=resume[section_key],
            )

        result = _call_llm(system_prompt, user_prompt)

        if section_key in result:
            optimized[section_key] = result[section_key]

    return optimized