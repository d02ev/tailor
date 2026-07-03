# Tailor Technical Documentation

## 1. Overview

Tailor is a Python CLI that automates resume optimization for software engineering roles using a staged AI pipeline with explicit review checkpoints.

Design goals:
- Keep LLM output structurally safe by constraining writes to known resume sections
- Increase ATS alignment in JD mode using keyword extraction and score deltas
- Preserve user control with interactive and manual approval gates before publish
- Maintain extensibility through clear pipeline module boundaries

## 2. Runtime Modes

Tailor has two execution modes in `cli.py`:

- `generic` mode (default):
  - Optimizes writing quality and technical clarity
  - No job description required
- `jd` mode (`--jd` + `--company-name`):
  - Parses JD into keyword tiers
  - Computes ATS baseline and post-pass scores
  - Injects best-matching projects from full project inventory
  - Supports optional CV generation via `--cv`

Constraint:
- `--cv` is valid only in JD mode

## 3. High-Level Architecture

Primary modules:
- `cli.py`: pipeline orchestration, UX, and control flow
- `config.py`: environment-backed settings
- `pipeline/`: execution modules
- `prompts/`: system and user prompt builders per pass/mode

### 3.1 Pipeline Sequence (JD Mode)

1. `loader.fetch_resume()` loads resume JSON from API
2. `jd_parser.parse_jd()` extracts keyword tiers and gap analysis
3. `scorer.ats_score()` computes baseline ATS score
4. `loader.fetch_projects()` + `project_matcher.match_and_inject()` selects top 2 projects
5. `pass1_optimizer.run_pass1()` rewrites sections with LLM
6. `scorer.ats_score()` recomputes ATS score after pass 1
7. `pass2_reviewer.run_pass2()` audits quality and emits structured issues
8. `approver.run_approval_loop()` applies approved fixes
9. Optional: `cv_generator.generate_cv()` generates and exports CV docx
10. `review_checkpoint.write_review_file()` creates editable `assets/resume.json`
11. `publisher.publish_resume()` sends final payload to API
12. `review_checkpoint.cleanup_review_file()` removes checkpoint after successful publish

## 4. Module Responsibilities

### 4.1 `cli.py`

Responsibilities:
- Validates CLI argument combinations
- Presents progress, score reports, and review summaries with Rich
- Runs all stages in order and exits safely on failure
- Supports deferred imports for faster `--help`

Notable UX behaviors:
- Prompts for `template_id` and `resume_name` if omitted
- Manual checkpoint before publishing
- Non-fatal CV failure (publish still proceeds)

### 4.2 `pipeline/loader.py`

- Shared authenticated GET helper `_get()`
- `fetch_resume()`: expects envelope with `data` object
- `fetch_projects()`: expects envelope with `data` list
- Uses `X-Api-Key` header from settings

### 4.3 `pipeline/jd_parser.py`

- Cleans JD text and extracts keywords using `KeyBERT`
- Loads NLP dependencies lazily (`KeyBERT`, `spaCy en_core_web_sm`)
- Keyword tier thresholds (absolute):
  - `Tier 1`: `>= 0.68`
  - `Tier 2`: `0.42–0.68`
  - `Tier 3`: `< 0.42`
  - Adaptive fallback (`_assign_tiers`): when the absolute split leaves Tier 1 empty,
    keywords are re-split by rank percentile (top 30% → Tier 1, next 40% → Tier 2) so
    tiering stays stable across JDs with different score distributions.
- Computes `gaps` (`present`, `partial`, `missing`) against flattened resume text

### 4.4 `pipeline/scorer.py`

Local ATS scoring (no external API):
- `keyword_hit_rate`: **importance-weighted** ratio — each keyword contributes its
  KeyBERT score as weight, so covering high-signal (Tier 1) keywords matters more.
- Matching is **token/lemma based with word boundaries** (spaCy), not raw substring:
  "python" no longer matches "pythonic". Multi-word keywords match as contiguous
  lemma spans, and an acronym↔expansion map (ml↔machine learning, k8s↔kubernetes, …)
  treats equivalent forms as hits.
- `semantic_similarity`: TF-IDF cosine similarity between resume text and JD keyword text
- Composite formula (unchanged):
  - `score = (keyword_hit_rate * 0.65) + (semantic_similarity * 0.35)`

Outputs include missing keyword list and score deltas (`score_delta`).

### 4.5 `pipeline/project_matcher.py`

- Sends slim project objects + JD keyword context to LLM
- Enforces selection target of exactly 2 projects through prompt contract
- Replaces `resume["projects"]` only when selected IDs differ from existing IDs
- Returns reasoning map for CLI display

### 4.6 `pipeline/pass1_optimizer.py`

- **Single LLM call** rewrites the whole resume at once — `experience`, `projects`,
  `techStack`, plus a generated `professionalSummary`. (Previously one call per
  section; consolidating cuts a JD run from ~6–8 calls to ~3–4 for the free tier.)
- Each returned section is shape-validated (`_shape_ok`) before it replaces the
  original — a null/wrong-typed/length-mismatched section falls back to the untouched
  input instead of corrupting the resume.
- Uses `llm_client.chat_json` (JSON response format, low temperature, seed).
- Applies mode-specific prompts (`prompts/generic_pass1.py`, `prompts/jd_pass1.py`),
  both of which inject the shared `prompts/resume_standards.py` directives.

### 4.7 `pipeline/pass2_reviewer.py`

- Audits original vs optimized resume via `llm_client.chat_json`
- Produces structured issue list with severity labels; includes `metric_inflation`
  (implausible/unsupported numbers) and `summary_issue` (professional-summary) checks
- Sorts issues by severity (`high`, `medium`, `low`)
- Applies safe defaults if keys are missing in model output

### 4.8 `pipeline/approver.py`

- Interactive issue-by-issue approval loop
- Supports apply/skip/quit decisions
- Uses `utils.apply_fix_to_resume()` mutation routing per section

### 4.9 `pipeline/review_checkpoint.py`

- Writes final reviewed resume to `assets/resume.json`
- Reloads and validates user-edited JSON object
- Deletes checkpoint file after successful publish

### 4.10 `pipeline/publisher.py`

- POSTs payload to `/resume/generate`
- Payload contract:
  - `resumeData`
  - `templateId`
  - `resumeName`
  - optional `companyName`

### 4.11 `pipeline/cv_generator.py`

- Optional JD-only branch (`--cv`)
- Performs lightweight web research via DuckDuckGo
- Generates plaintext CV with LLM
- Renders CV in terminal and writes formatted `.docx` to `assets/`

Docx formatting highlights:
- US Letter, 1-inch margins, Arial body
- Styled section headers and list bullets
- Safe filename normalization for output

## 5. Prompt Contracts and Safety Strategy

Prompt strategy is split by mode and pass:
- `generic_pass1.py` / `jd_pass1.py`: rewrite directives
- `generic_pass2.py` / `jd_pass2.py`: audit directives
- `cv_prompt.py`: CV generation format contract

Shared standards (`prompts/resume_standards.py`) are injected into every Pass 1
prompt, so rewrite and audit hold the resume to one set of rules (action verbs,
XYZ/STAR, quantification, ATS-safe formatting, truthfulness, professional summary).

Safety controls used:
- "Return JSON only" constraints for pass 1 and pass 2, plus `chat_json` fence-
  stripping + one corrective re-prompt in `llm_client` (malformed JSON no longer crashes)
- Output schema preservation rules (do not rename keys) + shape validation in Pass 1
- Bounds-checked fix routing (`apply_fix_to_resume`) so bad indices are no-ops
- Human approval loop before mutating final output
- `metric_inflation` / `factual_inflation` audit checks against invented or inflated numbers

## 6. Data Model Assumptions

The pipeline assumes resume payloads include sections such as:
- `professionalSummary`: top-level string (generated by Pass 1 if absent)
- `experience`: list with `description` bullet arrays
- `projects`: list with `shortDescription` and `longDescription`
- `techStack`: dictionary of list-based categories

Issue patch routing relies on this structure:
- `professionalSummary` (top-level string)
- `experience[i].description[j]`
- `projects[i].longDescription` or `projects[i].shortDescription`
- `techStack.<sub_key>[j]`

## 7. Configuration

Configured via `pydantic-settings` in `config.py`:
- `API_BASE_URL`
- `API_KEY`
- `GITHUB_ACCESS_TOKEN`
- optional `MODEL` (default: `openai/gpt-4o`)
- optional `LLM_BASE_URL` (default: `https://models.github.ai/inference`)
- free-tier tuning: `REQUEST_TIMEOUT`, `MAX_RETRIES`, `MIN_SECONDS_BETWEEN_CALLS`,
  `CACHE_ENABLED`, `CACHE_DIR`

Environment file:
- `.env.development` (hardcoded in settings config)

### 7.1 LLM client (`pipeline/llm_client.py`)

All model calls route through one shared client:
- tenacity retry with exponential backoff on `429`/`5xx`, honouring `Retry-After`
- throttle (`MIN_SECONDS_BETWEEN_CALLS`) so multi-call runs don't burst the limiter
- explicit request timeout
- on-disk response cache keyed by `sha256(model, temperature, system, user)`; re-runs
  on identical input cost zero quota (`call_count` / `cache_hit_count` reported by CLI)
- `chat()` (plain text) and `chat_json()` (fence-stripping + corrective re-prompt)

## 8. External Dependencies

Core libraries:
- `typer`, `rich` for CLI and terminal UX
- `httpx` for API IO
- `openai` SDK for chat completion calls
- `tenacity` for retry/backoff on the shared LLM client
- `keybert`, `spacy` for keyword extraction and token/lemma ATS matching
- `scikit-learn` for semantic scoring
- `python-docx` for CV export
- `duckduckgo-search` for company context retrieval (with a 10s timeout)

## 9. Error Handling and Recovery

Patterns present in CLI:
- API or stage failures exit with user-readable errors
- CV generation failure is warning-only (non-blocking)
- Publish failure preserves `assets/resume.json` for retry
- Manual checkpoint loader validates JSON object shape

## 10. Operational Notes and Known Gaps

1. Python version pin:
- `pyproject.toml` requires `>=3.14.2`, which may be stricter than necessary and can reduce environment portability.

2. Model endpoint (resolved):
- All calls — Pass 1/2, project matching, cover letter, and CV — now go through
  `pipeline/llm_client.py` using the single `LLM_BASE_URL` from `config.py`. The
  previous split endpoint / undeclared `github_models_api_key` mismatch is gone.

3. Backend schema dependency:
- The pipeline now emits a `professionalSummary` field; the `/resume/generate`
  backend must accept it. Loader validates the fetched resume shape and fails fast
  with a clear message on breaking API changes.

## 11. Extensibility Guide

Common extension paths:

1. Add rewriteable sections:
- Update `REWRITEABLE_SECTIONS` in `pipeline/utils.py` (and the `professionalSummary`
  handling in `pass1_optimizer.run_pass1` if adding another top-level string field)
- Extend the combined payload in the Pass 1 prompt `build()` functions
- Extend `apply_fix_to_resume()` routing (and add a shape check in `_shape_ok`)

2. Add audit issue types:
- Extend prompt schema in pass2 prompts
- Map labels in `ISSUE_TYPE_LABELS`
- Ensure `apply_fix_to_resume()` can route fixes safely

3. Improve ATS scoring:
- Per-keyword tier weighting, phrase-level matching, and acronym normalization are
  already implemented in `scorer.py`; extend the `_ACRONYMS` map for new domains
- Keep the `ats_score` return schema and `score_delta()` stable for CLI compatibility

4. Tune free-tier behaviour:
- Adjust retry/throttle/cache via `config.py` env vars; all LLM calls honour them
  through `pipeline/llm_client.py`

5. Add storage backends:
- Replace or wrap `loader.py` and `publisher.py` HTTP contract layer
- Keep resume shape contract stable for pipeline compatibility

## 12. Running the Project

Install:

```bash
uv sync
```

Run generic mode:

```bash
uv run tailor
```

Run JD mode:

```bash
uv run tailor --jd jd.txt --company-name "Google"
```

Run JD mode with CV generation:

```bash
uv run tailor --jd jd.txt --company-name "Google" --cv
```
