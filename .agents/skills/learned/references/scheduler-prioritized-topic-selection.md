# Pattern: Prioritized Topic Selection for Scheduler Loops

## When to load: modifying scheduler loops, adding new periodic processing, scaling to 200+ topics

---

## Problem

`SELECT id FROM topics WHERE status = 'active'` processes ALL topics every cycle.
At 200+ topics, even windowed O(N²) clustering per topic saturates CPU.
Topics with zero pending work waste cycles.

## Pattern: Priority queue with HAVING filter

```sql
SELECT t.id,
       COUNT(ci.id) FILTER (WHERE ci.narrative_cluster_id IS NULL
                              AND ci.embedding IS NOT NULL) AS pending
FROM topics t
LEFT JOIN content_items ci ON ci.topic_id = t.id
WHERE t.status = 'active'
GROUP BY t.id
HAVING COUNT(...) > 0          -- skip topics with no work
ORDER BY pending DESC          -- most urgent first
LIMIT $1                       -- cap per-cycle (when throttle enabled)
```

Three benefits:
1. **Skip idle topics** — HAVING clause eliminates topics with zero unclustered items
2. **Prioritize urgent** — topics with 100 pending items before topics with 5
3. **Cap per-cycle** — LIMIT prevents CPU saturation on busy deployments

## Settings

- `MAX_TOPICS_PER_CYCLE=0` (disabled, process all with pending items)
- When set to 50: process top 50, remaining get processed next cycle
- Fair rotation happens naturally — once items are clustered, pending drops, topic yields

## Pitfall: Don't remove SQL_ACTIVE_TOPICS

Keep the old `SQL_ACTIVE_TOPICS` for use cases that need ALL active topics
regardless of pending state (e.g., backfill sweep, signal checks).
The prioritized query is specifically for clustering.

## Files

- `services/analyst/anveshak/analyst/scheduler.py` — `get_prioritized_topics()`, `SQL_ACTIVE_TOPICS_PRIORITIZED`
