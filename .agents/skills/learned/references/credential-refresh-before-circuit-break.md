# Credential Refresh Before Circuit Break

## Pattern
When `AdapterAuthError` is raised during `collect()`, attempt `refresh_credentials()`
once before recording a circuit breaker failure. Default implementation returns False;
adapters that support re-auth override it.

## Why
- Bluesky tokens expire after ~24h; re-login with handle+password restores access
- Without refresh, expired token → 5 consecutive auth errors → circuit opens for 15min
- With refresh, first auth error triggers re-login → immediate recovery
- Reddit OAuth auto-refreshes via PRAW; X bearer tokens are static (no refresh needed)

## Implementation
```python
# In SourceAdapterBase:
async def refresh_credentials(self) -> bool:
    return False  # default: no refresh possible

# In BlueskyAdapter:
async def refresh_credentials(self) -> bool:
    try:
        await self.authenticate()  # Re-login
        return True
    except AdapterAuthError:
        return False

# In poll_social_topic:
except AdapterAuthError as exc:
    refreshed = await adapter.refresh_credentials()
    if not refreshed and cb:
        await cb.record_failure()
```

## Files
- `services/social/anveshak/social/adapters/base.py` — base method
- `services/social/anveshak/social/adapters/bluesky.py` — override
- `tests/unit/test_social_credential_refresh.py` — 5 tests
