# Idempotent Cron Insert

## When to load: any cron job that INSERTs rows into a table on every cycle

---

## The Problem

A cron job detects a condition and writes a warning/event row. It runs every N hours.
If the condition persists, the cron inserts a duplicate row every cycle — forever.

**Real example:** `check_source_warnings` runs every 6h. A source whose credibility dropped
below its report snapshot gets a `report_source_warnings` row on the first cycle. On the
second cycle the condition is still true → another row. After a week: 28 duplicate warnings
for the same (report, source) pair. UI shows 28 banners for one event.

This is distinct from the immutable-write-idempotency pattern (which handles replayed single-write
jobs via `WHERE sentinel IS NULL`). This pattern handles **periodic crons that re-evaluate
conditions and must not accumulate duplicates**.

---

## The Fix: Two-layer defence

### Layer 1 — DB constraint (prevents duplicates at database level)

Add a UNIQUE index on the columns that identify "same event":

```python
# In migration
op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_report_source_warnings_pair
    ON report_source_warnings(report_id, source_id)
""")
```

Before creating the index, deduplicate existing rows (keep earliest):
```python
op.execute("""
    DELETE FROM report_source_warnings a
    USING report_source_warnings b
    WHERE a.id > b.id
      AND a.report_id = b.report_id
      AND a.source_id = b.source_id
""")
```

### Layer 2 — SQL ON CONFLICT (silent skip at insert level)

```python
SQL_INSERT_SOURCE_WARNING = """
    INSERT INTO report_source_warnings (
        id, report_id, source_id, source_name, warning_type,
        old_score, new_score, created_at, updated_at, labels
    ) VALUES ($1, $2, $3, $4, 'credibility_downgraded', $5, $6, $7, $7, $8)
    ON CONFLICT (report_id, source_id) DO NOTHING
    --  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    --  Second+ cron cycles for same condition → silent no-op
"""
```

---

## When to use ON CONFLICT DO NOTHING vs DO UPDATE

| Behaviour wanted | Clause |
|---|---|
| Event was detected once — don't log it again | `DO NOTHING` |
| Always update with the latest value (e.g. new_score refreshed) | `DO UPDATE SET new_score = EXCLUDED.new_score, updated_at = NOW()` |
| Re-alert on a new severity level | Use a composite unique key that includes severity, or check and delete-before-insert |

For audit/warning tables where the first occurrence is the meaningful event: `DO NOTHING`.

---

## Test: assert constraint works

```python
def test_sql_has_on_conflict_clause():
    normalised = " ".join(SQL_INSERT_SOURCE_WARNING.split()).upper()
    assert "ON CONFLICT" in normalised
    assert "DO NOTHING" in normalised
```

```python
async def test_cron_does_not_duplicate(pool):
    await insert_source_warning(pool, report_id, source_id, ...)
    await insert_source_warning(pool, report_id, source_id, ...)  # second cycle
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM report_source_warnings WHERE report_id=$1 AND source_id=$2",
        report_id, source_id,
    )
    assert count == 1
```

---

## Checklist for any new cron-insert table

- [ ] Does the table have a UNIQUE index on the natural key for "same event"?
- [ ] Does the INSERT SQL use `ON CONFLICT (...) DO NOTHING` (or `DO UPDATE`)?
- [ ] Does the migration deduplicate existing rows before adding the UNIQUE index?
- [ ] Is there a unit test that asserts `ON CONFLICT` appears in the SQL string?
- [ ] Is there an integration test that runs the cron twice and counts rows?

---

## Implementation reference
`services/api/migrations/versions/004_report_source_warnings_unique.py`
`services/reporter/anveshak/reporter/db/__init__.py` — `SQL_INSERT_SOURCE_WARNING`
`tests/unit/test_source_warning_dedup.py`
