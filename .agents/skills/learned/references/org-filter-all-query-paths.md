# Org Filter Must Cover ALL Query Paths

## Problem
Route had two code paths: with time range and without. The non-time-range
path had org_id filtering. The time-range path skipped it entirely.
Result: all orgs' signals leaked to any user using time filters.

## How it happened
```python
# Route code:
if since or until:
    return list_signals_filtered(db, status, since, until)  # NO org filter!
if is_super_admin(user):
    return list_signals(db, status)
org_id = get_user_org(user)
return list_signals_by_org(db, status, org_id)  # has org filter
```

Time-range path was added later, copied the query but forgot org scoping.

## Fix
Pass org_id through ALL query paths:
```python
if since or until:
    _org = None if is_super_admin(user) else get_user_org(user)
    return list_signals_filtered(db, status, since, until, org_id=_org)
```

## Prevention
When adding a new query path (filter, sort, pagination) to an existing
endpoint, check that EVERY existing security filter (org_id, topic_access,
RLS) is applied in the new path too. Grep for `org_id` in the route and
verify each return statement includes it.
