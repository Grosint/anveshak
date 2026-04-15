# Immutable Write with Idempotency Guard

## When to load: any table where a row is written once and must never be overwritten

---

## The Problem

CLAUDE.md rule 4: "Reports are immutable — once `generated_at` is set, it is NEVER updated."
The same ARQ job can be replayed (ARQ retry, duplicate enqueue, infrastructure restart).
Without a guard, a replay overwrites the first valid write — corrupting the evidence chain.

---

## The Pattern

### DB: nullable sentinel column on the table

```sql
-- In migration — generated_at is nullable, set ONCE
CREATE TABLE reports (
    id           TEXT        NOT NULL PRIMARY KEY,
    -- ... other columns ...
    generated_at TIMESTAMPTZ,         -- NULL until generated. SET ONCE. NEVER UPDATED.
    source_snapshot JSONB   NOT NULL DEFAULT '{}'::jsonb
);
```

### SQL: UPDATE with idempotency guard

```python
SQL_SET_REPORT_GENERATED = """
    UPDATE reports
    SET content_md         = $2,
        confidence_score   = $3,
        geojson            = $4,
        source_snapshot    = $5,
        content_item_count = $6,
        generated_at       = $7,
        updated_at         = $7
    WHERE id = $1
      AND generated_at IS NULL   -- THE GUARD: no-op if already written
"""
```

### Python: check return value to detect replay

```python
async def set_report_generated(pool, report_id, ...) -> bool:
    result = await conn.execute(SQL_SET_REPORT_GENERATED, report_id, ...)
    updated = int(result.split()[-1])   # asyncpg returns "UPDATE <n>"
    return updated > 0                  # False = already written, job was a replay
```

### ARQ job: exit cleanly on replay

```python
async def generate_report(ctx: dict, report_id: str) -> None:
    # ... RAG + LLM ...
    stored = await db.set_report_generated(pool, report_id, ...)
    if not stored:
        log.info("reporter.generate_report.already_generated", report_id=report_id)
        return   # No error — this is expected behaviour on replay
```

---

## Test coverage required

```python
def test_idempotency_second_call_is_noop():
    """Second generate_report() call on same ID must be a no-op."""
    # Mock set_report_generated to return False (already written)
    # Assert: job exits without re-writing, no error raised
```

---

## Applies to any sentinel-column immutability

Same pattern works for:
- `published_at` on news items (once published, never re-published)
- `sent_at` on notifications (once sent, never re-sent)
- `closed_at` on incidents (once closed, remain closed)

Replace `generated_at` with the appropriate sentinel column.

---

## Implementation reference
`services/reporter/src/anveshak/reporter/db.py` — `SQL_SET_REPORT_GENERATED` and `set_report_generated()`
`tests/unit/test_reporter_immutability.py`
