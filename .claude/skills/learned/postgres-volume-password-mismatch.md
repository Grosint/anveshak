---
name: postgres-volume-password-mismatch
description: postgres volume initialized with old/blank password — how to detect and fix
type: feedback
---

PostgreSQL only reads `POSTGRES_PASSWORD` **on first initialisation** (when the data
directory is empty). If the volume was created with a blank or different password, changing
`.env` does NOT change the DB password — the volume wins.

**Symptom:** services connecting to postgres fail with
`asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "anveshak"`
even though `.env` looks correct.

**Diagnosis:**
```bash
# Connect without password (peer auth from inside container always works)
docker compose exec postgres psql -U anveshak -d anveshak -c "SELECT 1"
# → if this succeeds, the volume exists and is accessible
```

**Fix:** update the DB password to match `.env` without wiping the volume:
```bash
docker compose exec postgres psql -U anveshak -d anveshak \
  -c "ALTER USER anveshak PASSWORD '$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)';"
```

**When it happens:** typically when containers were first started without `.env` (blank
password), then `.env` was populated later. The volume keeps the old (blank) password.

**Prevention:** always populate `.env` from `.env.example` BEFORE the first `make up`.
`make fresh-all` is safe if `.env` is set before the very first run.

**How to apply:** any time API/scraper/social/analyst services fail to start with
`InvalidPasswordError` — run the ALTER USER fix above rather than wiping volumes.
