# Resume Best Practices

This is the human-readable mirror of the directives Tailor enforces in
`prompts/resume_standards.py`. Both Pass 1 (rewrite) and Pass 2 (audit) hold the
resume to these standards. Edit the module and this file together.

## Action & impact
- Every experience bullet starts with a strong action verb — past tense for prior
  roles, present tense for the current role. Never start with a pronoun or article.
- Banned weak verbs: worked, helped, assisted, handled, participated, involved,
  utilized, leveraged, responsible for, managed (unless genuine people management).
- Apply the **XYZ / STAR** formula explicitly: "Accomplished [X], measured by [Y],
  by doing [Z]" — Situation/Task, Action, Result.
- **Quantify** every achievement (latency, throughput, scale, time saved, cost,
  uptime, revenue). Where no metric exists, use scope signals: team size, data
  volume, traffic, timeline.
- **Power of three**: across a role, balance technical depth, scope/scale, and
  business impact.

## Structure & length
- 3–5 bullets per experience role; most impactful first; reverse-chronological order.
- Bullets are 1–2 lines. `longDescription`: 2–3 sentences (problem → impact →
  differentiator). `shortDescription`: one sentence, ≤ 20 words, outcome-first.
- **Professional summary** leads the resume: 3–4 lines, no pronouns, no bullets —
  seniority + domain, strongest quantified achievement, then the most role-relevant
  technologies.
- Replace generic tech with specifics ("database" → "PostgreSQL 15").

## ATS safety
- Standard section names, plain characters only. No tables, columns, graphics,
  emojis, or in-line decorative symbols (→, │) that parsers misread.
- Spell out an acronym on first use, then use it: "continuous integration (CI)".
- Match the job description's exact terminology; don't substitute synonyms.

## Skills (techStack)
- Concrete, current, relevant technologies only. No soft skills, no vague entries.
  Cluster by domain within the existing sub-lists.

## Truthfulness
- Never fabricate or inflate experience, metrics, tools, scope, or titles. Use only
  facts present or strongly implied in the source resume. Pass 2 flags both
  `factual_inflation` (invented facts) and `metric_inflation` (numbers that are
  unsupported, physically implausible, or a vague original turned into a hard figure).
  A conservative true metric beats an impressive invented one.

## JD alignment (JD mode)
- Tell the story of someone who can do this job; let keywords emerge from honest,
  specific work. Demonstrate domain concepts rather than name-dropping them.
- A resume that passes ATS but reads as AI-optimised is worse than one that scores
  slightly lower but reads like a human wrote it about real work.
