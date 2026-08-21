# Pattern: Incremental Clustering via Centroid Assignment

## When to load: modifying clustering logic, scaling to many topics, debugging orphaned signals

---

## Problem

Re-running full clustering from scratch every cycle on ALL items is O(N²) per topic. At 500 items that's 250K distance computations. At 5000 items it's 25M.

## Solution

1. Load only **unclustered** items (`narrative_cluster_id IS NULL`)
2. Compare each new item against **existing cluster centroids** (cosine similarity)
3. If similarity ≥ threshold (0.75) → assign to that cluster, update centroid + ISC
4. Only items that DON'T match any centroid go through Leiden community detection
5. Fresh topics (no existing clusters) fall back to full Leiden

## Key Code

```python
# Load unclustered only
SQL_UNCLUSTERED = "WHERE ci.narrative_cluster_id IS NULL AND ci.embedding IS NOT NULL"

# Assign to nearest centroid
for row in new_rows:
    best_sim = max(np.dot(row.vector, c.vector) for c in centroids)
    if best_sim >= threshold:
        assign_to_cluster(row, best_cluster)
    else:
        unassigned.append(row)

# Leiden only on truly unassigned
if len(unassigned) >= min_cluster_size:
    find_narrative_clusters(unassigned)
```

## Performance

| Scale | O(N²) full | O(new × clusters) incremental |
|-------|-----------|-------------------------------|
| 500 items, 5 new | 250,000 | 50 |
| 5000 items, 50 new | 25,000,000 | 1,000 |

## Pitfall: Centroid Drift

When updating centroids with new items, use weighted average:
```python
updated = (old_centroid * old_count + sum(new_vectors)) / (old_count + new_count)
```
Then L2-normalize. Don't just average old centroid with new item — that over-weights recent items.

## Pitfall: Signal Orphaning

The whole point is cluster_id stability. Never generate new cluster_ids for items that belong to existing clusters. HDBSCAN only runs on the truly unassigned buffer — new cluster_ids only appear for genuinely new narratives.

## Files

- `services/analyst/anveshak/analyst/clustering.py` — `assign_to_nearest_cluster()`, `update_cluster_with_assignments()`
- `services/analyst/anveshak/analyst/settings.py` — `cluster_assign_threshold: float = 0.75`
