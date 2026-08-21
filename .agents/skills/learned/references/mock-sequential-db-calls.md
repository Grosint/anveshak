# Pattern: Mock Sequential DB Calls with side_effect

## When to load: writing unit tests for functions that make multiple sequential DB queries on the same connection

---

## Problem

A function calls `conn.fetch()` twice — first for the main query, then for enrichment. Using `mock_conn.fetch.return_value` returns the same data for both calls, causing `KeyError` on the second call's different column names.

```python
# WRONG — same data returned for both fetch() calls
mock_conn.fetch.return_value = [
    {"id": "c1", "label": "Naval ops", "item_count": 10}
]
# Second call expects {"source_name": ...} → KeyError: 'source_name'
```

## Solution

Use `side_effect` with a list — each call consumes the next item:

```python
# RIGHT — different data for each sequential call
mock_conn.fetch.side_effect = [
    # First call: main query results
    [{"id": "c1", "label": "Naval ops", "item_count": 10}],
    # Second call: enrichment query results
    [{"source_name": "reuters.com", "platform": "web", "credibility_score": 72.0}],
]
```

Also applies to `fetchrow` / `fetchval` when a function queries multiple tables sequentially.

## Corollary: expanded row schemas

When a SQL query is expanded with JOINs (e.g. adding topic fields), every test mock returning `fake_row` must include the new columns:

```python
# After SQL_GET_CONTENT joins topics table:
fake_row = {
    "id": content_id,
    "clean_text": text,
    "topic_id": "topic-test",           # NEW
    "topic_name": "Test Topic",          # NEW
    "topic_keywords": ["kw1", "kw2"],    # NEW
    "topic_relevance_threshold": None,   # NEW
}
```
