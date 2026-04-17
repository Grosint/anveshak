# Docker Compose Project Name Consistency

## When to load: writing scripts, Makefile targets, or backup/restore tools that call docker compose

---

## Problem

Docker Compose determines the project name (which prefixes all container and volume names) from:
1. `-p <name>` flag (highest priority)
2. `COMPOSE_PROJECT_NAME` env var
3. Directory name where compose runs (default)

If you run `docker compose -f infra/compose.yml` from different directories without `-p`, you get different project names → compose can't find existing containers → network overlap errors.

```bash
# From /anveshak/ → project "anveshak" → containers: anveshak-api-1
# From /anveshak/infra/ → project "infra" → tries to create infra-api-1
# Error: "Pool overlaps with other one on this address space"
```

## Pattern

Define a single COMPOSE variable in every script and Makefile target:

```bash
# scripts/backup.sh, scripts/restore.sh
COMPOSE="docker compose --env-file .env -p anveshak -f infra/compose.yml"
${COMPOSE} exec -T postgres pg_dump ...

# Makefile
COMPOSE := docker compose --env-file .env -p anveshak -f infra/compose.yml
up:
	$(COMPOSE) up -d
ps:
	$(COMPOSE) ps
```

**Three things that must match:**
1. `-p anveshak` — same project name everywhere
2. `--env-file .env` — explicit path (don't rely on auto-discovery)
3. `-f infra/compose.yml` — explicit compose file path

**Volume names follow project name:** `anveshak_postgres_data`, `anveshak_redis_data`, etc. If project name is wrong, `docker volume inspect` won't find them.
