# Adapter Circuit Breaker (Redis-backed, per-adapter)

## Pattern
Three-state circuit breaker: CLOSED → OPEN (after N consecutive failures) → HALF_OPEN
(after cooldown). Redis keys per adapter for failure count + opened_at timestamp.

## Why
- SQL-backed circuit breaker (`circuit-breaker-sql-filter.md`) works for scraper sources
  but social adapters don't have per-source rows — they need per-adapter tracking
- Redis survives container restarts; in-memory counters don't
- HALF_OPEN probe after cooldown prevents permanent lockout
- `time.monotonic()` for cooldown avoids clock-skew issues

## Implementation
```python
class AdapterCircuitBreaker:
    _failure_key = f"anveshak:social:failures:{adapter_id}"
    _opened_key = f"anveshak:social:opened_at:{adapter_id}"

    async def record_failure():   # INCR, check threshold, set opened_at
    async def record_success():   # DELETE both keys
    async def get_state():        # CLOSED | OPEN | HALF_OPEN
    async def allows_call():      # False only when OPEN
```

## How to apply
Create one `AdapterCircuitBreaker` per adapter at startup. Check `allows_call()`
before `collect()`. Call `record_failure()` on exception, `record_success()` on
successful collect. Auth errors get `refresh_credentials()` attempt first.

## Files
- `services/social/anveshak/social/circuit_breaker.py` — implementation
- `services/social/anveshak/social/jobs.py` — wiring
- `tests/unit/test_social_circuit_breaker.py` — 9 tests
