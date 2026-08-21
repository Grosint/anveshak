# Startup Credential Validation (Not Per-Call)

## Pattern
Validate required env vars before adapter instantiation. Log missing credentials
with the exact env var names at startup, not at first API call.

## Why
- Missing `BLUESKY_HANDLE` with `BLUESKY_ADAPTER_ENABLED=true` silently fails at
  first `authenticate()` — minutes later, buried in logs
- Startup validation surfaces all missing credentials at once in the first 2 seconds
- Clear `hint` field tells the operator exactly what to set
- Adapter still skipped gracefully (other adapters still work — criteria 3.5)

## Implementation
```python
_REQUIRED_CREDENTIALS = {
    "bluesky": [("bluesky_handle", "BLUESKY_HANDLE"), ("bluesky_password", "BLUESKY_PASSWORD")],
    "reddit":  [("reddit_client_id", "REDDIT_CLIENT_ID"), ("reddit_client_secret", "REDDIT_CLIENT_SECRET")],
}

def _validate_adapter_credentials(adapter_name: str, s) -> list[str]:
    missing = [env for attr, env in _REQUIRED_CREDENTIALS.get(adapter_name, [])
               if getattr(s, attr, None) is None]
    return missing

# In startup():
for enabled, name, factory in adapter_configs:
    if not enabled: continue
    missing = _validate_adapter_credentials(name, settings)
    if missing:
        log.warning("adapter_missing_credentials", adapter=name, missing=missing)
        continue  # skip, don't crash
    candidates.append(factory())
```

## Files
- `services/social/anveshak/social/jobs.py` — implementation
- `tests/unit/test_social_settings_validation.py` — 6 tests
