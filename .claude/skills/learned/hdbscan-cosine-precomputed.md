# Pattern: HDBSCAN with Cosine Distance (Precomputed Matrix)

## When to load: modifying clustering distance metric, upgrading hdbscan version, debugging clustering quality

---

## Problem

HDBSCAN 0.8.x does not support `metric="cosine"` directly. Using `metric="euclidean"` on L2-normalized embeddings is mathematically monotonic with cosine but HDBSCAN's density estimation (mutual reachability distance) handles them differently, producing worse clusters.

## Solution

Precompute the cosine distance matrix and use `metric="precomputed"`:

```python
matrix = np.vstack([r.vector for r in rows]).astype(np.float64)  # MUST be float64
cosine_sim = matrix @ matrix.T
np.clip(cosine_sim, -1.0, 1.0, out=cosine_sim)
distance_matrix = 1.0 - cosine_sim

clusterer = HDBSCAN(
    min_cluster_size=effective_min,
    min_samples=settings.hdbscan_min_samples,
    metric="precomputed",
)
labels = clusterer.fit_predict(distance_matrix)
```

## Pitfalls

### 1. HDBSCAN 0.8.x requires float64

```python
# WRONG: float32 → "Buffer dtype mismatch, expected 'double_t' but got 'float'"
matrix = np.vstack([r.vector for r in rows])

# CORRECT:
matrix = np.vstack([r.vector for r in rows]).astype(np.float64)
```

### 2. metric="cosine" string not recognized in 0.8.x

```python
# WRONG: "Unrecognized metric 'cosine'"
HDBSCAN(metric="cosine")

# CORRECT: precompute the matrix yourself
HDBSCAN(metric="precomputed")
```

### 3. Consistency with rest of stack

Ensure ALL similarity computations use cosine:
- pgvector: `<=>` operator (cosine distance)
- Relevance scoring: `np.dot(a, b)` on L2-normalized vectors
- Near-duplicate detection: cosine threshold 0.95
- Backfill: cosine similarity search
- HDBSCAN: now also cosine via precomputed

## Files

- `services/analyst/anveshak/analyst/clustering.py` — `run_hdbscan()` function
