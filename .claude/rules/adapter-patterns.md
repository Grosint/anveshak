# Adapter Patterns

5 instincts. Social adapter lifecycle, auth, resilience.

## authenticate() Must Catch All Connection Errors

- Every adapter's `authenticate()` converts ALL platform-specific exceptions to `AdapterAuthError`
  Worker startup loop only catches `AdapterAuthError` — anything else crashes entire worker, kills ALL adapters
  Catch: `ConnectionError`, `TimeoutError`, `OSError`, DNS failures, TLS errors, plus platform-specific
  One adapter blocked by ISP → infinite crash-restart loop → YouTube/X never register
  See: `learned/adapter-auth-must-catch-connection-errors.md`

## Circuit Breaker (Redis-Backed, Per-Adapter)

- Three-state: CLOSED → OPEN (N consecutive failures) → HALF_OPEN (after cooldown probe)
  Redis keys per adapter for failure count + opened_at. Survives container restarts.
  Check `allows_call()` before `collect()`. `record_failure()` on exception, `record_success()` on success.
  Social adapters need per-adapter tracking (no per-source rows like scraper)
  See: `learned/adapter-circuit-breaker-redis.md`

## Credential Refresh Before Circuit Break

- On `AdapterAuthError` during `collect()`, attempt `refresh_credentials()` BEFORE recording failure
  Base returns False; adapters w/ refreshable tokens override (Bluesky re-login, Reddit auto-refresh via PRAW)
  Without refresh: expired token → 5 auth errors → circuit opens 15min. With: first error → re-login → immediate recovery
  See: `learned/credential-refresh-before-circuit-break.md`

## Startup Credential Validation

- Validate required env vars BEFORE adapter instantiation, not at first API call
  Missing `BLUESKY_HANDLE` w/ `BLUESKY_ADAPTER_ENABLED=true` silently fails minutes later, buried in logs
  Log missing credentials w/ exact env var names at startup. Skip adapter gracefully — others still work.
  See: `learned/startup-credential-validation.md`

## Webhook Fire-and-Forget

- Secondary notifications (webhook, email) NEVER block primary delivery (WebSocket)
  Webhook function catches all exceptions AND caller wraps in try/except — belt and suspenders
  Short timeout (10s). Returns bool, caller ignores. Delivery marking always runs after.
  Stuck delivery loop = signals stop reaching analysts
  See: `learned/webhook-fire-and-forget.md`
