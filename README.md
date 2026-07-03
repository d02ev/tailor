# Tailor

Tailor is an AI-powered resume optimization CLI that rewrites a software engineer's resume for stronger recruiter readability and better ATS keyword alignment.

It supports two workflows:
- `generic` mode: improve clarity, impact, and technical specificity without a job description
- `jd` mode: tailor the resume to a specific job description, score ATS alignment, optionally generate a targeted CV, and publish the final output

## Why This Project Matters

For recruiters and hiring teams, this project demonstrates a practical AI workflow that combines:
- LLM content rewriting with strict output schema control
- JD keyword extraction and ATS-style scoring
- Human-in-the-loop review before final publish
- API-driven integration with resume/project systems

In short: it is not just "prompt in, text out"; it is an engineered pipeline for production-style resume tailoring.

## Key Capabilities

- Resume ingestion from an external API
- JD parsing with adaptive keyword tiering (`Tier 1`, `Tier 2`, `Tier 3`)
- ATS scoring with importance-weighted, token/lemma keyword matching (acronym-aware)
- AI project selection from a full project catalog (JD mode)
- Generated, summary-first **professional summary** held to senior-resume standards
- Two-pass LLM pipeline:
  - Pass 1: rewrite and optimize the whole resume in a single call
  - Pass 2: audit quality (incl. metric-inflation and summary checks) and surface structured issues
- Interactive approval loop for each suggested fix
- Manual JSON checkpoint before publishing
- Optional CV generation (`.docx`) with company-aware context research
- Free-tier friendly: shared LLM client with retry/backoff, throttling, and response caching

## End-to-End Flow (JD Mode)

1. Fetch resume from API
2. Parse job description into keyword tiers + gap analysis
3. Fetch all projects and inject top 2 JD-relevant projects
4. Run Pass 1 optimization
5. Run Pass 2 quality review
6. Approve/skip fixes interactively
7. (Optional) Generate tailored CV
8. Manually review/edit final `assets/resume.json`
9. Publish final resume payload to API

## Tech Stack

- Python + Typer CLI + Rich terminal UX
- OpenAI-compatible chat completion APIs
- spaCy + KeyBERT for JD keyword extraction and token/lemma ATS matching
- scikit-learn TF-IDF + cosine similarity for ATS scoring
- tenacity for LLM retry/backoff on rate-limited free tiers
- python-docx for CV export
- httpx for API integrations

## Quick Start

### 1) Install dependencies

```bash
uv sync
```

### 2) Configure environment

Create `.env.development` (or adapt `env.example`) with:

```env
API_BASE_URL=""
API_KEY=""
GITHUB_ACCESS_TOKEN=""
MODEL="openai/gpt-4o"
```

### 3) Run

Generic optimization:

```bash
uv run tailor
```

JD-based optimization:

```bash
uv run tailor --jd jd.txt --company-name "Google"
```

JD optimization + CV generation:

```bash
uv run tailor --jd jd.txt --company-name "Google" --cv
```

You can optionally provide:
- `--template-id` to skip template prompt
- `--resume-name` to skip resume name prompt

## Project Structure

```text
tailor/
├─ cli.py
├─ config.py
├─ prompts/
├─ pipeline/
│  ├─ jd_parser.py
│  ├─ project_matcher.py
│  ├─ pass1_optimizer.py
│  ├─ pass2_reviewer.py
│  ├─ approver.py
│  ├─ scorer.py
│  ├─ cv_generator.py
│  ├─ review_checkpoint.py
│  ├─ loader.py
│  └─ publisher.py
└─ docs/
   └─ TECHNICAL_DOC.md
```

## Recruiter Snapshot

This codebase reflects strengths in:
- Product-minded applied AI engineering
- Prompt + schema design for predictable outputs
- Human-AI collaboration patterns (approval gates)
- API integration and pipeline orchestration
- CLI UX and pragmatic operational design

If you want the engineering deep dive, see `docs/TECHNICAL_DOC.md`.
