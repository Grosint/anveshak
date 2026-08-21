# Services: Database and SQL

Applies to PostgreSQL and asyncpg code under `services/`, `sdk/`, and `tests/`.
Repo-wide rules are in [../AGENTS.md](../AGENTS.md).
API and frontend data contracts are in [../frontend/AGENTS.md](../frontend/AGENTS.md).

14 learned instincts.

## SQL style

- Module-level SQL constants (`SQL_GET_X = """..."""`), never inline SQL inside functions
- Always parameterized queries (`$1`, `$2`), never f-strings or string interpolation in SQL
- Typed async functions taking `conn: DBConnection` (from `anveshak.db`) or `pool: asyncpg.Pool`
- Never annotate a connection param as `asyncpg.Connection`.
  `pool.acquire()` yields a `PoolConnectionProxy`, so that annotation is wrong at every call site
  even though the proxy forwards Connection methods at runtime.
  `DBConnection` is the union of the two.

## Idempotency

- All replayed inserts use `ON CONFLICT ... DO NOTHING` or `DO UPDATE`.
  See: `.agents/skills/learned/references/idempotent-cron-insert.md`
- Cron jobs inserting rows MUST have a `UNIQUE` constraint preventing dupes
- Immutable fields such as `generated_at` are guarded with `WHERE generated_at IS NULL`,
  which prevents replayed ARQ jobs overwriting. See: `.agents/skills/learned/references/immutable-write-idempotency.md`
- ARQ child jobs are enqueued from the parent, not the scheduler, with a scope guard:
  `if clusters: enqueue(...)` prevents empty enqueues. See: `.agents/skills/learned/references/causal-arq-job-chaining.md`
- Orphan sweep: null completion rows from the last 1h, every 5min, batch 100.
  Catches jobs where the INSERT succeeded but the enqueue failed, since the two are not atomic.
  See: `.agents/skills/learned/references/orphan-sweep-safety-net.md`
- Redis quota guards use INCR, which is atomic, never GET then compare then SET, which races.
  Decrement on reject for an accurate counter. See: `.agents/skills/learned/references/redis-atomic-budget-guard.md`

## Migrations

- Run Alembic inside the container: `docker compose exec api alembic upgrade head`.
  Never from the host, because env vars such as POSTGRES_URL won't pass correctly.
- All migrations are additive: no column drops, no destructive changes
- Seed SQL must match the schema, since column name drift causes a silent `ROLLBACK`.
  Always check output for `ERROR:` or `ROLLBACK`.

## Silent migration failures

After a migration adding a NOT NULL column, update ALL of:

1. **conftest.py factory fixtures**: `make_topic`, `make_source`, `insert_content_item`
2. **Inline SQL in integration tests**: `grep -r 'INSERT INTO <table>' tests/`
3. **Container test scripts**: `scripts/test_analyst_models.py` and similar
4. **Unit test mock rows**: grep `{"id": "topic-1"}` across `tests/unit/`
5. **Service code audit rows**: every INSERT path includes the new column
6. **Seed SQL**: `scripts/seed_demo*.sql`

Checklist shortcut: `grep -r 'INSERT INTO <table>' tests/ scripts/ | grep -v <new_column>`

Why this is invisible: unit tests with a mocked DB pass fine because the column is unchecked.
Integration tests fail but are often skipped in quick CI.
Service code catches the `KeyError` in a generic `except Exception` and produces zero output rather than crashing.
See: `.agents/skills/learned/references/migration-breaks-all-test-fixtures.md`, `.agents/skills/learned/references/seed-sql-schema-sync.md`

Adding a new role value means updating the CHECK constraint in the SAME migration,
BEFORE any INSERT using the new role. Use `DROP CONSTRAINT IF EXISTS` plus `ADD CONSTRAINT`.
See: `.agents/skills/learned/references/role-constraint-migration-order.md`

## Testing

- Adding a new async DB function means grepping all tests mocking that module and adding
  `AsyncMock()` for it, otherwise `await` on a plain MagicMock raises
  `"can't be used in 'await' expression"`
- Use `side_effect=[row1, row2]` (not `return_value`) to mock multiple sequential
  DB calls returning different column schemas

## Backfill

- Use a many-to-many join table (`topic_content_items`) for additive backfill
  rather than an UPDATE on the primary table.
  This preserves UNIQUE constraints and allows an item to belong to multiple topics.

## Source of truth

- The database is ALWAYS authoritative.
  Never rely on Redis or in-memory state for long-lived entities such as jobs, reports, or credibility scores.
  Redis is queues and caches; the DB is truth.
  See: `.agents/skills/learned/references/analysis-jobs-db-source-of-truth.md`

## Atomicity

- Use DB constraints and SQL atomicity for critical paths:
  `ON CONFLICT`, `WHERE sentinel IS NULL`, Redis INCR rather than GET then SET.
  See: `.agents/skills/learned/references/redis-atomic-budget-guard.md`, `.agents/skills/learned/references/immutable-write-idempotency.md`

## SQL correctness checklist

- JOINing tables with the same column name (`labels`, `id`) means always qualifying:
  `ci.labels`, not `labels`. PostgreSQL raises "ambiguous column" at runtime.
  See: `.agents/skills/learned/references/sql-ambiguous-labels-join.md`
- Adding a `$N` parameter to a SQL constant means grepping ALL callers and adding the param.
  A missing param gives `asyncpg.exceptions.DataError` at runtime, not compile time.
  See: `.agents/skills/learned/references/sql-param-count-caller-mismatch.md`
- Use `EXISTS (SELECT 1 FROM ...)` for boolean flags on list queries instead of
  N+1 API calls from the frontend. EXISTS short-circuits and needs no GROUP BY.
  See: `.agents/skills/learned/references/has-vision-exists-subquery.md`
- `ON CONFLICT` requires a conflict target: `ON CONFLICT (id) DO NOTHING`, not bare
  `ON CONFLICT DO NOTHING`, which PostgreSQL accepts but leaves undefined.
- Before writing multi-table SQL (JOINs, aggregates), run `\d tablename` for EACH table.
  Column name assumptions are wrong more often than expected: `is_active` versus
  `status = 'active'`, `platform` on sources rather than content_items.
  Mocked unit tests pass fine, and the error surfaces only at runtime after a container rebuild.
  See: `.agents/skills/learned/references/aggregate-sql-schema-validation.md`

## Pitfalls

- PostgreSQL volumes read the password only on first init.
  If a volume already exists with the wrong credentials, run `ALTER USER ... PASSWORD` inside the container
  rather than recreating the volume and losing data.
