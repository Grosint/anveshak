---
paths:
  - "services/**/*.py"
  - "sdk/**/*.py"
  - "tests/**/*.py"
---
# Database Rules

Consolidated from 9 learned instincts. These apply to all PostgreSQL/asyncpg code.

## SQL Style

- Module-level SQL constants (`SQL_GET_X = """..."""`) — never inline SQL in functions
- Always parameterized queries (`$1`, `$2`) — never f-strings or string interpolation in SQL
- Typed async functions taking `conn: asyncpg.Connection` or `pool: asyncpg.Pool`

## Idempotency

- All inserts that may be replayed use `ON CONFLICT ... DO NOTHING` or `DO UPDATE`
- Cron/scheduled jobs that insert rows MUST have a `UNIQUE` constraint preventing duplicates
- Immutable fields (e.g., `generated_at`) are guarded with `WHERE generated_at IS NULL`
  to prevent replayed ARQ jobs from overwriting

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

## Pitfalls

- PostgreSQL volumes read the password only on first init — if the volume exists
  with wrong credentials, `ALTER USER ... PASSWORD` inside the container rather
  than recreating the volume and losing data
