# Scope Parameter Passthrough Invariant

## Problem

Signals route accepted `topic_id` query param but ignored it for non-admin users.
Route dispatched to `list_signals_by_org(org_id)` which returned ALL signals in the org.
Frontend passed `topic_id` correctly — bug was purely backend.

Bug was invisible with one topic per org. Exposed when second topic added to same org.

## Rule

If a route accepts a scoping parameter (`topic_id`, `source_id`, `org_id`), EVERY code
path in that route must pass it through to the DB layer. No path may silently drop it.

Invariant: `route accepts param` → `all branches pass param` → `SQL uses param`

Checklist for scope-filtering routes:
1. List all `if/elif/else` branches in the route
2. For EACH branch, verify the scope param reaches the SQL
3. Time-range queries are easy to miss — they often have separate SQL without the filter
4. Super-admin path can skip org_id but should still respect topic_id

## Pattern

```python
# WRONG — topic_id silently dropped for org users
if is_super_admin(user):
    return await db.list_signals(status, topic_id=topic_id)
return await db.list_signals_by_org(status, org_id)  # topic_id lost

# CORRECT — topic_id takes priority when present
if topic_id:
    return await db.list_signals(status, topic_id=topic_id)
if is_super_admin(user):
    return await db.list_signals(status)
return await db.list_signals_by_org(status, org_id)
```

## See also

- `dual-layer-rls-safety-net.md` — org isolation layers
- `org-id-root-tables-only.md` — where org_id belongs
