# Compose Environment Variable Silent Disable

## When this applies
Adding a new feature flag or credential env var to a service's `settings.py`.

## The pitfall
`.env` can have `TELEGRAM_ADAPTER_ENABLED=true` but if the compose service
environment block doesn't forward it, the container never sees it. The setting
silently defaults to `false` — no error, no warning, feature just doesn't work.

**How we lost time:** Telegram and X adapters were silently disabled for the
entire dev cycle. Auth credentials were in `.env` but the boolean enable flags
and X bearer token were never in compose's `environment:` block. The old
`TWITTER_BEARER_TOKEN` naming was also wrong — code expected `X_BEARER_TOKEN`.

## The fix pattern
For every env var a service reads in `settings.py`, there MUST be a
corresponding line in compose's `environment:` block:

```yaml
social:
  environment:
    TELEGRAM_ADAPTER_ENABLED: ${TELEGRAM_ADAPTER_ENABLED:-false}
    X_ADAPTER_ENABLED: ${X_ADAPTER_ENABLED:-false}
    X_BEARER_TOKEN: ${X_BEARER_TOKEN:-}
```

## Verification
```bash
# Check what env vars a service reads:
grep -E '^\s+\w+:' services/social/anveshak/social/settings.py

# Check what compose forwards:
grep -A 50 'social:' infra/compose.yml | grep -E '^\s+[A-Z_]+:'

# Verify inside container:
docker exec anveshak-social-1 env | grep TELEGRAM_ADAPTER
```

## Checklist (every new env var)
1. Add to `settings.py` with default
2. Add to `infra/compose.yml` service environment block
3. Add to `.env.example` with comment
4. Verify: `docker exec <container> env | grep NEW_VAR`
