# Clustering & Signal Engine

Consolidated from 5 learned instincts. These apply to narrative clustering and signal generation.

## Leiden Over HDBSCAN

Use Leiden community detection for narrative clustering, not HDBSCAN.
HDBSCAN fails when all articles form a single narrative (no density gaps).
Leiden has one parameter (threshold), is deterministic, handles single-narrative case.
Dependencies: `leidenalg>=0.10`, `igraph>=0.11`.
See: `learned/leiden-graph-narrative-clustering.md`

## Threshold Must Match Embedding Model

Leiden threshold must be calibrated per embedding model's similarity distribution.
`all-MiniLM-L6-v2` (384d): threshold = 0.70. Larger models may need 0.75–0.80.
When changing model: run benchmark, plot similarity histogram, set threshold at valley.
Also update both `CLUSTERING_SIMILARITY_THRESHOLD` and `CLUSTER_ASSIGN_THRESHOLD` in compose.
See: `learned/leiden-threshold-per-model.md`

## Incremental Clustering via Centroid Assignment

Don't re-cluster all items every cycle — O(N²). Instead:
1. Load only unclustered items (`narrative_cluster_id IS NULL`)
2. Compare against existing cluster centroids (cosine similarity)
3. If similarity >= threshold → assign to cluster, update centroid with weighted average
4. Only unassigned items go through full Leiden
5. L2-normalize centroids after update

This preserves cluster_id stability (no signal orphaning).
See: `learned/incremental-clustering-centroid-assign.md`

## Entity MinHash Blending

Blend entity Jaccard similarity into the distance metric:
`(1 - weight) * cosine_sim + weight * entity_jaccard_sim`, default weight 0.3.
Store MinHash as `BIGINT[]` in PostgreSQL (values overflow int32).
NULL-safe: only blend where BOTH items have minhash.
See: `learned/entity-minhash-clustering-boost.md`

## ISC Counts Sources, Not Platforms

`independent_source_count` must count distinct `source_id` values, not distinct `platform` strings.
Consolidating sources to one platform (e.g., all RSS) collapses ISC to 1.
Three different news organisations via RSS = ISC 3, not ISC 1.
ISC is the signal engine's core metric — if max ISC equals number of platforms, counting is wrong.
See: `learned/isc-count-sources-not-platforms.md`

## Cross-Topic Convergence Must Be Org-Scoped

`SQL_CONVERGENT_CLUSTERS` must add `AND t1.org_id = t2.org_id` to prevent
detecting convergence between different organizations' classified topics.
See: `learned/dual-layer-rls-safety-net.md`
