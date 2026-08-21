# Compose Env Var Pre-flight Check

## When to load: modifying Makefile startup targets, adding new compose files, or adding required (no-default) env vars

---

## Pattern: Parse compose files for required vars before startup

Compose vars with `${VAR}` (no `:-` default) silently become empty strings if missing
from `.env`. This causes subtle failures: empty passwords, blank API keys, services
that start but can't authenticate.

**Solution:** `scripts/check_env.sh` extracts `${VAR}` patterns (no default) from the
compose file(s) being used, sources `.env`, and blocks startup if any are missing.

```bash
# Extract ${VAR} (no default) — exclude ${VAR:-...} which have fallbacks
REQUIRED_VARS=$(grep -hoE '\$\{[A-Z_]+\}' $COMPOSE_FILES | sed 's/[${}]//g' | sort -u)
```

**Wiring into Makefile:** The `check_env` define takes compose files as argument:
```makefile
$(call check_env,infra/compose.yml)                          # make up
$(call check_env,infra/compose.yml infra/compose.bridge.yml) # make up-bridge
```

This way `make up-bridge` checks for `DRISHTI_REDPANDA_BOOTSTRAP` (required, no default)
but `make up` doesn't — because you only need it when running the bridge overlay.

## Key insight

Vars with defaults (`${VAR:-false}`) are safe to omit — compose substitutes the default.
Only vars without defaults (`${VAR}`) are truly required and worth blocking on.
Credential vars often use `${VAR:-}` (empty default) which is intentional — the adapter
checks at runtime and logs a warning when disabled.
