# Adapter authenticate() Must Catch ConnectionError

## Problem
Telegram adapter's `authenticate()` called `self._client.connect()` which raised
`ConnectionError` on network failure (ISP blocking Telegram servers). The worker
startup loop in `jobs.py` only caught `AdapterAuthError` — `ConnectionError`
crashed the entire worker, preventing ALL other adapters from registering.

## How it happened
```python
# jobs.py startup:
for adapter in candidates:
    try:
        await adapter.authenticate()  # Telegram raises ConnectionError
    except AdapterAuthError:          # Only catches this!
        log.error(...)                # ConnectionError escapes → crash
```

Worker restarted in infinite loop — Telegram blocked by ISP → crash → restart →
crash. YouTube and X adapters never got a chance to register.

## Fix
Catch `ConnectionError`, `TimeoutError`, `OSError` in the adapter's
`authenticate()` and convert to `AdapterAuthError`:
```python
except (ConnectionError, TimeoutError, OSError) as exc:
    raise AdapterAuthError(
        f"Telegram connection failed — check network/firewall: {exc}"
    ) from exc
```

## Prevention
Every adapter's `authenticate()` must convert ALL platform-specific exceptions
to `AdapterAuthError`. The startup loop relies on this contract. If any
exception escapes, it kills the entire worker — not just that adapter.

Checklist for new adapters:
- API client connection errors → `AdapterAuthError`
- DNS resolution failures → `AdapterAuthError`
- TLS/SSL errors → `AdapterAuthError`
- Auth token validation errors → `AdapterAuthError`
