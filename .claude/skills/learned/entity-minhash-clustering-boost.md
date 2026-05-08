# Pattern: Entity MinHash Clustering Boost

## When to load: modifying clustering distance, debugging why semantically diverse articles don't cluster, adding new entity-based features

---

## Problem

A dark web post about "AIIMS data dump" and a CERT-In advisory about "AIIMS cyber incident" embed far apart (different vocabulary, tone, style). Pure cosine distance fails to cluster them. But NER already extracted "AIIMS" and "Delhi" from both articles — they share entities.

## Solution

Compute a MinHash fingerprint from extracted entities at ingestion time. At clustering time, blend entity similarity into the distance matrix:

```python
blended_sim = (1 - weight) * cosine_sim + weight * entity_jaccard_sim
```

Default weight: 0.3 (70% embedding, 30% entity).

## Why MinHash, Not Raw Jaccard

- Raw Jaccard: compare sets of strings per pair → O(N² × avg_entities)
- MinHash: precompute 128-integer fingerprint once → compare integers → ~3ms for 500 items
- Same accuracy (probabilistic Jaccard estimate)

## Key Implementation Details

### 1. MinHash values are uint64 — use BIGINT[], not INTEGER[]

```sql
-- WRONG: MinHash values overflow int32
ALTER TABLE content_items ADD COLUMN entity_minhash INTEGER[];
-- OverflowError: value out of int32 range

-- CORRECT:
ALTER TABLE content_items ADD COLUMN entity_minhash BIGINT[];
```

### 2. NULL-safe blending is critical

Items without entity_minhash (no entities, pre-migration content) must NOT be penalized. Without NULL-safety:
```python
# WRONG: NULL minhash → entity_sim=0 → entity_dist=1.0
blended = 0.7 * cosine + 0.3 * 1.0  # adds 0.3 to ALL distances!
```

Fix: only blend where BOTH items have minhash:
```python
has_minhash = np.array([m is not None for m in minhash_list])
blend_mask = np.outer(has_minhash, has_minhash)
distance = np.where(blend_mask, blended, cosine_only)
```

### 3. Don't prefix topic keywords into embeddings

Considered but rejected: prepending topic name to article text before embedding. This corrupts the embedding for multi-topic use — one article can be linked to many topics via `topic_content_items`. Baking Topic A's keywords into the embedding makes it useless for Topic B.

Entity MinHash is the correct approach because it's computed once from NER output (topic-independent) and blended only at clustering time (per-topic).

## Files

- `services/analyst/anveshak/analyst/entity_minhash.py` — `compute_entity_minhash()`, `minhash_similarity_matrix()`
- `services/analyst/anveshak/analyst/clustering.py` — blending logic in `_compute_blended_similarity()`
- `services/analyst/anveshak/analyst/jobs.py` — compute + store after NER
- `services/api/migrations/versions/010_entity_minhash.py` — BIGINT[] column
