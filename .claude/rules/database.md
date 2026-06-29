---
paths:
  - "services/**/*.py"
  - "sdk/**/*.py"
  - "tests/**/*.py"
---
# Database Rules

14 learned instincts. All PostgreSQL/asyncpg code.

## SQL Style

- Module-level SQL constants (`SQL_GET_X = """..."""`) — never inline SQL in functions
- Always parameterized queries (`$1`, `$2`) — never f-strings or string interpolation in SQL
- Typed async functions taking `conn: asyncpg.Connection` or `pool: asyncpg.Pool`

## Idempotency

- All replayed inserts use `ON CONFLICT ... DO NOTHING` or `DO UPDATE`
  See: `learned/idempotent-cron-insert.md`
- Cron jobs inserting rows MUST have `UNIQUE` constraint preventing dupes
- Immutable fields (e.g., `generated_at`) guarded with `WHERE generated_at IS NULL`
  — prevents replayed ARQ jobs overwriting. See: `learned/immutable-write-idempotency.md`
- ARQ child jobs enqueued from parent (not scheduler) with scope guard:
  `if clusters: enqueue(...)` — prevents empty enqueues. See: `learned/causal-arq-job-chaining.md`
- Orphan sweep: null completion rows from last 1h, every 5min, batch 100.
  Catches jobs where INSERT succeeded but enqueue failed (not atomic).
  See: `learned/orphan-sweep-safety-net.md`
- Redis quota guards use INCR (atomic), never GET→compare→SET (race condition).
  Decrement on reject for accurate counter. See: `learned/redis-atomic-budget-guard.md`

## Migrations

- Run Alembic inside container: `docker compose exec api alembic upgrade head`
  Never from host — env vars (POSTGRES_URL) won't pass correctly
- All migrations additive — no column drops, no destructive changes
- Seed SQL must match schema — silent `ROLLBACK` on column name drift;
  always check output for `ERROR:` or `ROLLBACK`

## Silent Migration Failures

After migration adding NOT NULL column, update ALL:
1. **conftest.py factory fixtures** — `make_topic`, `make_source`, `insert_content_item`
2. **Inline SQL in integration tests** — `grep -r 'INSERT INTO <table>' tests/`
3. **Container test scripts** — `scripts/test_analyst_models.py`, etc.
4. **Unit test mock rows** — grep `{"id": "topic-1"}` across `tests/unit/`
5. **Service code audit rows** — every INSERT path includes new column
6. **Seed SQL** — `scripts/seed_demo*.sql`

Checklist shortcut: `grep -r 'INSERT INTO <table>' tests/ scripts/ | grep -v <new_column>`

Why invisible: unit tests with mocked DB pass fine (column unchecked).
Integration tests fail but often skipped in quick CI. Service code catches
`KeyError` in generic `except Exception` — produces zero output, not crash.
See: `learned/migration-breaks-all-test-fixtures.md`, `learned/seed-sql-schema-sync.md`

Adding new role value → update CHECK constraint in SAME migration,
BEFORE any INSERT using new role. Use `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`.
See: `learned/role-constraint-migration-order.md`

## Testing

- Adding new async DB function → grep all tests mocking that module, add
  `AsyncMock()` for new function — otherwise `await` on plain MagicMock raises
  `"can't be used in 'await' expression"`
- Use `side_effect=[row1, row2]` (not `return_value`) to mock multiple sequential
  DB calls returning different column schemas

## Backfill

- Use many-to-many join table (`topic_content_items`) for additive backfill
  not UPDATE on primary table — preserves UNIQUE constraints, allows item
  belonging to multiple topics

## Source of Truth

- Database ALWAYS authoritative. Never rely on Redis or in-memory state
  for long-lived entities (jobs, reports, credibility scores).
  Redis = queues and caches. DB = truth.
  See: `learned/analysis-jobs-db-source-of-truth.md`

## Atomicity

- Use DB constraints and SQL atomicity for critical paths
  `ON CONFLICT`, `WHERE sentinel IS NULL`, Redis INCR (not GET→SET)
  See: `learned/redis-atomic-budget-guard.md`, `learned/immutable-write-idempotency.md`

## SQL Correctness Checklist

- JOINing tables with same column name (`labels`, `id`) → always qualify:
  `ci.labels`, not `labels`. PostgreSQL raises "ambiguous column" at runtime.
  See: `learned/sql-ambiguous-labels-join.md`
- Adding `$N` parameter to SQL constant → grep ALL callers, add param.
  Missing param → `asyncpg.exceptions.DataError` at runtime, not compile time.
  See: `learned/sql-param-count-caller-mismatch.md`
- Use `EXISTS (SELECT 1 FROM ...)` for boolean flags on list queries instead of
  N+1 API calls from frontend. EXISTS short-circuits, no GROUP BY needed.
  See: `learned/has-vision-exists-subquery.md`
- `ON CONFLICT` requires conflict target: `ON CONFLICT (id) DO NOTHING`, not bare
  `ON CONFLICT DO NOTHING` (PostgreSQL accepts but behavior undefined).
- Before writing multi-table SQL (JOINs, aggregates), run `\d tablename` for EACH
  table. Column name assumptions wrong more often than expected (`is_active` vs
  `status = 'active'`, `platform` on sources not content_items). Mocked unit tests
  pass fine — error only at runtime after container rebuild.
  See: `learned/aggregate-sql-schema-validation.md`

## Pitfalls

- PostgreSQL volumes read password only on first init — if volume exists
  with wrong credentials, `ALTER USER ... PASSWORD` inside container rather
  than recreating volume and losing data