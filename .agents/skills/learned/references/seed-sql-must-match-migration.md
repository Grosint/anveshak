# Seed SQL Must Match Migration Schema

## Pitfall

After a migration adds NOT NULL columns (e.g., `org_id`), existing seed scripts fail silently or with `NOT NULL violation`. This happened twice in this session:
1. `seed_demo.sql` topics INSERT lacked `org_id` → `make seed-demo` fails
2. `seed_demo.sql` sources INSERT lacked `org_id` → same

The fix requires updating EVERY INSERT in the seed script to include the new column. Easy to miss because:
- The migration has a backfill (`UPDATE ... SET org_id = 'default' WHERE org_id IS NULL`)
- But seed scripts run AFTER migration, on a fresh DB — there's nothing to backfill
- The INSERT hits the NOT NULL constraint directly

## How to apply

After any migration that adds a NOT NULL column:
1. `grep -n "INSERT INTO <table>" scripts/seed_demo*.sql` — find all affected INSERTs
2. Add the new column + value to each INSERT
3. Also add rows to join tables if applicable (e.g., `org_sources`)
4. Test with `make seed-demo` on a fresh DB after migration

This is the same lesson as `learned/seed-sql-schema-sync.md` but specifically for NOT NULL additions.
