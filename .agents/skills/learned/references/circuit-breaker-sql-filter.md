# Circuit Breaker via SQL Filter

## When to load: adding health-based source skipping to any polling/crawling loop

---

## Pattern

Skip unhealthy sources at the SQL level instead of checking in application code. Track state transitions with Prometheus counters.

```python
# In the job query — filter out downed sources
SQL_GET_SOURCES = """
    SELECT s.id, s.url_or_handle, s.health_status
    FROM sources s
    WHERE s.is_active = TRUE
      AND s.health_status != 'down'   -- circuit breaker: skip downed sources
"""

# In the health check loop — detect transitions
prev_status = source["health_status"]
new_status = "healthy" if check_passed else "down"

if prev_status == "down" and new_status == "healthy":
    scraper_circuit_breaker_total.labels(event="recovered").inc()
    log.info("circuit_breaker_recovered", source_id=source["id"])
elif new_status == "down" and prev_status != "down":
    scraper_circuit_breaker_total.labels(event="tripped").inc()
    log.warning("circuit_breaker_tripped", source_id=source["id"])
```

**Why:** No retry storms against dead sources. Recovery is automatic — the daily health check flips status back. Zero application-level blocking/waiting logic. Prometheus tracks trip/recovery events for alerting.

**Where this lives:** SQL query in `jobs.py`, transition logic in `health.py`, metrics in `metrics.py`.

---

## Pitfall: don't use in-memory circuit breakers

In-memory state (like `circuitbreaker` library) resets on container restart. Database-backed health_status survives restarts and is visible to all workers.
