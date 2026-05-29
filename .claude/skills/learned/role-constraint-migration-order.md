# Role Constraint Must Be Updated Before New Roles

## Pitfall

Adding a new role (`super-admin`) to the users table fails if a CHECK constraint (`chk_users_role`) only allows the old set (`admin`, `analyst`, `viewer`). The INSERT gets `ERROR: new row violates check constraint`.

This was missed during migration development because:
1. Migration 007 added `org_id` columns but didn't update the role constraint
2. The super-admin user seed failed at runtime
3. Had to manually `ALTER TABLE users DROP CONSTRAINT` + re-add

## How to apply

When adding a new role to the system:
1. Update the CHECK constraint in the SAME migration that introduces the role
2. Put the constraint change BEFORE any INSERT that uses the new role
3. Use `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT` pattern (idempotent)

```sql
-- In the migration, BEFORE creating super-admin users:
ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_role;
ALTER TABLE users ADD CONSTRAINT chk_users_role
    CHECK (role IN ('super-admin', 'admin', 'analyst', 'viewer'));
```
