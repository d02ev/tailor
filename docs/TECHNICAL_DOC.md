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
- Keyword tier thresholds:
  - `Tier 1`: `>= 0.68`
  - `Tier 2`: `0.42–0.68`
  - `Tier 3`: `< 0.42`
- Computes `gaps` (`present`, `partial`, `missing`) against flattened resume text

### 4.4 `pipeline/scorer.py`

Local ATS scoring (no external API):
- `keyword_hit_rate`: direct keyword presence ratio
- `semantic_similarity`: TF-IDF cosine similarity between resume text and JD keyword text
- Composite formula:
  - `score = (keyword_hit_rate * 0.65) + (semantic_similarity * 0.35)`

Outputs include missing keyword list and score deltas (`score_delta`).

### 4.5 `pipeline/project_matcher.py`

- Sends slim project objects + JD keyword context to LLM
- Enforces selection target of exactly 2 projects through prompt contract
- Replaces `resume["projects"]` only when selected IDs differ from existing IDs
- Returns reasoning map for CLI display

### 4.6 `pipeline/pass1_optimizer.py`

- Section-by-section rewrite loop over `REWRITEABLE_SECTIONS`:
  - `experience`
  - `projects`
  - `techStack`
- Uses JSON response format and low temperature for deterministic structure
- Applies mode-specific prompts:
  - `prompts/generic_pass1.py`
  - `prompts/jd_pass1.py`

### 4.7 `pipeline/pass2_reviewer.py`

- Audits original vs optimized resume via LLM
- Produces structured issue list with severity labels
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

Safety controls used:
- "Return JSON only" constraints for pass 1 and pass 2
- Output schema preservation rules (do not rename keys)
- Section-scoped processing to reduce accidental structural drift
- Human approval loop before mutating final output

## 6. Data Model Assumptions

The pipeline assumes resume payloads include sections such as:
- `experience`: list with `description` bullet arrays
- `projects`: list with `shortDescription` and `longDescription`
- `techStack`: dictionary of list-based categories

Issue patch routing relies on this structure:
- `experience[i].description[j]`
- `projects[i].longDescription` or `projects[i].shortDescription`
- `techStack.<sub_key>[j]`

## 7. Configuration

Configured via `pydantic-settings` in `config.py`:
- `API_BASE_URL`
- `API_KEY`
- `GITHUB_ACCESS_TOKEN`
- optional `MODEL` (default: `openai/gpt-4o`)

Environment file:
- `.env.development` (hardcoded in settings config)

## 8. External Dependencies

Core libraries:
- `typer`, `rich` for CLI and terminal UX
- `httpx` for API IO
- `openai` SDK for chat completion calls
- `keybert`, `spacy` for keyword extraction
- `scikit-learn` for semantic scoring
- `python-docx` for CV export
- `duckduckgo-search` for company context retrieval

## 9. Error Handling and Recovery

Patterns present in CLI:
- API or stage failures exit with user-readable errors
- CV generation failure is warning-only (non-blocking)
- Publish failure preserves `assets/resume.json` for retry
- Manual checkpoint loader validates JSON object shape

## 10. Operational Notes and Known Gaps

1. Python version pin:
- `pyproject.toml` requires `>=3.14.2`, which may be stricter than necessary and can reduce environment portability.

2. CV config mismatch risk:
- `cv_generator.py` reads `settings.github_models_api_key`, but `config.py` does not declare `github_models_api_key`.
- If not resolved in runtime settings behavior, `--cv` may fail before or during model invocation.

3. Model endpoint split:
- Pass 1/2 and project matching use `https://models.github.ai/inference`
- CV generation uses `https://models.inference.ai.azure.com`
- This is valid but should be intentional and documented in deployment config.

4. API schema dependency:
- Loader and publisher assume a fixed envelope and endpoint structure.
- Breaking API changes will fail fast.

## 11. Extensibility Guide

Common extension paths:

1. Add rewriteable sections:
- Update `REWRITEABLE_SECTIONS` in `pipeline/utils.py`
- Extend prompt schema rules and fix routing logic

2. Add audit issue types:
- Extend prompt schema in pass2 prompts
- Map labels in `ISSUE_TYPE_LABELS`
- Ensure `apply_fix_to_resume()` can route fixes safely

3. Improve ATS scoring:
- Add weighting per keyword tier
- Add phrase-level matching and acronym normalization
- Keep `score_delta()` stable for CLI output compatibility

4. Add storage backends:
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
