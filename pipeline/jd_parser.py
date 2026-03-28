"""
Parses a plain-text job description into tiered keywords and computes
a gap analysis against the current resume.
"""

import re
import spacy
from keybert import KeyBERT
from pipeline.utils import extract_all_text

TIER1_THRESHOLD = 0.68
TIER2_THRESHOLD = 0.42

_kw_model: KeyBERT | None = None
_nlp = None


def _get_models():
    global _kw_model, _nlp
    if _kw_model is None:
        _kw_model = KeyBERT()
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _kw_model, _nlp


def _clean_jd(text: str) -> str:
    """Strip boilerplate lines and normalise whitespace."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = [l for l in lines if not re.fullmatch(r"[-=_*#]{3,}", l)]
    return " ".join(lines)


def parse_jd(jd_text: str, resume: dict | None = None) -> dict:
    """
    Returns:
    {
        "all_keywords": [("python", 0.85), ...],
        "tiers": {
            "tier1": [("python", 0.85), ...],       # must-have  (score >= 0.68)
            "tier2": [("rest api", 0.55), ...],      # nice-to-have (0.42–0.68)
            "tier3": [("agile", 0.31), ...],         # context only (< 0.42)
        },
        "gaps": {
            "missing": ["ci/cd pipelines", ...],    # not in resume at all
            "partial": ["ml → machine learning"],   # root present, not exact phrase
            "present": ["python", ...],             # already matched
        }
    }
    """
    kw_model, _ = _get_models()
    cleaned = _clean_jd(jd_text)

    raw_keywords: list[tuple[str, float]] = kw_model.extract_keywords(
        cleaned,
        keyphrase_ngram_range=(1, 3),
        stop_words="english",
        use_mmr=True,
        diversity=0.55,
        top_n=40,
    )

    phrases = [kw for kw, _ in raw_keywords]
    deduped: list[tuple[str, float]] = []
    for kw, score in raw_keywords:
        is_subsumed = any(kw != phrase and kw in phrase for phrase in phrases)
        if not is_subsumed:
            deduped.append((kw.lower(), round(score, 4)))

    tier1 = [(kw, s) for kw, s in deduped if s >= TIER1_THRESHOLD]
    tier2 = [(kw, s) for kw, s in deduped if TIER2_THRESHOLD <= s < TIER1_THRESHOLD]
    tier3 = [(kw, s) for kw, s in deduped if s < TIER2_THRESHOLD]

    gaps: dict[str, list[str]] = {"missing": [], "partial": [], "present": []}
    if resume:
        resume_text = extract_all_text(resume)
        for kw, _ in tier1 + tier2:
            if kw in resume_text:
                gaps["present"].append(kw)
            elif any(word in resume_text for word in kw.split()):
                gaps["partial"].append(kw)
            else:
                gaps["missing"].append(kw)

    return {
        "all_keywords": deduped,
        "tiers": {"tier1": tier1, "tier2": tier2, "tier3": tier3},
        "gaps": gaps,
    }