# SQL Ambiguous Column in JOINed Queries

## Problem
`content_items` and `sources` both have a `labels` JSONB column. Any SQL
that JOINs these tables and references bare `labels` gets:
```
asyncpg.exceptions.AmbiguousColumnError: column reference "labels" is ambiguous
```

## How it bit us
Three separate SQL constants failed with this error in one session:
- `SQL_TOP_AUTHORS` — `labels->>'author_handle'` without `ci.` prefix
- `SQL_AUTHOR_POST_COUNTS` — same issue
- `SQL_FORWARD_NETWORK` — `replace_all` added `ci.` to a query with no alias

## Fix
Always use table alias prefix when querying JSONB in JOINed queries:
```sql
-- BAD:  labels->>'author_handle'
-- GOOD: ci.labels->>'author_handle'
```

## Prevention
When writing SQL that JOINs `content_items` with `sources`:
1. Always alias both tables (`ci`, `s`)
2. Prefix EVERY `labels` reference with the alias
3. Check WHERE, GROUP BY, ORDER BY, HAVING — not just SELECT
