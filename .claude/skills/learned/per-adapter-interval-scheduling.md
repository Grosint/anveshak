# Per-Adapter Independent Interval Scheduling

## When to load: any polling service where different components need different poll cadences

> Solved in Phase 3 for X/Twitter adapter (criteria 3.25): X must respect its own
> `x_poll_interval_s` independently of the global `poll_interval_s`.

---

### The problem

A polling service loops and enqueues jobs for multiple adapters. One adapter (X/Twitter)
must poll less frequently than others to control API spend. A single `sleep(poll_interval_s)`
can't express mixed cadences.

### The solution: per-component timestamp tracking

```python
# In main loop state:
last_x_poll_at: datetime | None = None

while True:
    now = datetime.now(UTC)

    # X is due if: never polled, OR enough time has elapsed
    x_due = (
        settings.x_adapter_enabled
        and (
            last_x_poll_at is None
            or (now - last_x_poll_at).total_seconds() >= settings.x_poll_interval_s
        )
    )

    await enqueue_topic_polls(db_pool, arq_pool, include_x=x_due)

    if x_due:
        last_x_poll_at = now

    await asyncio.sleep(settings.poll_interval_s)   # base tick rate
```

Then propagate the gate flag into the ARQ job:

```python
async def poll_social_topic(ctx, topic_id: str, include_x: bool = True) -> dict:
    for adapter in _ADAPTERS.values():
        if adapter.platform == "twitter" and not include_x:
            log.debug("social.x_poll_skipped", reason="x_poll_interval_s not elapsed")
            continue
        # ... normal poll
```

### Key design decisions

1. **Timestamp per adapter, not a counter** — survives restarts cleanly (timer resets, not a problem since adapters re-authenticate on startup anyway).
2. **Gate flag passed as job argument** (`include_x`) — keeps the ARQ job stateless. The job doesn't need to check Redis or DB to know if it should poll X.
3. **Base loop cadence stays fast** — `poll_interval_s` should be ≤ the smallest adapter interval so no adapter misses its window.
4. **Log when skipped** — `social.x_poll_skipped` makes it visible in logs why X isn't polling.

### Generalisation for >2 intervals

```python
@dataclass
class AdapterSchedule:
    interval_s: int
    last_poll_at: datetime | None = None

    def is_due(self, now: datetime) -> bool:
        return (
            self.last_poll_at is None
            or (now - self.last_poll_at).total_seconds() >= self.interval_s
        )

schedules = {
    "telegram": AdapterSchedule(settings.poll_interval_s),
    "reddit":   AdapterSchedule(settings.poll_interval_s),
    "twitter":  AdapterSchedule(settings.x_poll_interval_s),
}

while True:
    now = datetime.now(UTC)
    due = {name for name, sched in schedules.items() if sched.is_due(now)}
    await enqueue_topic_polls(db_pool, arq_pool, adapters_due=due)
    for name in due:
        schedules[name].last_poll_at = now
    await asyncio.sleep(min(s.interval_s for s in schedules.values()))
```

### When to use this pattern

- Multiple components share one polling loop but have different frequency requirements
- You need to audit "why wasn't X polled?" in logs
- One component has cost implications (API billing) that need explicit control

### When NOT to use

- If all adapters share the same interval — just sleep once
- If you need persistent scheduling across restarts — use ARQ cron or a DB-backed schedule
