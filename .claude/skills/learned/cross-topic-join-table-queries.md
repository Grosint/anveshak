# Pattern: Cross-Topic Join Table Must Be Queried Everywhere

## When to load: writing SQL that filters by topic_id, adding new analytics queries, modifying clustering/signal/reporting code

---

## Problem

Anveshak has two paths for content → topic association:
1. `content_items.topic_id` — direct ownership (scraper inserts here)
2. `topic_content_items` join table — cross-topic backfill (backfill_topic writes here)

Any SQL query that filters `WHERE ci.topic_id = $1` silently excludes backfilled items.
This breaks ISC (independent source count), sentiment analysis, entity extraction, and
keyword trends for topics with shared sources.

## Pattern

Replace single-table filter:
```sql
WHERE ci.topic_id = $1
```

With dual-path filter:
```sql
WHERE (ci.topic_id = $1
   OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
```

Index `idx_topic_content_items_topic` makes the subquery an efficient index scan.

## Checklist for new topic-scoped queries

Before writing any `WHERE topic_id = $1` query, ask:
1. Should this include backfilled items? (almost always yes)
2. Is `topic_content_items` in the query? If not, add the `OR ... IN` clause
3. Is there a contract test verifying backfilled items appear in results?

## How this bug was missed

Backfill tests verified "did we INSERT into topic_content_items?" ✓
Clustering tests verified "does Leiden form correct clusters from EmbeddingRows?" ✓
Neither tested the seam: "does clustering's SQL load backfilled items?" ✗

Both had 100% unit test coverage. The bug lived in a SQL WHERE clause.

## Files affected (fixed 2026-05-09)

- `services/analyst/anveshak/analyst/clustering.py` — 4 queries
- `services/analyst/anveshak/analyst/signal_engine.py` — 2 queries
- `services/api/anveshak/api/db/topics.py` — 4 queries
- `tests/integration/test_backfill_clustering_contract.py` — contract tests
