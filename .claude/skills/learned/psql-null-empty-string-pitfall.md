# psql NULL Returns Empty String in Script Output

## Problem

Scripts that shell out to `psql` with `-A -F "\t"` (tab-separated, no alignment)
get empty string `''` for NULL columns, not Python `None`. Code like:

```python
# WRONG — '' is not None, so float('') crashes with ValueError
threshold = float(row["col"]) if row.get("col") is not None else default
```

This is invisible during development because the column usually has values.
It only crashes when a row has a genuine NULL — e.g., a newly added column
that hasn't been populated yet.

## Fix

Use truthiness check instead of `is not None`:

```python
# CORRECT — '' is falsy, None is falsy, both fall through to default
raw = row.get("col")
threshold = float(raw) if raw else default
```

Or explicitly check for empty string:

```python
raw = row.get("col")
threshold = float(raw) if raw not in (None, '') else default
```

## When This Applies

Any Python script that reads psql output as text (subprocess, not asyncpg).
asyncpg returns proper Python None for NULL — this pitfall is psql-specific.

Files affected in Anveshak: `scripts/pipeline_health.py`, any future scripts
using `_query()` / `_query_val()` helpers.
