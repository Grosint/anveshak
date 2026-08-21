# org_id on Root Tables Only — Multi-Tenancy Column Placement

## Pattern

Add `org_id` to root entities only (users, topics, sources, content_items, credibility_audit_log). Child entities (signals, clusters, reports, extracted_entities, media_assets, vision_results) inherit org scope through `topic_id` FK — no org_id column needed.

## Why

The architect review initially suggested adding org_id to all 20 tables. But child entities are always queried through topic-scoped paths (`WHERE topic_id = $1`). Adding org_id to them would mean:
- 90+ SQL queries to update instead of ~20
- Duplicate data (org_id stored on parent AND child)
- Risk of inconsistency (child has different org_id than parent)

The exception is `content_items` — it CAN be accessed directly by UUID (`GET /content/{id}`), so it needs org_id for defense-in-depth. `credibility_audit_log` has no topic_id path (it belongs to source, not topic), so it also needs direct org_id.

## How to apply

When adding multi-tenancy to a PostgreSQL schema:
1. Map the FK graph — identify root entities vs children
2. Add org_id only where direct access bypasses the parent path
3. Use `verify_parent_access()` helpers for child entity routes
4. Child entities without direct access routes don't need org_id
