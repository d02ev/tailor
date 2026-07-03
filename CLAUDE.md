# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies:
```bash
uv sync
```

Run generic optimization (no JD):
```bash
uv run tailor
```

Run JD-based optimization:
```bash
uv run tailor --jd jd.txt --company-name "Google"
```

Run JD optimization with cover letter generation:
```bash
uv run tailor --jd jd.txt --company-name "Google" --cover-letter
```

There is no test suite.

## Architecture

Tailor is a two-pass LLM pipeline CLI. `cli.py` is the orchestrator — it runs all stages in sequence and handles UX. Pipeline modules live in `pipeline/`, prompt builders in `prompts/`.

**Two modes:**
- **Generic** (default): rewrites `experience`, `projects`, `techStack` for clarity and impact
- **JD** (`--jd` + `--company-name`): additionally parses the job description into keyword tiers, scores ATS alignment before/after Pass 1, and uses AI to select the 2 best-matching projects from the full project catalog

**Pipeline sequence (JD mode):**
1. `loader.fetch_resume()` — GET resume JSON from API
2. `jd_parser.parse_jd()` — KeyBERT + spaCy keyword extraction, tiered by score threshold; also classifies keywords into `hard_skill`, `domain_concept`, `soft_process` (stored in `jd_context["classified"]`)
3. `scorer.ats_score()` — local baseline: TF-IDF cosine similarity + **importance-weighted, token/lemma keyword matching** (word-boundary, with acronym↔expansion equivalence — not raw substring)
4. `loader.fetch_projects()` + `project_matcher.match_and_inject()` — LLM picks top 2 projects, replaces `resume["projects"]` only if IDs differ
5. `pass1_optimizer.run_pass1()` — **single-call** LLM rewrite of all `REWRITEABLE_SECTIONS` + a generated `professionalSummary` (one request, not one per section)
6. `scorer.ats_score()` — post-Pass 1 ATS delta; **if score declined, pipeline exits early** (cover letter still generated if `--cover-letter` was given, using the original resume)
7. `pass2_reviewer.run_pass2()` — LLM audits original vs optimized, emits structured issues with severity; receives `ats_scores` for context
8. `approver.run_approval_loop()` — interactive per-issue apply/skip/quit
9. Optional: `cover_letter_generator.generate_cover_letter()` — DuckDuckGo website lookup + user confirmation → company research → LLM generates 4-paragraph letter → rendered in terminal + saved as `.docx` in cwd
10. `review_checkpoint.write_review_file()` — writes `assets/resume.json` for manual editing
11. `publisher.publish_resume()` — POST to `/resume/generate`
12. `review_checkpoint.cleanup_review_file()` — removes checkpoint on success

**Resume data model** the pipeline assumes:
- `professionalSummary` — top-level string, generated/rewritten by Pass 1 (senior-standard summary-first resume)
- `experience[i].description` — list of bullet strings
- `projects[i].longDescription` / `projects[i].shortDescription` — strings
- `techStack.<sub_key>` — list of strings

`REWRITEABLE_SECTIONS` in `pipeline/utils.py` controls the structured sections Pass 1 rewrites; `professionalSummary` is handled explicitly alongside them (it's a top-level string, not a section). `apply_fix_to_resume()` in the same file handles mutation routing for Pass 2 approved fixes (bounds-checked) — extend both when adding new rewriteable sections. Shared best-practice directives live in `prompts/resume_standards.py` and are injected into every Pass 1 prompt.

**All LLM calls go through `pipeline/llm_client.py`** — a single shared client with tenacity retry/backoff (429/5xx, honours `Retry-After`), a throttle between calls, an explicit timeout, an on-disk response cache (`.tailor_cache/`), and JSON hardening (`chat_json` strips markdown fences and does one corrective re-prompt). `llm_client.call_count` / `cache_hit_count` are surfaced by the CLI at the end of a run. Do **not** instantiate `OpenAI(...)` directly in pipeline modules — call `llm_client.chat()` / `chat_json()`.

**Prompt files** are paired by mode and pass:
- `prompts/generic_pass1.py`, `prompts/jd_pass1.py` — rewrite directives (consolidated, whole-resume payload)
- `prompts/generic_pass2.py`, `prompts/jd_pass2.py` — audit directives (include `metric_inflation` + `summary_issue` checks)
- `prompts/resume_standards.py` — shared `STANDARDS` + `SUMMARY_RULES`
- `prompts/cover_letter_prompt.py` — cover letter format contract

The LLM endpoint and free-tier behaviour are configured in `config.py` (`llm_base_url`, defaults to `https://models.github.ai/inference`).

## Configuration

Settings are loaded from `.env.development` via `pydantic-settings` in `config.py`:

```env
API_BASE_URL=""
API_KEY=""
GITHUB_ACCESS_TOKEN=""
MODEL="openai/gpt-4o"                 # optional, this is the default
LLM_BASE_URL="https://models.github.ai/inference"   # optional
# Free-tier rate-limit tuning (all optional, defaults shown)
REQUEST_TIMEOUT="60"
MAX_RETRIES="5"
MIN_SECONDS_BETWEEN_CALLS="3"
CACHE_ENABLED="true"
CACHE_DIR=".tailor_cache"
```

See `env.example` for the template. Delete `.tailor_cache/` to force fresh LLM calls.

## Known Gaps

- **Python version pin**: `pyproject.toml` requires `>=3.14.2`, which may be stricter than necessary.
- **`professionalSummary` field**: must be accepted by the backend `/resume/generate` payload (the schema was extended for this).
