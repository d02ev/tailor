"""
Local ATS scorer — no external APIs required.

Composite score = (keyword_hit_rate × 0.65) + (semantic_similarity × 0.35)

keyword_hit_rate is *weighted* by each keyword's KeyBERT importance score, so a
resume that covers the high-signal (Tier 1) keywords scores higher than one that
only covers low-signal ones — matching how recruiters actually screen.

Matching is token/lemma based with word boundaries (not raw substring), so "python"
no longer matches "pythonic", and common acronym/expansion pairs (ml ↔ machine
learning, k8s ↔ kubernetes) are treated as equivalent.
"""

import re

import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from pipeline.utils import extract_all_text

# Loaded lazily — only when the scorer is actually used (JD mode).
_nlp = None

# Bidirectional acronym ↔ expansion equivalence. Keys are expansions.
_ACRONYMS = {
    "machine learning": "ml",
    "artificial intelligence": "ai",
    "natural language processing": "nlp",
    "continuous integration": "ci",
    "continuous delivery": "cd",
    "continuous deployment": "cd",
    "infrastructure as code": "iac",
    "kubernetes": "k8s",
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "user interface": "ui",
    "user experience": "ux",
    "test driven development": "tdd",
    "object relational mapping": "orm",
}
_REVERSE_ACRONYMS: dict[str, set[str]] = {}
for _full, _acr in _ACRONYMS.items():
    _REVERSE_ACRONYMS.setdefault(_acr, set()).add(_full)


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _lemmas(text: str) -> list[str]:
    """Content-token lemmas (lowercased) for span matching."""
    doc = _get_nlp()(text.lower())
    return [t.lemma_.lower() for t in doc if not t.is_space and not t.is_punct]


def _surface_forms(keyword: str) -> set[str]:
    """A keyword plus its acronym/expansion equivalents."""
    kw = keyword.lower().strip()
    forms = {kw}
    if kw in _ACRONYMS:
        forms.add(_ACRONYMS[kw])
    forms |= _REVERSE_ACRONYMS.get(kw, set())
    return forms


def _span_in(needle: list[str], haystack: list[str]) -> bool:
    if not needle:
        return False
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def _keyword_hit(keyword: str, resume_text: str, resume_lemmas: list[str]) -> bool:
    """
    True if the keyword (or an acronym-equivalent form) appears in the resume as a
    whole word / contiguous phrase — never as a substring of a larger word.
    """
    for surface in _surface_forms(keyword):
        # Word-boundary match on the raw text handles exact phrases and acronyms.
        pattern = r"(?<!\w)" + re.escape(surface) + r"(?!\w)"
        if re.search(pattern, resume_text):
            return True
        # Lemma span match catches inflected forms ("designs" ↔ "design").
        if _span_in(_lemmas(surface), resume_lemmas):
            return True
    return False


def ats_score(resume: dict, keywords: list[tuple[str, float]]) -> dict:
    """
    Args:
        resume:   The resume dict (pre or post optimisation).
        keywords: List of (keyword, score) tuples from jd_parser (all tiers combined).
                  The score doubles as the keyword's weight.

    Returns:
        {
            "composite_ats_score": 84.7,
            "keyword_hit_rate":    91.2,   # importance-weighted
            "semantic_similarity": 73.1,
            "hits":   31,
            "total":  34,
            "missing_keywords": ["stakeholder management", ...]
        }
    """
    resume_text   = extract_all_text(resume)
    resume_lemmas = _lemmas(resume_text)
    jd_text       = " ".join(kw for kw, _ in keywords)

    try:
        vectorizer   = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
        semantic     = float(cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]) * 100
    except ValueError:
        semantic = 0.0

    hits, missing = [], []
    hit_weight = total_weight = 0.0
    for kw, score in keywords:
        weight = max(float(score), 0.01)   # every keyword counts at least a little
        total_weight += weight
        if _keyword_hit(kw, resume_text, resume_lemmas):
            hits.append(kw)
            hit_weight += weight
        else:
            missing.append(kw)

    hit_rate  = (hit_weight / total_weight * 100) if total_weight else 0.0
    composite = round((hit_rate * 0.65) + (semantic * 0.35), 1)

    return {
        "composite_ats_score": composite,
        "keyword_hit_rate":    round(hit_rate, 1),
        "semantic_similarity": round(semantic, 1),
        "hits":                len(hits),
        "total":               len(keywords),
        "missing_keywords":    missing,
    }


def score_delta(before: dict, after: dict) -> dict:
    """Returns a diff dict between two ats_score results."""
    return {
        "composite_delta": round(after["composite_ats_score"] - before["composite_ats_score"], 1),
        "keyword_delta":   round(after["keyword_hit_rate"]    - before["keyword_hit_rate"],    1),
        "semantic_delta":  round(after["semantic_similarity"] - before["semantic_similarity"],  1),
        "new_hits":        after["hits"] - before["hits"],
        "still_missing":   after["missing_keywords"],
    }
