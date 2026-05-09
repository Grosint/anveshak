# Compose Environment Variable Consistency

## When to load: adding any new env var to a service's settings.py

Merged from: `compose-env-var-silent-disable.md`, `docker-run-compose-env-vars.md`

---

## Rule 1: Every settings.py var must be in compose environment block

For every env var a service reads in `settings.py`, there MUST be a corresponding
line in the compose service's `environment:` block. Missing vars silently default
to `false`/`""` with no error — features appear disabled for no visible reason.

```yaml
social:
  environment:
    TELEGRAM_ADAPTER_ENABLED: ${TELEGRAM_ADAPTER_ENABLED:-false}
    X_BEARER_TOKEN: ${X_BEARER_TOKEN:-}
```

## Rule 2: docker run misses compose-defined vars

`docker run --env-file .env` only reads the flat `.env` file. Variables set via
compose `environment:` block (POSTGRES_URL, REDIS_URL, OLLAMA_BASE_URL) are NOT
in `.env`. Running `docker run --env-file .env` alone = service crashes on DB connect.

Fix: pass compose vars explicitly with `-e` flags when running one-off containers.

## Checklist (every new env var)

1. Add to `settings.py` with default
2. Add to `infra/compose.yml` service environment block (or x-*-env anchor)
3. Add to `.env.example` with comment
4. Verify: `docker exec <container> env | grep NEW_VAR`

See also: `learned/compose-env-preflight-check.md` — `scripts/check_env.sh` blocks `make up` if required (no-default) vars are missing from `.env`
See also: `learned/compose-dead-env-var-cleanup.md` — algorithm migrations leave dead env vars in compose; audit after every migration
