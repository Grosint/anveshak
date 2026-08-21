# Pattern: Cross-Service Event Delivery via DB Polling

## When to load: any time one service writes events and another service must push them to clients

---

## Problem

Two services share a DB but cannot call each other directly:
- **Writer** (analyst): runs background jobs, writes events to DB, has no WebSocket connections
- **Pusher** (api): owns WebSocket sessions, cannot run the writer's logic

Naive approaches fail:
- Writer calls pusher's HTTP endpoint → tight coupling, adds latency, breaks standalone rule
- Writer imports pusher's in-memory session dict → import cycle, impossible across processes

## Solution: Delivery-flag column + polling loop

### Step 1 — Add `delivered_at TIMESTAMPTZ` to the event table

```sql
ALTER TABLE signals ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
CREATE INDEX idx_signals_undelivered ON signals(created_at ASC)
WHERE delivered_at IS NULL;   -- partial index: only undelivered rows scanned
```

### Step 2 — Writer ignores delivery entirely

Writer inserts events with `delivered_at = NULL`. Done.

### Step 3 — Pusher owns a polling loop

```python
SQL_UNDELIVERED = """
    SELECT * FROM events
    WHERE delivered_at IS NULL
    ORDER BY created_at ASC
    LIMIT 50
"""

SQL_MARK_DELIVERED = "UPDATE events SET delivered_at = $1 WHERE id = $2"

async def delivery_loop(pool: asyncpg.Pool, broadcast) -> None:
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_UNDELIVERED)
            for row in rows:
                try:
                    await broadcast(build_payload(row))
                except Exception:
                    pass  # no sessions connected — still mark delivered
                await conn.execute(SQL_MARK_DELIVERED, datetime.now(UTC), row["id"])
        await asyncio.sleep(POLL_INTERVAL_S)
```

### Step 4 — Wire into FastAPI lifespan

```python
@asynccontextmanager
async def lifespan(app):
    pool = await create_pool()
    task = asyncio.create_task(delivery_loop(pool, broadcast_fn))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await pool.close()
```

## Why `delivered_at` is set even when no sessions are connected

Client reconnect gets missed events via the replay endpoint (`?since=` timestamp).
Setting `delivered_at` on every event — even with zero sessions — prevents infinite
re-processing on restart.  Clients that miss it receive it on reconnect via replay.

## Poll interval sizing

- ≤5s poll → ≤10s end-to-end latency (poll + processing).
- Use `SIGNAL_DELIVERY_POLL_S = 5` for interactive analyst alerts.
- For lower-priority events (audit logs, reports), 30–60s is fine.

## Pitfall: don't use `SELECT FOR UPDATE SKIP LOCKED`

Tempting for concurrent workers, but the API only runs one delivery loop.
`delivered_at IS NULL` partial index is faster and simpler.
