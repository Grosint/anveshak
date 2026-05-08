# Pattern: Leiden Graph Clustering for Narrative Detection

## When to load: modifying clustering algorithm, debugging why articles don't cluster, evaluating clustering alternatives, scaling clustering to more topics

---

## Problem

HDBSCAN finds dense regions separated by sparse gaps. But OSINT narrative clustering asks "which articles are about the same story?" — a fundamentally different question. When all articles form a single narrative (common on first scrape), there are no density gaps. HDBSCAN marks everything as noise.

## Solution

Leiden community detection on a blended similarity graph:

```python
# 1. Compute blended similarity (cosine + entity minhash)
sim_matrix = _compute_blended_similarity(rows)

# 2. Build graph: edge if similarity >= threshold
edges, weights = [], []
for i in range(n):
    for j in range(i + 1, n):
        if sim_matrix[i, j] >= threshold:
            edges.append((i, j))
            weights.append(float(sim_matrix[i, j]))

# 3. Leiden community detection
graph = ig.Graph(n=n, edges=edges, directed=False)
graph.es["weight"] = weights
partition = leidenalg.find_partition(
    graph, leidenalg.ModularityVertexPartition, weights="weight",
)
```

## Why Leiden Over Connected Components

Connected components has a chaining problem: A~B and B~C chains into one cluster even when A~C are unrelated. Entity overlap makes this worse (shared entities create bridge edges). Leiden optimises modularity — it only keeps communities where internal density exceeds random expectation, naturally breaking weak chains.

## Why Leiden Over HDBSCAN

| Property | HDBSCAN | Leiden |
|----------|---------|-------|
| Single narrative | Fails (no density contrast) | Works (one community) |
| Noise points | Many items marked as noise | No noise concept |
| Parameters | min_cluster_size, min_samples, allow_single_cluster | One threshold (0.75) |
| Deterministic | No | Yes |

## Industry Validation

Newscatcher (production, millions of articles) uses Leiden for news clustering. They switched FROM density-based methods TO graph community detection.

## Dependencies

```toml
"leidenalg>=0.10"   # Leiden algorithm
"igraph>=0.11"       # Graph library
```

Replaces `hdbscan>=0.8`.

## Files

- `services/analyst/anveshak/analyst/clustering.py` — `find_narrative_clusters()`, `_compute_blended_similarity()`
- `services/analyst/anveshak/analyst/settings.py` — `clustering_similarity_threshold`, `clustering_min_cluster_size`
- `docs/narrative_clustering_algorithm.md` — full algorithm explanation
