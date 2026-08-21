---
name: clustering-signals
description: "Narrative clustering and signal engine. Covers Leiden over HDBSCAN, similarity thresholds calibrated per embedding model, incremental clustering via centroid assignment, entity MinHash blending, independent_source_count counting sources not platforms, and org-scoped convergence. Use when working on clustering, narrative detection, signal generation, or services/analyst."
---

# Clustering & Signal Engine

5 learned instincts. Narrative clustering + signal generation.

## Leiden Over HDBSCAN

Leiden for narrative clustering, not HDBSCAN.
HDBSCAN fails when all articles = single narrative (no density gaps).
Leiden: one param (threshold), deterministic, handles single-narrative.
Deps: `leidenalg>=0.10`, `igraph>=0.11`.
See: `.agents/skills/learned/references/leiden-graph-narrative-clustering.md`

## Threshold Must Match Embedding Model

Leiden threshold calibrated per embedding model similarity distribution.
`all-MiniLM-L6-v2` (384d): threshold = 0.70. Larger models: 0.75–0.80.
Model change: benchmark, plot similarity histogram, set threshold at valley.
Update both `CLUSTERING_SIMILARITY_THRESHOLD` and `CLUSTER_ASSIGN_THRESHOLD` in compose.
See: `.agents/skills/learned/references/leiden-threshold-per-model.md`

## Incremental Clustering via Centroid Assignment

Never re-cluster all items every cycle — O(N²). Instead:
1. Load only unclustered items (`narrative_cluster_id IS NULL`)
2. Compare against existing cluster centroids (cosine similarity)
3. similarity >= threshold → assign to cluster, update centroid weighted average
4. Only unassigned items go through full Leiden
5. L2-normalize centroids after update

Preserves cluster_id stability (no signal orphaning).
See: `.agents/skills/learned/references/incremental-clustering-centroid-assign.md`

## Entity MinHash Blending

Blend entity Jaccard similarity into distance metric:
`(1 - weight) * cosine_sim + weight * entity_jaccard_sim`, default weight 0.3.
Store MinHash as `BIGINT[]` in PostgreSQL (values overflow int32).
NULL-safe: only blend where BOTH items have minhash.
See: `.agents/skills/learned/references/entity-minhash-clustering-boost.md`

## ISC Counts Sources, Not Platforms

`independent_source_count` must count distinct `source_id`, not distinct `platform` strings.
All sources on one platform (e.g. RSS) collapses ISC to 1.
Three news orgs via RSS = ISC 3, not ISC 1.
ISC = signal engine core metric — max ISC equals platform count means counting wrong.
See: `.agents/skills/learned/references/isc-count-sources-not-platforms.md`

## Cross-Topic Convergence Must Be Org-Scoped

`SQL_CONVERGENT_CLUSTERS` must add `AND t1.org_id = t2.org_id` — prevents convergence detection across different orgs' classified topics.
See: `.agents/skills/learned/references/dual-layer-rls-safety-net.md`