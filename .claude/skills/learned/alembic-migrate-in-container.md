---
name: alembic-migrate-in-container
description: run Alembic migrations inside the container — host alembic uses wrong DB URL
type: feedback
---

**Never run Alembic migrations from the host shell** when the DB is inside Docker.

**Why it breaks:** the host alembic reads `POSTGRES_URL` from the shell environment. That
variable is NOT exported from `.env` to the shell — it's only passed to Docker containers via
`--env-file`. The host falls back to the hardcoded default in `migrations/env.py`:

```python
_db_url = os.getenv(
    "POSTGRES_URL",
    "postgresql://anveshak:anveshak@localhost:5433/anveshak",  # ← fallback password
)
```

If `.env` has a different `POSTGRES_PASSWORD`, this login fails with
`password authentication failed`.

**Fix:** run migrations inside the running API container, which already has the correct env:

```makefile
migrate:
    $(COMPOSE) exec -T api alembic upgrade head
```

**Why:** the container inherits `POSTGRES_URL` from the compose env block (which substitutes
`${POSTGRES_PASSWORD}` from `.env`). No manual env export needed.

**How to apply:** any Makefile `migrate` target that runs alembic on the host — move it into
the container. The API service already has alembic installed and the migrations directory
copied in by the Dockerfile.
