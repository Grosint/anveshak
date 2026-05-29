# Dual-Layer Isolation — Application + RLS Safety Net

## Pattern

For LEA/defence multi-tenancy, enforce org isolation at TWO layers:
1. **Primary:** Application-level `WHERE org_id = $N` in every query + `verify_topic_access()` on every route
2. **Secondary:** PostgreSQL Row-Level Security as a safety net

RLS policy pattern:
```sql
CREATE POLICY org_isolation ON topics
    USING (
        current_setting('app.current_org', true) = ''  -- super-admin bypass
        OR org_id = current_setting('app.current_org', true)
    );
```

API sets `SET LOCAL app.current_org = '<org_id>'` per request (transaction-scoped, auto-resets with asyncpg pooling). Background services use `anveshak_worker` role with `BYPASSRLS`.

## Why

Application-only filtering means one missed WHERE clause = cross-org data leak. With ~30 SQL queries across 6 services, the probability of a future developer forgetting a filter is high. RLS catches it at the DB level.

The `SET LOCAL` approach is safe with connection pooling because it's transaction-scoped — it auto-resets when the connection returns to the pool. No per-connection state leaks.

## How to apply

- Enable RLS on tables with org_id (not all tables — only root entities)
- Use `current_setting('app.current_org', true)` — the `true` means missing_ok (returns '' if not set)
- Empty string '' bypasses RLS (super-admin / background services / unset context)
- Create a dedicated worker role with BYPASSRLS for background services
- Sanitize org_id input before `SET LOCAL` to prevent SQL injection (regex: `^[a-zA-Z0-9_-]+$`)
