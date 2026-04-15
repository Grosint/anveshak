---
name: seed-sql-schema-sync
description: seed SQL drifts silently from the actual DB schema — how to verify and fix
type: feedback
---

`scripts/seed_demo.sql` drifts from the actual schema as migrations evolve. The drift is
silent: `psql` silently rolls back the transaction and prints `ROLLBACK` — but the Makefile
still prints "Demo scenario loaded."

**Detection:** run seed and check for `ERROR:` lines or `ROLLBACK` in the output.
If `INSERT 0 0` appears for every table (no rows inserted), the data was already there but
the schema check passed by accident.

**Fix workflow:**
1. Dump actual schema for each table:
   ```bash
   docker compose exec postgres psql -U anveshak -d anveshak -c "\d users" -c "\d topics" ...
   ```
2. Compare column names to the INSERT statements in seed_demo.sql.
3. Common drifts to check:
   - `email` → `username` (if auth model changed)
   - `hashed_password` → `password_hash`
   - `is_active` → `status` (text enum)
   - `url` → `url_or_handle` (sources table)
   - `content_ids[]` removed from narrative_clusters
   - `title`/`body_markdown` → `content_md` (reports table)
   - `time_window_start`/`time_window_end` added (reports, NOT NULL)

**ON CONFLICT column must also match:** `ON CONFLICT (email)` fails if `email` column was
renamed to `username`.

**How to apply:** any time `make seed-demo` runs without errors but data isn't visible in
the app — verify schema alignment before assuming a logic bug.
