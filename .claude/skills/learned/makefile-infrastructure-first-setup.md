# Makefile Infrastructure-First Setup

## When to load: any task involving Docker Compose startup ordering, `make setup`, or fresh-clone onboarding

> See also: `learned/alembic-migrate-in-container.md` — migrations must run inside the container
> See also: `learned/compose-project-name-consistency.md` — -p flag for consistent naming
> See also: `learned/postgres-volume-password-mismatch.md` — stale volume keeps old password

---

### Problem

When `docker compose up -d` starts all services at once, application services (scraper, social, analyst) query the database on startup. If migrations haven't run yet, they crash with `UndefinedTableError: relation "topics" does not exist` and enter a crash-loop with exponential backoff. A static `sleep N` doesn't help — it's a guess, not a guarantee.

### Pattern: Phased startup with health-gated waits

```makefile
# WRONG — all services start, app services crash before migrations
@$(COMPOSE) up -d --remove-orphans
@sleep 10
@$(COMPOSE) exec -T api alembic upgrade head

# CORRECT — infrastructure first, migrate, then app services
# Step 1: Start only infrastructure
@$(COMPOSE) up -d --remove-orphans postgres redis ollama

# Step 2: Health-poll loop (replaces blind sleep)
@timeout=120; elapsed=0; \
while [ $$elapsed -lt $$timeout ]; do \
    healthy=$$(docker compose ... ps --format json 2>/dev/null | \
        python3 -c "import sys,json; lines=sys.stdin.read().strip().split('\n'); \
        print(sum(1 for l in lines if json.loads(l).get('Health','')=='healthy'))" \
        2>/dev/null || echo 0); \
    if [ "$$healthy" -ge 3 ]; then break; fi; \
    sleep 5; elapsed=$$((elapsed + 5)); \
done

# Step 3: Migrate (DB is guaranteed healthy)
@$(COMPOSE) exec -T api alembic upgrade head

# Step 4: Now start everything
@$(COMPOSE) up -d --remove-orphans
```

### Key rules

1. **Never `sleep N` for health** — always poll. Infrastructure cold-start times vary wildly (10s–90s).
2. **Migrations before app services** — any service that queries DB on startup will crash on empty schema.
3. **Use `--format json`** for machine-parseable health status — text output varies across Docker versions.
4. **Fallback for API container** — if API isn't running yet when you need it for `alembic`, start it explicitly:
   ```makefile
   @$(COMPOSE) exec -T api alembic upgrade head 2>&1 || { \
       $(COMPOSE) up -d api; sleep 10; \
       $(COMPOSE) exec -T api alembic upgrade head; \
   }
   ```

### Makefile `$(call)` pitfall

`$(call warn,...)` expands to `@printf "..."`. The `@` prefix is Make syntax (suppress echo), valid only at the start of a recipe line. Inside a shell `{ ... }` block, `@printf` is interpreted by the shell as a command named `@printf` — which doesn't exist.

```makefile
# WRONG — @printf inside shell block
@$(UV) python scripts/syscheck.py || { \
    $(call warn,System does not meet minimum requirements); \
}
# /bin/sh: @printf: command not found

# CORRECT — use plain printf inside shell blocks
@$(UV) python scripts/syscheck.py || { \
    printf "  $(_WARN) $(_YEL)System does not meet minimum requirements$(_RST)\n"; \
}
```

### Discovered during

Clean-slate Makefile testing (2026-04-18): nuked all Docker images/volumes/cache, ran `make setup` from scratch. Scraper and social crash-looped for 5+ minutes until migrations were manually applied.
