# Multi-Tenancy

Consolidated from 5 learned instincts. These apply to all org isolation and access control code.

## org_id Placement — Root Tables Only

Add `org_id` to root entities only: users, topics, sources, content_items, credibility_audit_log.
Child entities (signals, clusters, reports, entities, media_assets, vision_results) inherit
org scope through `topic_id` FK — no org_id column needed.

Exception: tables with no topic_id path (credibility_audit_log) need direct org_id.
Exception: tables accessible by direct UUID (content_items) need org_id for defense-in-depth.
See: `learned/org-id-root-tables-only.md`

## Dual-Layer Isolation

Primary: application-level `verify_topic_access()` / `verify_source_access()` on every route.
Secondary: PostgreSQL Row-Level Security as a safety net.

RLS pattern: `USING (current_setting('app.current_org', true) = '' OR org_id = current_setting(...))`.
API sets `SET LOCAL app.current_org` per request (transaction-scoped, safe with pooling).
Background services use `anveshak_worker` role with `BYPASSRLS`.
See: `learned/dual-layer-rls-safety-net.md`

## Source Visibility — Global Sources, Org-Scoped Access

Sources are global entities (an RSS feed is the same feed). Don't duplicate per org.
Use `org_sources` join table for visibility. `SQL_LIST_SOURCES` JOINs through it.
When an org creates a source, auto-link in `org_sources`.
See: `learned/global-sources-org-visibility.md`

## Role Constraints and Migrations

When adding a new role (e.g., `super-admin`), update the CHECK constraint in the
SAME migration, BEFORE any INSERT that uses the new role. Use `DROP CONSTRAINT IF EXISTS`
+ `ADD CONSTRAINT` pattern for idempotency.
See: `learned/role-constraint-migration-order.md`

## Seed Scripts Must Match Schema

After any migration that adds NOT NULL `org_id` columns, update ALL seed SQL INSERTs
to include the column. Also add rows to join tables (`org_sources`). Seed scripts run
on fresh DBs — there's nothing to backfill.
See: `learned/seed-sql-must-match-migration.md`

## Cross-Org Leak Prevention

Every cross-topic query (convergence, similarity) MUST filter `AND t1.org_id = t2.org_id`.
WebSocket signal broadcast must filter by session's org_id.
Export endpoints must verify topic ownership before executing.
SQL parameter count must match all callers after adding org_id columns.
See: `learned/sql-param-count-caller-mismatch.md`
