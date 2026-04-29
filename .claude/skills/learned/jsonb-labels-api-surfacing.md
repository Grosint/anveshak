# Surfacing JSONB Labels Through CTE Content Queries

## When to load: exposing labels JSONB sub-fields (sentiment, keywords, etc.) through API content listing endpoints

---

## Problem

Content items store NLP results in `labels` JSONB (`nlp-results-in-jsonb-labels.md`), but the content listing CTE query doesn't select `labels`. Adding it to a complex CTE with UNION ALL + DISTINCT ON dedup requires careful column threading.

## Pattern

### 1. Add `ci.labels` to BOTH halves of the UNION ALL

The content listing uses `all_items AS (SELECT ... UNION ALL SELECT ...)`. The `labels` column must appear in **both** SELECT lists at the same position:

```sql
-- First half (direct content)
SELECT ci.id, ci.url, ..., ci.labels, s.name AS source_name, ...
FROM content_items ci ...
WHERE ci.topic_id = $1

UNION ALL

-- Second half (backfilled content)
SELECT ci.id, ci.url, ..., ci.labels, s.name AS source_name, ...
FROM topic_content_items tci
JOIN content_items ci ON ...
WHERE tci.topic_id = $1
```

### 2. Carry through `deduped` and `with_counts` CTEs

```sql
deduped AS (
    SELECT DISTINCT ON (COALESCE(clean_hash, id))
           id, url, ..., labels, source_name, platform, backfilled
    FROM all_items
    ORDER BY COALESCE(clean_hash, id), captured_at DESC
)
-- Final SELECT must include labels too
SELECT ..., labels FROM with_counts ...
```

### 3. Post-process: extract sub-fields, drop raw labels

Don't return the full `labels` blob to the frontend. Extract what's needed:

```python
results = []
for r in rows:
    d = dict(r)
    labels = d.pop("labels", None) or {}
    if isinstance(labels, str):
        labels = json.loads(labels)  # asyncpg may return JSON string
    d["sentiment"] = labels.get("sentiment")
    d["keywords"] = labels.get("keywords", [])
    results.append(d)
return results
```

### 4. Filter clauses use JSONB operators directly

```python
# No parameterized input needed — these are static float literals
if sentiment == "positive":
    clause = "AND (ci.labels->'sentiment'->>'compound')::float >= 0.05"
```

Inject `{sentiment_clause}` into both UNION ALL halves alongside existing `quality_clause`, `emb_clause`, `platform_clause`.

## Why this matters

- CTE column lists must match across UNION ALL — missing a column in one half is a SQL error
- `DISTINCT ON` dedup preserves the labels from the newest row per clean_hash (correct behaviour)
- asyncpg sometimes returns JSONB as a string (no registered codec) — always guard with `isinstance(str)` check
- Returning raw labels wastes bandwidth and leaks internal metadata to the frontend
