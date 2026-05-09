---
paths:
  - "services/**/*.py"
  - "sdk/**/*.py"
  - "tests/**/*.py"
---
# Database Rules

Consolidated from 14 learned instincts. These apply to all PostgreSQL/asyncpg code.

## SQL Style

- Module-level SQL constants (`SQL_GET_X = """..."""`) — never inline SQL in functions
- Always parameterized queries (`$1`, `$2`) — never f-strings or string interpolation in SQL
- Typed async functions taking `conn: asyncpg.Connection` or `pool: asyncpg.Pool`

## Idempotency

- All inserts that may be replayed use `ON CONFLICT ... DO NOTHING` or `DO UPDATE`
  See: `learned/idempotent-cron-insert.md`
- Cron/scheduled jobs that insert rows MUST have a `UNIQUE` constraint preventing duplicates
- Immutable fields (e.g., `generated_at`) are guarded with `WHERE generated_at IS NULL`
  to prevent replayed ARQ jobs from overwriting. See: `learned/immutable-write-idempotency.md`
- ARQ child jobs enqueued from parent (not scheduler) with scope guard:
  `if clusters: enqueue(...)` — prevents empty enqueues. See: `learned/causal-arq-job-chaining.md`
- Orphan sweep: query rows with null completion from last 1h, every 5min, batch of 100.
  Catches jobs where INSERT succeeded but enqueue failed (not atomic).
  See: `learned/orphan-sweep-safety-net.md`
- Redis quota guards use INCR (atomic), never GET→compare→SET (race condition).
  Decrement on reject to keep counter accurate. See: `learned/redis-atomic-budget-guard.md`

## Migrations

- Run Alembic inside the container: `docker compose exec api alembic upgrade head`
  Never from the host — env vars (POSTGRES_URL) won't be passed correctly
- All migrations are additive — no column drops, no destructive changes
- Seed SQL must match actual schema — silent `ROLLBACK` occurs on column name drift;
  always check output for `ERROR:` or `ROLLBACK`

## Testing

- When adding a new async DB function, grep all tests mocking that module and add
  `AsyncMock()` for the new function — otherwise `await` on a plain MagicMock raises
  `"can't be used in 'await' expression"`
- Use `side_effect=[row1, row2]` (not `return_value`) to mock multiple sequential
  DB calls that return different column schemas

## Backfill

- Use a many-to-many join table (`topic_content_items`) for additive backfill
  rather than UPDATE on the primary table — preserves UNIQUE constraints and
  allows an item to belong to multiple topics

## Source of Truth

- The database is ALWAYS authoritative. Never rely on Redis or in-memory state
  as the record for long-lived entities (jobs, reports, credibility scores).
  Redis is for queues and caches — DB is for truth.
  See: `learned/analysis-jobs-db-source-of-truth.md`

## Atomicity

- Use database constraints and SQL atomicity for critical paths
  `ON CONFLICT`, `WHERE sentinel IS NULL`, Redis INCR (not GET→SET)
  See: `learned/redis-atomic-budget-guard.md`, `learned/immutable-write-idempotency.md`

## Pitfalls

- PostgreSQL volumes read the password only on first init — if the volume exists
  with wrong credentials, `ALTER USER ... PASSWORD` inside the container rather
  than recreating the volume and losing data
