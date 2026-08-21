# Redis Atomic Budget Guard

## When to load: any feature with a hard spending cap or quota that must never be silently exceeded

> Solved in Phase 3 for X/Twitter API spend enforcement (criteria 3.22–3.24).

---

### The problem

X API charges per read. If multiple ARQ workers call the API concurrently, a naive
`if count < cap: count += 1; call_api()` check has a race condition — two workers
can both pass the check simultaneously and both increment, overshooting the cap.

### The solution: Redis INCR is atomic

```python
async def check_and_increment(self) -> bool:
    key = f"anveshak:x:monthly_reads:{datetime.now(UTC).strftime('%Y-%m')}"

    # INCR is atomic — no race condition possible
    new_count = await self._redis.incr(key)

    if new_count == 1:
        # First read this month — set TTL so key auto-expires (no explicit reset needed)
        ttl = _seconds_until_month_end()
        await self._redis.expire(key, ttl)

    if new_count > self._cap:
        await self._redis.decr(key)   # undo — don't inflate the counter
        log.warning("spend_guard.cap_reached", count=new_count - 1, cap=self._cap)
        return False

    return True
```

### Key design decisions

1. **INCR then check**, never check then INCR — eliminates TOCTOU race.
2. **Decrement on block** — blocked calls don't inflate the counter, so `current_count()` stays accurate for monitoring.
3. **Month-keyed key with TTL** — `{prefix}:{YYYY-MM}` resets automatically at month boundary. No cron job, no explicit reset logic. New month = new key.
4. **TTL set only on first write** — `if new_count == 1` avoids re-setting TTL on every call (which would extend it incorrectly).
5. **Hard stop on False** — callers must check return value and not make the API call if False.

### Generalised template

```python
class ResourceGuard:
    """Atomic Redis quota guard. Works for any rate-limited or budgeted resource."""

    def __init__(self, redis, cap: int, key_prefix: str, ttl_seconds: int):
        self._redis = redis
        self._cap = cap
        self._key_prefix = key_prefix
        self._ttl = ttl_seconds

    def _key(self) -> str:
        return f"{self._key_prefix}:{datetime.now(UTC).strftime('%Y-%m-%dT%H')}"  # per-hour variant

    async def acquire(self) -> bool:
        new = await self._redis.incr(self._key())
        if new == 1:
            await self._redis.expire(self._key(), self._ttl)
        if new > self._cap:
            await self._redis.decr(self._key())
            return False
        return True
```

### Pitfall: Do NOT use GET → compare → SET

```python
# WRONG — race condition
count = int(await redis.get(key) or 0)
if count < cap:
    await redis.set(key, count + 1)   # two workers can both pass the check
    return True
```

### Tests to always write

- Under cap: `incr returns 1` → True, TTL set once
- At cap: `incr returns cap` → True (still permitted)
- Over cap: `incr returns cap+1` → False + decr called
- New month key is independent counter
- `current_count()` does not call incr
