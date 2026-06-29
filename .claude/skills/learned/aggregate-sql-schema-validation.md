# Verify Column Names Against Live Schema Before Writing Aggregate SQL

## Problem

Multi-table aggregate queries reference columns across 3-8 tables. Column name
assumptions are wrong more often than expected — `is_active` vs `status = 'active'`,
`platform` on content_items vs sources, `generated_at` vs `created_at`.

Unit tests with mocked DB pass fine. Error only surfaces at runtime (500) after
container rebuild + deploy. Wasted 10 minutes per wrong column.

## Pattern

Before writing any SQL that touches 2+ tables, run `\d` for each:

```bash
# From project root:
docker compose --env-file .env -p anveshak -f infra/compose.yml exec -T postgres \
  psql -U anveshak -d anveshak -c "\d content_items"

# Or check specific columns:
docker compose ... exec -T postgres psql -U anveshak -d anveshak -c \
  "SELECT column_name FROM information_schema.columns
   WHERE table_name IN ('content_items','topics','signals','sources')
     AND column_name IN ('org_id','is_active','status','platform')
   ORDER BY table_name, column_name;"
```

## Common traps in this codebase

| Expected | Actual | Table |
|----------|--------|-------|
| `is_active` | `status = 'active'` | topics |
| `platform` | via JOIN sources | content_items |
| `generated_at` | can be NULL (pending) | reports |
| `description` | may not exist | signals (check first) |

## When to apply

- Writing new SQL constants that JOIN 2+ tables
- Writing aggregate queries (GROUP BY, COUNT, SUM across tables)
- Copying SQL patterns from one table context to another
- After migrations that rename/add columns

## When NOT needed

- Single-table queries on well-known tables
- Modifying existing SQL that already works
