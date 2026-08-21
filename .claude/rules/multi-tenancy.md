# Multi-Tenancy

5 instincts. All org isolation + access control.

## org_id Placement — Root Tables Only

`org_id` on root entities only: users, topics, sources, content_items, credibility_audit_log.
Children (signals, clusters, reports, entities, media_assets, vision_results) inherit via `topic_id` FK — no org_id needed.

Exception: tables w/ no topic_id path (credibility_audit_log) need direct org_id.
Exception: tables accessible by direct UUID (content_items) need org_id for defense-in-depth.
See: `.claude/skills/learned/org-id-root-tables-only.md`

## Dual-Layer Isolation

Primary: `verify_topic_access()` / `verify_source_access()` on every route.
Secondary: PostgreSQL Row-Level Security as safety net.

RLS pattern: `USING (current_setting('app.current_org', true) = '' OR org_id = current_setting(...))`.
API sets `SET LOCAL app.current_org` per request (transaction-scoped, safe w/ pooling).
Background services use `anveshak_worker` role w/ `BYPASSRLS`.
See: `.claude/skills/learned/dual-layer-rls-safety-net.md`

## Source Visibility — Global Sources, Org-Scoped Access

Sources = global entities (RSS feed same feed). Don't duplicate per org.
`org_sources` join table for visibility. `SQL_LIST_SOURCES` JOINs through it.
Org creates source → auto-link in `org_sources`.
See: `.claude/skills/learned/global-sources-org-visibility.md`

## Role Constraints and Migrations

Adding new role (e.g., `super-admin`) → update CHECK constraint in SAME migration, BEFORE any INSERT using new role. `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT` for idempotency.
See: `.claude/skills/learned/role-constraint-migration-order.md`

## Seed Scripts Must Match Schema

Migration adds NOT NULL `org_id` → update ALL seed SQL INSERTs w/ column. Add rows to join tables (`org_sources`). Seeds run on fresh DBs — nothing to backfill.
See: `.claude/skills/learned/seed-sql-must-match-migration.md`

## Cross-Org Leak Prevention

Every cross-topic query (convergence, similarity) MUST filter `AND t1.org_id = t2.org_id`.
WebSocket signal broadcast filters by session org_id.
Export endpoints verify topic ownership before executing.
SQL param count must match all callers after adding org_id columns.
See: `.claude/skills/learned/sql-param-count-caller-mismatch.md`

## Cross-Topic Aggregate Endpoints

Aggregate endpoints (analytics dashboard, global stats) have NO single resource to verify.
org_id must be baked into EVERY SQL sub-query — missing one leaks cross-org data.
Tables without org_id (signals, reports) → JOIN through topics.org_id.
Make org_id keyword-only param on repository function to prevent forgetting.
Test: assert "org_id" in every SQL constant + assert org_id in every DB call args.
See: `.claude/skills/learned/cross-topic-aggregate-org-scoping.md`