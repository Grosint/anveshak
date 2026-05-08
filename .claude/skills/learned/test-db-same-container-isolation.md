# Test DB: Same Container, Separate Database

## Problem
Integration tests inserting into the production database caused data pollution.
239 orphaned test topics and 410 sources accumulated from incomplete fixture
teardowns. Transaction-rollback (`db_conn`) works for single-connection tests
but not for pool-based service functions that `pool.acquire()` internally.

## Solution
Create a second database (`anveshak_test`) in the same postgres container:

1. **Init script** (`init-pgvector.sql`) creates the DB + extensions on first start
2. **`make create-test-db`** handles existing volumes (idempotent CREATE DATABASE)
3. **`make migrate-test`** runs Alembic inside the API container with overridden POSTGRES_URL
4. **`make test-integration`** auto-runs create + migrate before tests (zero setup for devs)
5. **`tests/conftest.py`** reads `POSTGRES_TEST_URL` (not `POSTGRES_URL`) — tests never inherit production URL
6. **Safety guard** in integration conftest: `pytest.exit()` if URL points at production DB

## Why not a separate container?
Same postgres container is simpler — no extra memory, no extra healthcheck,
shared credentials. A second database in the same server provides full schema
isolation. The only overhead is `make migrate-test` (~1s).

## Why not just transaction rollback everywhere?
Pool-based service functions (`run_clustering(topic_id, pool)`) call
`pool.acquire()` internally, getting a NEW connection that cannot see
uncommitted data from the test's rollback transaction. Only conn-based
functions (`list_signals(conn, ...)`) can use `db_conn`.

## Key files
- `infra/configs/postgres/init-pgvector.sql` — DB creation
- `Makefile` — `create-test-db`, `migrate-test`, `migrate-all`
- `tests/conftest.py` — `POSTGRES_TEST_URL` default
- `tests/integration/conftest.py` — `_refuse_production_db` safety guard

## Pitfall: Alembic inside vs outside container
Running Alembic from the host requires the correct password in env.
Running inside the container (`docker compose exec -T -e POSTGRES_URL=... api alembic upgrade head`)
uses the container's credentials — always prefer this approach.
