---
name: data-quality-gates
description: "Schema validation, contract testing, and LLM output validation. Covers verifying live column names before multi-table SQL, source-scan contract tests for ARQ queue mismatches, golden test data for ML pipelines, L2-normalized test embeddings, LLM output retry, and generated_at NULL as a phase sentinel. Use when writing SQL across multiple tables, contract tests, or validating LLM output."
---

# Data Quality Gates & Validation

6 learned instincts. Schema validation, contract testing, golden data, test embeddings, LLM output, phase sentinels.

## Aggregate SQL Schema Validation

- Before writing SQL touching 2+ tables, run `\d` for each table — verify column names against live schema
  Common traps: `is_active` vs `status = 'active'`, `platform` via JOIN not direct column, `generated_at` can be NULL
  Mocked DB tests pass fine, error only surfaces at runtime (500) after container rebuild
  See: `.agents/skills/learned/references/aggregate-sql-schema-validation.md`

## Contract Tests via Source Scanning

- Source-scan contract tests catch queue/function mismatches mocked integration tests miss
  Import all `WorkerSettings` → collect registry. Regex scan `services/**/*.py` for `enqueue_job` calls. Cross-reference both directions
  Verify function names match `WorkerSettings.functions` list. Default queue (`arq:queue`) = always a bug
  See: `.agents/skills/learned/references/contract-test-source-scan.md`

## Golden Test Data for ML Pipelines

- Write test content in each supported language w/ pre-decided expected outputs
  Run through real models inside container, NOT on host. Fuzzy keyword matching (3/5, not 5/5) — NLLB non-deterministic
  Cross-language clustering: assert intra-narrative similarity > 0.5, inter-narrative < intra. Never assert exact cluster membership
  See: `.agents/skills/learned/references/golden-test-data-ml-pipeline.md`

- Test embeddings must be L2-normalized (sentence-transformers outputs unit vectors)
  Seeded RNG, perturb base vectors w/ controlled noise
  Calibration: 0.02 noise (tight clusters), 0.03 (realistic), 0.05 (broad topics)
  See: `.agents/skills/learned/references/test-embedding-realism.md`

## LLM Output Validation with Progressive Retry

- Strip JSON markdown fences before `json.loads()`. Fallback: find outermost `{ ... }`
  Progressive retry: tighten prompt each failure ("JSON only, no preamble"). Embed exact JSON schema in every prompt
  Caller treats `None` as hard failure — never store partial output. Always `labels: Labels` on LLM output schemas
  See: `.agents/skills/learned/references/llm-validated-output-retry.md`

## generated_at NULL for Stats-Only Phase

- Phase 0 INSERT must NOT set `generated_at` — leave NULL. Phase 2 UPDATE uses `WHERE generated_at IS NULL` as idempotency guard
  Setting at Phase 0 defeats both immutability sentinel (CLAUDE.md rule 4) and phase indicator
  API returns `generation_status: "stats_only"` when NULL. Frontend shows "Generate Brief" button only then
  See: `.agents/skills/learned/references/generated-at-null-for-stats-only.md`
