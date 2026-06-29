# Cross-Topic Aggregate Queries Must Org-Scope Every Sub-Query

## Problem

Cross-topic aggregate endpoints (analytics dashboard, global stats) query across
multiple tables (content_items, signals, reports, extracted_entities, credibility_audit_log).
Each sub-query MUST filter by org_id — missing it on ANY one leaks data cross-org.

Unlike single-topic routes where `verify_topic_access()` catches it, aggregate
routes have no single resource to verify. The org filter must be baked into SQL.

## Pattern

```python
# $1 = days, $2 = org_id on time-filtered queries
SQL_CONTENT_VOLUME_TREND = """
    SELECT DATE(ci.captured_at) AS date, COUNT(*) AS count
    FROM content_items ci
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
    GROUP BY DATE(ci.captured_at)
"""

# Tables without org_id (signals, reports) → JOIN through topics
SQL_SIGNAL_ACTIVITY = """
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    WHERE s.created_at >= NOW() - make_interval(days => $1)
      AND t.org_id = $2
"""

# Repository function: org_id is keyword-only (can't forget it)
async def get_dashboard_data(conn, days: int, *, org_id: str) -> dict:
    ...

# Route: extract org_id from JWT user dict
org_id = user.get("org_id", "")
data = await get_dashboard_data(db, days, org_id=org_id)
```

## Verification test

```python
def test_all_queries_have_org_id_filter(self):
    for sql in [SQL_VOLUME, SQL_PLATFORM, SQL_LANGUAGE, ...]:
        assert "org_id" in sql.lower()

async def test_org_id_passed_to_all_queries(self, mock_conn):
    await get_dashboard_data(mock_conn, days=30, org_id="org-xyz")
    for call in all_db_calls:
        assert "org-xyz" in call.args
```

## How we got burned

First implementation had zero org_id filters. All 8 queries returned data across
all orgs. Code review (cavecrew-reviewer) caught it before production. Fix required
updating every SQL constant + adding org_id as keyword-only parameter + 2 new tests.

## Checklist for new aggregate endpoints

1. Every SQL constant references org_id (directly or via JOIN to topics)
2. `org_id` is keyword-only parameter on repository function
3. Route extracts `org_id` from `user.get("org_id")`
4. Test asserts org_id present in every SQL constant
5. Test asserts org_id passed to every DB call
