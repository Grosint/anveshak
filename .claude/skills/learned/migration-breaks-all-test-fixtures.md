# NOT NULL Migration Breaks All Test Fixtures Silently

## Problem

Migration 007 added `org_id NOT NULL` to topics, sources, content_items, and
credibility_audit_log. The migration backfilled existing production rows, but
test fixtures, inline SQL in integration tests, container test scripts, and
mock rows in unit tests were never updated.

Result: 33+ test failures across 3 layers (unit, integration, e2e), all silent
until someone ran `make test-integration`. Unit tests using mocks passed because
mocks don't hit the DB — but `KeyError: 'org_id'` was caught as a generic
exception and swallowed (scraper inserted 0 items, no error logged).

## Rule

After any migration that adds a NOT NULL column:

1. **conftest.py factory fixtures** — update `make_topic`, `make_source`, `insert_content_item`
2. **Inline SQL in integration tests** — grep `INSERT INTO <table>` across `tests/integration/`
3. **Container test scripts** — `scripts/test_analyst_models.py`, `scripts/test_multilingual_pipeline.py`
4. **Unit test mock rows** — grep `{"id": "topic-1"}` or similar across `tests/unit/`
5. **Service code that builds audit rows** — grep for the table and ensure all INSERT paths include the new column
6. **Seed SQL** — `scripts/seed_demo.sql` etc.

Checklist shortcut: `grep -r 'INSERT INTO <table>' tests/ scripts/ | grep -v org_id`
If any results, those need fixing.

## Why this is worse than it looks

- Unit tests with mocked DB pass fine — column isn't checked
- Integration tests fail but are often skipped in quick CI (`make test-unit`)
- The `KeyError` in service code is caught by generic `except Exception` blocks
  and produces zero output (not a crash, not an error — just no data)
- Scraper test shows `inserted=0` which looks like "no content" not "bug"

## See also

- `seed-sql-must-match-migration.md` — same rule for seed scripts
- `mock-shape-unwrap-mismatch.md` — mock rows must match real DB shape
