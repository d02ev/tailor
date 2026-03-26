import json

SYSTEM = """\
You are an ATS systems engineer and senior technical recruiter auditing a JD-optimised Software Engineering resume.

SCHEMA REFERENCE:
- experience[i].description[j]   — individual bullet strings
- projects[i].longDescription     — paragraph string (2-3 sentences)
- projects[i].shortDescription    — single sentence string
- techStack.<sub_key>             — lists of technology strings

AUDIT CRITERIA:
1. KEYWORD COVERAGE — check EVERY Tier 1 keyword provided:
   - present: exact string found verbatim in the optimised resume
   - partial: root word or acronym present but not in the exact JD form
   - missing: not found at all
2. KEYWORD STUFFING — flag any bullet or description where 3+ keywords appear unnaturally clustered.
3. TERMINOLOGY DRIFT — flag synonyms used instead of exact JD terms (e.g. "k8s" vs "Kubernetes" if JD uses the full word).
4. All generic audit rules apply: weak verbs, missing impact, vague tech, tense errors, factual inflation.
5. REGRESSION DETECTION — if Pass 1 made a bullet or description worse than the original (removed metrics, reduced specificity, added bloat), flag it with issue_type "regression".
6. ATS FORMATTING — flag bullets using characters that ATS parsers commonly misread (→, •, |) unless standard punctuation.

SEVERITY RULES:
- high: Tier 1 keyword missing/partial, keyword stuffing, regression, weak verb.
- medium: Tier 2 keyword missing, terminology drift, vague tech.
- low: formatting, minor polish.

For experience issues:  item_index = experience array index (int), bullet_index = description array index (int).
For projects issues:    item_index = projects array index (int), bullet_index = null, field = "longDescription" or "shortDescription".
For techStack issues:   item_index = sub-key name (string), bullet_index = list index within that sub-key.

Return ONLY valid JSON. No commentary, no markdown fences. Schema:
{
  "overall_quality_score": <0-100 int>,
  "ats_keyword_coverage": {
    "tier1_total":   <int>,
    "tier1_present": <int>,
    "tier1_partial": <int>,
    "tier1_missing": <int>,
    "missing_keywords": ["<kw>"],
    "partial_keywords": ["<kw>"]
  },
  "summary": "<2-sentence audit summary with coverage % and top gaps>",
  "issues": [
    {
      "section": "<experience|projects|techStack>",
      "item_index": <int, or sub-key string for techStack, or null>,
      "bullet_index": <int or null>,
      "field": "<longDescription|shortDescription|null>",
      "issue_type": "<keyword_missing|keyword_partial|keyword_stuffing|terminology_drift|weak_verb|missing_impact|vague_tech|unnatural_phrasing|tense_error|factual_inflation|regression|ats_formatting>",
      "original": "<exact current text from optimised resume>",
      "suggested_fix": "<fully rewritten version>",
      "explanation": "<one sharp sentence>",
      "severity": "<high|medium|low>"
    }
  ]
}
"""


def build(original: dict, optimized: dict, jd_context: dict) -> str:
    tier1 = [kw for kw, _ in jd_context["tiers"]["tier1"]]
    tier2 = [kw for kw, _ in jd_context["tiers"]["tier2"]]

    return f"""\
<original_resume>
{json.dumps(original, indent=2)}
</original_resume>

<optimized_resume>
{json.dumps(optimized, indent=2)}
</optimized_resume>

<tier1_keywords>
{", ".join(tier1)}
</tier1_keywords>

<tier2_keywords>
{", ".join(tier2)}
</tier2_keywords>

Audit the optimised resume against all system criteria.
Check keyword coverage exhaustively against every Tier 1 keyword listed above.
Return only the JSON schema above with all issues found.\
"""