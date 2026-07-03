"""
Single source of truth for resume best-practices directives.

These rules were previously restated (and drifted) across the Pass 1/Pass 2 prompt
files. Centralising them here means every pass audits and rewrites against the same
industry standard. The human-readable mirror lives in docs/RESUME_BEST_PRACTICES.md.
"""

# Core content standards — injected into every rewrite (Pass 1) prompt.
STANDARDS = """\
RESUME BEST-PRACTICE STANDARDS (apply to every section):

ACTION & IMPACT
- Every experience bullet starts with a strong action verb: past tense for prior
  roles, present tense for the current role. Never start with a pronoun or article.
- Ban weak verbs: worked, helped, assisted, handled, participated, involved, utilized,
  leveraged, responsible for, managed (unless it is genuine people management).
- Apply the XYZ / STAR formula explicitly: "Accomplished [X], measured by [Y], by
  doing [Z]." Every bullet should convey Situation/Task, Action, and Result.
- Quantify every achievement. Prefer hard metrics — latency (ms/%), throughput
  (req/s), scale (users/records/QPS), time saved (hrs/%), cost ($/%), uptime (%),
  revenue. Where no metric exists, add scope signals: team size, data volume, traffic,
  timeline. Do NOT invent numbers (see TRUTHFULNESS).
- Power of three: across a role's bullets, balance technical depth, scope/scale, and
  business impact — not three bullets that all say the same kind of thing.

STRUCTURE & LENGTH
- 3–5 bullets per experience role. Most impactful first; reverse-chronological order.
- Each bullet is 1–2 lines. longDescription: 2–3 sentences (problem → impact →
  technical differentiator). shortDescription: one sentence, max 20 words, outcome-first.
- Replace generic tech with specific tech: "database" → "PostgreSQL 15",
  "cloud" → "AWS (EC2, RDS, S3)".

ATS SAFETY
- Use standard section names and plain characters only. No tables, columns, graphics,
  emojis, or decorative symbols (arrows →, pipes │, bullets within a line) that resume
  parsers misread.
- Spell out an acronym on first use, then use the acronym: "continuous integration
  (CI)". Match the job description's exact terminology; do not substitute synonyms.

SKILLS (techStack)
- List concrete, current, relevant technologies only. No soft skills, no vague entries
  ("modern frameworks"). Cluster by domain within the existing sub-lists.

TRUTHFULNESS
- Do not fabricate or inflate experience, metrics, tools, scope, or titles. Only use
  facts present or strongly implied in the source resume. A conservative true metric
  always beats an impressive invented one.

FORMAT
- Standardise to American English. Fix all grammar, spelling, and punctuation.
- Return ONLY valid JSON matching the requested schema. No commentary, no markdown fences.
"""

# Professional-summary contract — a summary-first resume is the senior-level standard.
SUMMARY_RULES = """\
PROFESSIONAL SUMMARY:
- 3–4 lines (roughly 40–60 words). No bullet points, no first-person pronouns.
- Lead with seniority + primary domain, then the strongest quantified achievement,
  then the technologies/impact areas most relevant to the target role.
- Draw only from facts in the resume. Do not invent scope or metrics.
- In JD mode, mirror the role's core themes and exact terminology without keyword
  stuffing — it should read like a human wrote it, not like it was optimised.
"""
