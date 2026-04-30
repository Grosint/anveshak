# Quality Gate at All Consumers

## When: adding a content quality/relevance signal that filters data

## Problem

The `topic_relevance_score` was computed for every content item (in `jobs.py`)
and used as a WHERE clause filter in clustering SQL — but the content feed API
(`get_topic_content()`) had no relevance filter at all. Result: junk content
(score 0.17, threshold 0.42) was hidden from clusters/signals but still visible
to analysts in the content feed UI.

## Pattern

**When you compute a quality signal, apply it at every consumption point.**

Consumption points for `topic_relevance_score`:
1. Clustering SQL — `WHERE topic_relevance_score >= threshold` (was done)
2. Content feed API — `WHERE topic_relevance_score >= threshold` (was missing)
3. Report generation RAG context — should also filter (check if done)

The same applies to `content_quality`:
- Already filtered in content feed via `include_low_quality=False` default
- Already filtered in clustering via quality check in `analyse_content()`

## SQL pattern (backward-compatible NULL handling)

```sql
AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $N)
```

NULL = not yet scored (pre-feature items or pending analysis). Include them
to avoid hiding valid content that hasn't been through the analyst pipeline yet.

## Threshold resolution

Per-topic override from `topics.topic_relevance_threshold` column, falling back
to global default (0.42). Same `resolve_threshold()` pattern used in clustering.

## Checklist when adding a new quality signal

1. Where is the signal computed? (analyst jobs)
2. Where is it stored? (content_items column)
3. List ALL queries that read content_items — add filter to each
4. Handle NULL (pre-existing rows) with `IS NULL OR` pattern
5. Add per-topic override column if threshold varies by use case
6. Expose in API response if analyst needs to see/sort by it
