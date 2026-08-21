# asyncpg JSONB Codec Must Be Registered on Every Pool

## Problem

asyncpg returns JSONB columns as Python `str` by default, not `dict`.
API service had `set_type_codec("jsonb", decoder=json.loads)` via init callback.
7 other services (analyst, scraper, social, reporter, vision) created pools
WITHOUT the callback — JSONB arrived as strings.

Most code had defensive `json.loads()` or `isinstance(str)` checks. But 2 locations
used `json.loads(row["field"])` inside `try/except TypeError` — after codec fix,
`json.loads(dict)` raises TypeError, except catches it, data silently lost.

## Rule

1. **ONE shared pool factory** — `sdk/anveshak/db.py:create_db_pool()` with codec.
   All services import this. No raw `asyncpg.create_pool()` in service code.

2. **Before enabling codec globally**, grep for bare `json.loads(row[` without
   `isinstance(str)` guard. Pattern that breaks:
   ```python
   try:
       data = json.loads(row["jsonb_col"])  # TypeError after codec
   except (ValueError, TypeError):
       data = {}  # SILENT DATA LOSS
   ```
   Fix to: `json.loads(raw) if isinstance(raw, str) else raw`

3. **Safe patterns** (work before AND after codec):
   - `isinstance(val, str) → json.loads(val)` — safe
   - `json.loads(val) if isinstance(val, str) else val` — safe
   - Bare `json.loads(row["col"])` in try/except — BREAKS after codec

## Where Used

`sdk/anveshak/db.py` — shared pool, imported by all 8 services.
`tests/unit/test_latent_bugs.py` — verifies all pools use codec.
