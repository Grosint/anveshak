# Code References Column That Migration Never Created

## Problem

`SQL_ORPHANED_CONTENT` in scheduler.py referenced `orphan_enqueued_at` column.
Column never existed in any migration. Orphan sweep crashed every 5 minutes
with `UndefinedColumnError` — the safety net for missed enqueue jobs was
completely non-functional for the entire deployment lifetime.

Bug was invisible because:
1. Exception caught by generic `except Exception` in sweep loop
2. Logged as warning, not crash — service stayed "healthy"
3. No integration test ran the actual SQL against real DB
4. Unit tests mocked the DB, never executed the query

## Rule

After writing SQL that references a column:
1. `grep -r 'column_name' services/api/migrations/` — verify column in migration
2. `docker exec postgres psql -d anveshak -c "\d table_name"` — verify column in live DB
3. Add integration test that executes the EXACT SQL query against test DB

## Detection Pattern

Contract test that catches this:
```python
def test_orphan_query_executes_without_error(db_pool):
    """Execute the exact SQL_ORPHANED_CONTENT query against real DB."""
    async with db_pool.acquire() as conn:
        # This will crash with UndefinedColumnError if column missing
        rows = await conn.fetch(SQL_ORPHANED_CONTENT)
```

If this test existed, the bug would have been caught immediately.

## Broader Lesson

**Run your SQL against a real database in tests.** Mocked DB tests pass when
columns don't exist, when types are wrong, when constraints are missing.
The only way to catch schema drift is to hit the actual schema.
