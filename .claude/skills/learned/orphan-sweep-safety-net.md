# Orphan Sweep Safety Net

## When to load: any task involving distributed insert → enqueue patterns

---

## Problem

When a service inserts a DB row then enqueues an ARQ job in a separate call,
the enqueue can silently fail (Redis timeout, brief downtime, exception swallowed).
The row exists in the DB but no job processes it — an **orphan**.

```python
# scraper inserts content, then enqueues analysis
content_id = await conn.fetchval(SQL_INSERT_CONTENT, ...)  # succeeds
await redis.enqueue_job("analyse_content", content_id)      # can fail silently
```

No retry mechanism exists for the enqueue — the content sits forever with `embedding IS NULL`.

---

## Pattern: Periodic Orphan Sweep

A lightweight scheduler loop that finds orphaned rows and re-enqueues them:

```python
SQL_ORPHANED_CONTENT = """
    SELECT id FROM content_items
    WHERE embedding IS NULL
      AND created_at > NOW() - INTERVAL '1 hour'
    ORDER BY captured_at ASC
    LIMIT 100
"""

async def orphan_sweep(pool: asyncpg.Pool, redis) -> None:
    while True:
        await asyncio.sleep(300)  # every 5 min
        rows = await conn.fetch(SQL_ORPHANED_CONTENT)
        if rows:
            log.info("orphan_sweep.found", pending=len(rows))
            for row in rows:
                await redis.enqueue_job(
                    "analyse_content", row["id"], _queue_name="arq:analyst"
                )
```

### Design decisions

| Decision | Value | Rationale |
|---|---|---|
| Time window | `< 1 hour` | Avoids re-enqueueing ancient items; catches recent failures |
| Interval | 300s (5 min) | Fast enough to recover; slow enough to not spam DB |
| Batch limit | 100 | Prevents query/enqueue overload |
| Idempotency | Guaranteed | `analyse_content` is idempotent — re-enqueue is safe |
| False positives | None | Items being processed have `embedding IS NULL` only briefly |

### Why not use a transaction?

```python
# Can't wrap insert + enqueue in one transaction because Redis is not transactional
async with conn.transaction():
    await conn.execute(SQL_INSERT, ...)       # DB transaction
    await redis.enqueue_job(...)              # NOT part of DB transaction
```

The enqueue is outside the DB transaction boundary. If Redis fails, the DB row commits
but the job is lost. The orphan sweep is the only reliable recovery mechanism.

---

## Where it runs

The orphan sweep runs in the **scheduler** (not the worker) because:
1. It's a lightweight SQL query + Redis enqueue — no ML models needed
2. It should run even if all workers are busy or down
3. Single instance avoids duplicate re-enqueues from multiple workers

---

## Generalisation

This pattern applies anywhere you have `INSERT row → enqueue job`:
- Scraper inserts content → enqueues `analyse_content`
- Social adapter inserts content → enqueues `analyse_content`
- Analyst clusters → enqueues `generate_cluster_label`
- Reporter creates report shell → enqueues `generate_report`

Each insert-then-enqueue pair should have a corresponding sweep query:
```sql
-- Generic orphan detection
SELECT id FROM {table}
WHERE {completion_column} IS NULL
  AND created_at > NOW() - INTERVAL '{window}'
```
