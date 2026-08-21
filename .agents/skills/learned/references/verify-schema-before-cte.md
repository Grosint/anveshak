# Verify Schema Before Writing CTE Queries

## Pattern

Before writing SQL (especially CTEs joining multiple tables), verify actual column names against the live database. Don't assume columns exist from documentation or CLAUDE.md.

## Why

CTE referencing `t.description` on `topics` table caused `column does not exist` error on all 51 cluster regenerations. Topics table has `name` and `keywords` — no `description` column. Unit tests passed (mocked DB). Only failed at runtime.

## Verification

```bash
# Always do this before writing SQL referencing a table
docker compose -p anveshak exec postgres psql -U anveshak -c "\d topics"
```

## Rule

1. Check `\d tablename` before writing any new SQL constant
2. CTE UNION ALL queries are especially fragile — one bad column name fails the entire query
3. Unit tests with mocked DB won't catch missing columns — integration tests required
4. Migration squashing (001_initial_schema) means column history is hidden

## See also

- `rules/database.md` — SQL correctness checklist
- `learned/migration-breaks-all-test-fixtures.md` — schema changes break test fixtures
