# Adapter Lifecycle Management

## When to load: any task involving creating, modifying, or debugging a social/scraper adapter

Consolidated from 6 learned instincts covering the full adapter lifecycle:
startup validation → authentication → quota enforcement → polling → failure handling → recovery.

> See also: `.claude/skills/learned/adapter-circuit-breaker-redis.md` — Redis-backed CLOSED/OPEN/HALF_OPEN per adapter
> See also: `.claude/skills/learned/credential-refresh-before-circuit-break.md` — try refresh_credentials() before circuit breaking
> See also: `.claude/skills/learned/startup-credential-validation.md` — validate env vars at startup, not at first API call
> See also: `.claude/skills/learned/per-adapter-interval-scheduling.md` — independent poll cadence per adapter
> See also: `.claude/skills/learned/redis-atomic-budget-guard.md` — atomic INCR for X monthly / Bluesky daily caps
> See also: `.claude/skills/learned/robots-txt-cache-permissive-default.md` — robots.txt enforcement with 1h cache
> See also: `.claude/skills/learned/optional-dep-lazy-import-two-level-log.md` — graceful degradation for optional deps
> See also: `source-adapter-sdk.md` — adapter contract, RawItem, conformance suite

---

### Phase 1: Startup Validation

```python
# Validate BEFORE instantiation — clear logs, no crash
_REQUIRED_CREDENTIALS = {
    "bluesky": [("bluesky_handle", "BLUESKY_HANDLE"), ("bluesky_password", "BLUESKY_PASSWORD")],
}

for enabled, name, factory in adapter_configs:
    if not enabled: continue
    missing = _validate_adapter_credentials(name, settings)
    if missing:
        log.warning("adapter_missing_credentials", adapter=name, missing=missing)
        continue
    candidates.append(factory())
```

### Phase 2: Authentication + Circuit Breaker Init

```python
for adapter in candidates:
    try:
        await adapter.authenticate()
        _ADAPTERS[adapter.adapter_id] = adapter
        _CIRCUIT_BREAKERS[adapter.adapter_id] = AdapterCircuitBreaker(
            redis, adapter.adapter_id,
            threshold=settings.social_circuit_breaker_threshold,
            cooldown_s=settings.social_circuit_breaker_cooldown_s,
        )
    except AdapterAuthError:
        log.error("auth_failed", adapter_id=adapter.adapter_id)
        # Don't crash — other adapters still work
```

### Phase 3: Quota Enforcement (before each API call)

```python
# Bluesky: 7200 calls/day (daily key, auto-reset)
# X: $200/month cap (monthly key, auto-reset)
if self._quota_guard and not await self._quota_guard.check_and_increment():
    log.warning("quota_exhausted")
    return  # hard stop
```

Pattern: atomic Redis INCR → check cap → decrement on reject. Key includes date
(`YYYY-MM-DD` for daily, `YYYY-MM` for monthly) so reset is automatic.

### Phase 4: Polling with Error Hierarchy

```python
for adapter_id, adapter in _ADAPTERS.items():
    cb = _CIRCUIT_BREAKERS.get(adapter_id)
    if cb and not await cb.allows_call():
        continue  # OPEN → skip

    try:
        async for raw_item in adapter.collect(...):
            await ingest_raw_item(raw_item, ...)
    except AdapterAuthError:
        refreshed = await adapter.refresh_credentials()
        if not refreshed and cb: await cb.record_failure()
    except AdapterRateLimitError:
        social_rate_limit_total.labels(platform=platform).inc()
        if cb: await cb.record_failure()
    except Exception:
        if cb: await cb.record_failure()
    else:
        if cb: await cb.record_success()
```

### Phase 5: Circuit Breaker States

```
CLOSED  → normal operation, failures tracked via Redis INCR
OPEN    → consecutive failures >= threshold, all calls blocked
HALF_OPEN → cooldown expired, one probe call allowed
```

Keys: `anveshak:social:failures:{adapter_id}` (count), `anveshak:social:opened_at:{adapter_id}` (timestamp).
Success in any state → DELETE both keys → CLOSED.

### Phase 6: Credential Refresh

```python
# Default in SourceAdapterBase:
async def refresh_credentials(self) -> bool:
    return False  # override in subclasses

# Bluesky: re-login with handle+password
# Reddit: PRAW auto-refreshes OAuth
# Telegram: session file persists
# X: bearer token is static
```

### Scraper-Specific: robots.txt

```python
# Cache per domain (1h TTL), permissive default (allow on fetch failure)
# Skip .onion URLs entirely
if not await check_robots_allowed(url):
    return  # respect robots.txt
```
