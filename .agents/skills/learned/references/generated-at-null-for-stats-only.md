# generated_at Must Stay NULL for Stats-Only Assessments

## Pattern
When a table has both deterministic data (Phase 0 stats) and LLM-generated data
(Phase 2 brief), `generated_at` is the sentinel for the LLM phase only.

Phase 0 INSERT must NOT set `generated_at`. Leave it NULL.
Phase 2 UPDATE uses `WHERE generated_at IS NULL` as the idempotency guard.

## Why
Code review caught this bug: initial implementation passed `now` for `generated_at`
in the Phase 0 INSERT. This meant:
1. The idempotency guard `WHERE generated_at IS NULL` in Phase 2 always returned 0 rows
2. LLM brief could never be stored — silent failure
3. Frontend showed `generation_status: "complete"` when only stats existed (no brief)

The `generated_at` field serves two purposes:
- Immutability sentinel (CLAUDE.md rule 4)
- Phase indicator (NULL = stats only, set = LLM brief generated)

Setting it at Phase 0 defeats both.

## How to Apply
- SQL INSERT for stats-only rows: omit `generated_at` from column list (defaults to NULL)
- API response: return `"generation_status": "stats_only"` when `generated_at IS NULL`
- Frontend: show "Generate Brief" button only when `generation_status === "stats_only"`
- Phase 2 UPDATE: `SET generated_at = $N WHERE id = $1 AND generated_at IS NULL`

## Anti-Pattern
```sql
-- WRONG — sets generated_at at stats creation, breaks Phase 2 guard
INSERT INTO source_assessments (..., generated_at) VALUES (..., NOW())

-- CORRECT — leave generated_at NULL for Phase 2 to set
INSERT INTO source_assessments (...) VALUES (...)
-- generated_at defaults to NULL
```

## Session Context
Source Assessment code review finding #1 (2026-06-22).
