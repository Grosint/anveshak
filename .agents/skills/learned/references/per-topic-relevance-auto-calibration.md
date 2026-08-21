# Per-Topic Relevance Auto-Calibration

## Problem

A global relevance threshold (0.35) filtered out 74-96% of scraped content because
different topics have vastly different score distributions:

| Topic | Median Score | Surviving @0.35 |
|-------|-------------|-----------------|
| IOR Maritime | 0.142 | 6% |
| LAC Military | 0.255 | 4% |
| Pakistan LoC | 0.208 | 18% |
| Disinfo | 0.206 | 17% |

Broad topics (maritime security, geopolitics) produce lower similarity scores
against their keyword embedding than narrow topics (specific person or event).
A single threshold cannot work across topic breadths.

## Fix

Periodic auto-calibration loop in analyst-scheduler:

1. Compute `PERCENTILE_CONT(target_pct)` of `topic_relevance_score` per topic (last 7 days)
2. Clamp to `[floor, ceiling]` (default [0.08, 0.50])
3. UPDATE `topics.topic_relevance_threshold` per topic
4. Skip topics with < min_items scored items (default 20)
5. Skip update if threshold changed by < 0.005 (avoid churn)

```sql
SELECT t.id, t.name, t.topic_relevance_threshold,
       PERCENTILE_CONT($1) WITHIN GROUP (ORDER BY ci.topic_relevance_score) AS target,
       COUNT(*) AS item_count
FROM topics t JOIN content_items ci ON ci.topic_id = t.id
WHERE ci.embedding IS NOT NULL AND ci.topic_relevance_score IS NOT NULL
  AND ci.created_at > NOW() - INTERVAL '7 days'
GROUP BY t.id HAVING COUNT(*) >= $2
```

Runs on startup (immediate convergence) + every 6 hours.

The `topics.topic_relevance_threshold` column and `resolve_threshold()` already
existed but were never populated — the auto-calibration just fills them.

## Key Design Decisions

- **P40 (keep top 60%):** Leiden needs enough items to form communities. 60% survival
  rate gives ~60 items/day for a topic scraping 100 items/day.
- **Floor 0.08:** Prevents accepting pure noise even for very broad topics.
- **Ceiling 0.50:** Prevents filtering everything for narrow topics.
- **7-day window:** Score distributions shift slowly; 7 days is stable enough.
- **Global default (0.35) unchanged:** Fallback for topics with < 20 scored items.

## Quality Gate Enforcement

When adding a per-topic threshold, verify it's used at EVERY consumption point:
1. Clustering SQL — uses `resolve_threshold(per_topic)` ✅
2. Content feed API — reads from topics table ✅
3. Reporter RAG chunks — was MISSING, had to add ✅
4. Pipeline health script — was hardcoded 0.35, had to fix ✅
