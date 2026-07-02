"""
Parses a plain-text job description into tiered keywords, classifies them
by type, and computes a gap analysis against the current resume.
"""

import re
import spacy
from keybert import KeyBERT
from pipeline.utils import extract_all_text

# Score thresholds for keyword tiering
TIER1_THRESHOLD = 0.68
TIER2_THRESHOLD = 0.42

# Loaded lazily to avoid slow import at startup when not in JD mode
_kw_model: KeyBERT | None = None
_nlp = None

# ── Keyword classification ────────────────────────────────────────────────────
# Rule-based, no LLM call needed.

# Known soft/process terms — exact or substring match
_SOFT_PROCESS_TERMS = {
    "agile", "scrum", "kanban", "communication", "collaboration",
    "cross-functional", "stakeholder", "leadership", "ownership",
    "mentoring", "mentorship", "problem solving", "problem-solving",
    "team player", "fast learner", "detail-oriented", "self-starter",
    "proactive", "initiative", "interpersonal", "time management",
    "adaptable", "flexible", "strategic", "roadmap", "planning",
    "sprint", "retrospective", "standup", "jira", "confluence",
    "documentation", "presentation",
}

# Known hard skill signals — substrings that strongly indicate a technical tool
_HARD_SKILL_SIGNALS = {
    # Languages
    "python", "java", "golang", "go", "rust", "c#", "c++", "ruby",
    "typescript", "javascript", "kotlin", "swift", "scala", "php",
    "bash", "shell", "sql", "r language",
    # Frameworks / platforms
    ".net", "node.js", "fastapi", "django", "flask", "spring",
    "express", "react", "vue", "angular", "next.js", "nuxt",
    "laravel", "rails",
    # Cloud / infra
    "aws", "gcp", "azure", "ec2", "s3", "lambda", "rds", "sqs",
    "pubsub", "cloud run", "ecs", "eks", "fargate", "cloudfront",
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible",
    "pulumi", "jenkins", "github actions", "gitlab ci", "circleci",
    # Databases
    "postgresql", "postgres", "mysql", "sql server", "mongodb",
    "redis", "elasticsearch", "cassandra", "dynamodb", "firestore",
    "bigquery", "snowflake", "supabase", "cosmosdb",
    # Protocols / patterns (concrete tools, not concepts)
    "rest", "graphql", "grpc", "websocket", "kafka", "rabbitmq",
    "celery", "airflow", "spark", "flink",
    # Observability
    "datadog", "grafana", "prometheus", "splunk", "sentry", "newrelic",
    # Testing
    "pytest", "jest", "junit", "cypress", "playwright", "selenium",
    # Other concrete tools
    "git", "linux", "nginx", "stripe", "twilio", "openai",
}


def _classify_keyword(kw: str) -> str:
    """
    Classifies a keyword into one of three types:
      hard_skill     — concrete tool, language, or platform
      soft_process   — interpersonal, process, or methodology term
      domain_concept — architectural pattern, practice, or technical domain
                       (everything that isn't hard_skill or soft_process)

    Uses rule-based matching — no LLM call.
    """
    kw_lower = kw.lower()

    # Soft/process check: exact match or substring in known set
    if any(term in kw_lower for term in _SOFT_PROCESS_TERMS):
        return "soft_process"

    # Hard skill check: substring match against known signals
    if any(signal in kw_lower for signal in _HARD_SKILL_SIGNALS):
        return "hard_skill"

    # Everything else: domain concept
    # Heuristic: single short words that aren't in hard skills are likely domain
    # e.g. "scalability", "microservices", "distributed systems", "observability"
    return "domain_concept"


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
            "tier1": [("python", 0.85), ...],
            "tier2": [("rest api", 0.55), ...],
            "tier3": [("agile", 0.31), ...],
        },
        "classified": {
            "hard_skill":     [("python", 0.85), ("docker", 0.77), ...],
            "domain_concept": [("distributed systems", 0.74), ...],
            "soft_process":   [("agile", 0.31), ...],
        },
        "gaps": {
            "missing": ["ci/cd pipelines", ...],
            "partial": ["ml → machine learning", ...],
            "present": ["python", ...],
        }
    }
    """
    kw_model, _ = _get_models()
    cleaned = _clean_jd(jd_text)

    # Extract up to 40 keyphrases (1-3 gram) using MMR for diversity
    raw_keywords: list[tuple[str, float]] = kw_model.extract_keywords(
        cleaned,
        keyphrase_ngram_range=(1, 3),
        stop_words="english",
        use_mmr=True,
        diversity=0.55,
        top_n=40,
    )

    # Deduplicate: remove a unigram if a containing phrase is already present
    phrases = [kw for kw, _ in raw_keywords]
    deduped: list[tuple[str, float]] = []
    for kw, score in raw_keywords:
        is_subsumed = any(kw != phrase and kw in phrase for phrase in phrases)
        if not is_subsumed:
            deduped.append((kw.lower(), round(score, 4)))

    # Tier assignment
    tier1 = [(kw, s) for kw, s in deduped if s >= TIER1_THRESHOLD]
    tier2 = [(kw, s) for kw, s in deduped if TIER2_THRESHOLD <= s < TIER1_THRESHOLD]
    tier3 = [(kw, s) for kw, s in deduped if s < TIER2_THRESHOLD]

    # Keyword classification — applied across all tiers
    classified: dict[str, list[tuple[str, float]]] = {
        "hard_skill":     [],
        "domain_concept": [],
        "soft_process":   [],
    }
    for kw, score in deduped:
        ktype = _classify_keyword(kw)
        classified[ktype].append((kw, score))

    # Gap analysis (only when resume is supplied)
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
        "classified": classified,
        "gaps": gaps,
    }