"""
Local ATS scorer — no external APIs required.

Composite score = (keyword_hit_rate × 0.65) + (semantic_similarity × 0.35)

Rationale: most commercial ATS systems weight exact keyword presence more heavily
than semantic proximity, so the composite reflects realistic scoring behaviour.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pipeline.utils import extract_all_text


def ats_score(resume: dict, keywords: list[tuple[str, float]]) -> dict:
    """
    Args:
        resume:   The resume dict (pre or post optimisation).
        keywords: List of (keyword, score) tuples from jd_parser (all tiers combined).

    Returns:
        {
            "composite_ats_score": 84.7,
            "keyword_hit_rate":    91.2,
            "semantic_similarity": 73.1,
            "hits":   31,
            "total":  34,
            "missing_keywords": ["stakeholder management", ...]
        }
    """
    resume_text = extract_all_text(resume)
    jd_text     = " ".join(kw for kw, _ in keywords)

    try:
        vectorizer   = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
        semantic     = float(cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]) * 100
    except ValueError:
        semantic = 0.0

    all_keywords = [kw.lower() for kw, _ in keywords]
    hits         = [kw for kw in all_keywords if kw in resume_text]
    missing      = [kw for kw in all_keywords if kw not in resume_text]
    hit_rate     = (len(hits) / len(all_keywords) * 100) if all_keywords else 0.0

    composite = round((hit_rate * 0.65) + (semantic * 0.35), 1)

    return {
        "composite_ats_score": composite,
        "keyword_hit_rate":    round(hit_rate, 1),
        "semantic_similarity": round(semantic, 1),
        "hits":                len(hits),
        "total":               len(all_keywords),
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