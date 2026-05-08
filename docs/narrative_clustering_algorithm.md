# Narrative Clustering Algorithm: From HDBSCAN to Leiden

This document explains the narrative clustering algorithm used in Anveshak's analyst
service — what we used before (HDBSCAN), why it failed, what we replaced it with
(Leiden community detection), and how the new algorithm works step by step.

---

## What Narrative Clustering Does in Anveshak

Anveshak scrapes articles from multiple platforms (Telegram, Reddit, web, Bluesky, X)
about monitored topics like "Indian Defence" or "Cyber Threats." A single topic can
have multiple ongoing narratives:

- "Rafale deployment to Ladakh"
- "India-China LAC tensions"
- "Naval exercise Malabar"
- "DRDO missile test"

The clustering algorithm answers: **"Which articles are talking about the same
narrative?"** Articles in the same narrative get grouped into a `narrative_cluster`.
The signal engine then fires alerts when a cluster has articles from multiple
independent platforms (`independent_source_count >= signal_threshold`).

---

## The Previous Algorithm: HDBSCAN

### What HDBSCAN Is

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise)
is a clustering algorithm designed to find dense groups of points separated by sparse
gaps. Think of looking at a city from above at night — HDBSCAN finds the bright
clusters of lights (dense neighborhoods) separated by dark patches (empty land).

### How HDBSCAN Worked (Step by Step)

**Step 1 — Core distance.** For each article, measure the distance to its 2nd nearest
neighbor (`min_samples=2`). This tells HDBSCAN "how dense is it around this article?"
If the 2nd neighbor is close, it's a dense area. If far, it's a sparse area.

**Step 2 — Mutual reachability.** For every pair of articles A and B, compute the
"effective distance":

```
effective_distance(A, B) = max(core_distance_A, core_distance_B, actual_distance_A_B)
```

This smooths out the density — sparse areas get stretched, dense areas stay tight.

**Step 3 — Build a hierarchy.** Connect all articles using a minimum spanning tree
of mutual reachability distances, then cut edges from longest to shortest. This creates
a tree (dendrogram) showing "at what density level does each cluster appear and
disappear?"

**Step 4 — Extract stable clusters.** Walk the tree and find clusters that **persist**
across many density levels. A cluster that exists briefly is noise. A cluster that
exists for a long stretch is "real."

### Our Configuration

```python
HDBSCAN(
    min_cluster_size=3,      # adaptive: max(2, min(3, item_count // 5))
    min_samples=2,
    metric="precomputed",    # we pass a distance matrix, not raw data
    allow_single_cluster=True,  # added as a patch (see below)
)
```

### The Blended Distance Matrix

Before passing data to HDBSCAN, we computed a blended distance matrix combining
two signals:

1. **Cosine distance** (70% weight) — measures semantic similarity between article
   embeddings from sentence-transformers. Articles about the same topic have similar
   embeddings.

2. **Entity MinHash distance** (30% weight) — measures entity overlap using MinHash
   Jaccard estimation. Articles mentioning the same people, organizations, and
   locations get pulled closer together even if their embeddings are somewhat distant.

```python
# Where both articles have extracted entities:
blended_distance = 0.7 * cosine_distance + 0.3 * entity_distance

# Where either article has no entities:
blended_distance = cosine_distance  # fall back to cosine only
```

This blending is valuable and was kept in the new algorithm.

---

## Why HDBSCAN Failed

### The Fundamental Mismatch

HDBSCAN asks: **"Where are the dense regions separated by sparse gaps?"**

Anveshak asks: **"Which articles are about the same narrative?"**

These are different questions. When all articles are about one narrative, there
are no gaps — and HDBSCAN has no answer.

### Failure Case: Single Narrative (The Common Case)

Picture 15 articles about Rafale deployment. In embedding space, they're all sitting
in a tight ball — roughly equal distances from each other (~0.05 cosine distance
between any pair).

**Step 1 breaks down.** Every article's core distance is ~0.05. All identical. HDBSCAN
thinks "the density is the same everywhere."

**Step 2 changes nothing.** Since all core distances are the same, mutual reachability
equals actual distance. No smoothing effect.

**Step 3 builds a flat tree.** All edges in the spanning tree have roughly the same
weight (~0.05). The hierarchy looks like this:

```
density
  ^
high |  .......................  (all articles merge at nearly the same level)
     |
low  |  . . . . . . . . . . . . . . .  (15 individual articles)
     +--------------------------------------
```

There's no "step" in the hierarchy where a cluster clearly forms and persists.

**Step 4 finds nothing stable.** The cluster appears at density level 19.8 and
disappears at 20.0. That's a persistence of 0.2. HDBSCAN's stability test says
"this cluster barely existed — it's probably noise." So it labels everything -1
(noise). Zero clusters formed.

Compare this to what HDBSCAN is designed for — two well-separated groups:

```
density
  ^
high |  .....        ....    (two clusters persist across many density levels)
     |  .......    .......
     |  .........  .........
     |
low  |  . . . . . . . . . . . . . . .
     +--------------------------------------
```

Here, each cluster appears at high density and persists for a long range before
merging. HDBSCAN correctly identifies both.

### The Patches We Applied (Band-Aids)

We tried to fix HDBSCAN with two patches:

**Patch 1: `allow_single_cluster=True`** — By default, HDBSCAN refuses to recognize
a single group as a cluster. It needs at least two groups to compare against each
other. This flag tells it "yes, one cluster is a valid answer." But even with this
flag, the stability is still low, so HDBSCAN only puts `min_cluster_size` items (3)
in the cluster and marks the other 12 as noise.

**Patch 2: Noise reassignment** — After HDBSCAN runs, we took the noise items and
checked: "is this item close enough to an existing cluster centroid?" If yes, we
force-assigned it. This essentially overrides HDBSCAN's decision. If we have to
override it every time, the algorithm isn't solving our problem.

### The Uniform Vector Problem in Tests

The original integration tests used uniform base vectors like `[0.1, 0.1, 0.1, ...]*384`.
This caused two additional problems:

1. **Not L2-normalized.** The clustering code assumes unit vectors (matching
   sentence-transformers output) so cosine similarity = dot product. A vector
   `[0.1]*384` has L2 norm ~1.96, so dot products produced values >1.0 and negative
   distances — complete garbage.

2. **No per-dimension diversity.** Even after normalization, uniform vectors produce
   degenerate pairwise distances where every pair of items is exactly the same
   distance apart. Real sentence-transformer embeddings have varied values across
   dimensions (~0.4 in one dimension, -0.2 in another, 0.7 in another). This
   diversity is what makes perturbation produce meaningful distance variation.

---

## The New Algorithm: Leiden Community Detection

### Why Leiden

We researched how the industry handles news article clustering:

| System | Algorithm | Scale |
|--------|-----------|-------|
| **Newscatcher** (production) | Leiden community detection | Millions of articles |
| **Chronicle** (OSS) | HDBSCAN + MinHash dedup | Research scale |
| **AWS FSI** | Incremental centroid-based | Enterprise |
| **ACL 2025 paper** | Constrained k-means | Research |

Newscatcher, which clusters millions of news articles in production, switched FROM
density-based methods TO Leiden graph community detection. Their pipeline is exactly
what we now implement.

### What Leiden Does

Forget density. Forget hierarchies. Ask one simple question per pair of articles:

> "Are these two articles about the same narrative?"

If blended similarity >= 0.75 → **yes, same narrative** → draw an edge.
If blended similarity < 0.75 → **no, different narratives** → no edge.

Then find well-connected communities in this graph using modularity optimization.

### Why Not Simple Connected Components?

We initially considered connected components (just find groups of connected nodes).
But it has a **chaining problem**:

```
Article A: "Rafale contract with Dassault"      (entities: Rafale, Dassault)
Article B: "Dassault quarterly earnings report"  (entities: Dassault, CAC40)
Article C: "CAC40 index drops amid EU crisis"    (entities: CAC40, EU)
```

A is similar to B (share "Dassault"), B is similar to C (share "CAC40"), but A and C
are completely unrelated. Connected components would put all three in one cluster
because A-B-C forms a chain.

Leiden solves this. It optimizes **modularity** — it finds groups where internal
connections are denser than expected by chance. A-B-C is a weak chain, not a dense
community. Leiden would split it correctly.

### How Leiden Works (Step by Step)

#### Step 1 — Compute Blended Similarity Matrix

Same as before — this part is unchanged:

```python
# Cosine similarity (embeddings are L2-normalized)
cosine_sim = embedding_matrix @ embedding_matrix.T

# Entity MinHash similarity (Jaccard estimate)
entity_sim = minhash_similarity_matrix(minhash_list)

# Blend: 70% cosine + 30% entity (where both articles have entities)
blended_sim = 0.7 * cosine_sim + 0.3 * entity_sim
# Where either article has no entities: fall back to cosine only
```

#### Step 2 — Build Similarity Graph

Create a graph where:
- Each article is a **node**
- An **edge** connects two articles if their blended similarity >= 0.75
- The edge **weight** is the similarity value

Example with 8 articles — 4 about Rafale, 3 about Naval exercise, 1 unrelated:

```
Pairwise blended similarities:

        R1    R2    R3    R4    N1    N2    N3    O1
R1    1.00  0.88  0.82  0.85  0.35  0.31  0.38  0.20
R2    0.88  1.00  0.79  0.91  0.40  0.33  0.36  0.18
R3    0.82  0.79  1.00  0.80  0.42  0.38  0.41  0.22
R4    0.85  0.91  0.80  1.00  0.37  0.35  0.33  0.15
N1    0.35  0.40  0.42  0.37  1.00  0.84  0.81  0.25
N2    0.31  0.33  0.38  0.35  0.84  1.00  0.87  0.19
N3    0.38  0.36  0.41  0.33  0.81  0.87  1.00  0.21
O1    0.20  0.18  0.22  0.15  0.25  0.19  0.21  1.00
```

Apply threshold (>= 0.75). Edges formed:

```
R1-R2 (0.88), R1-R3 (0.82), R1-R4 (0.85)
R2-R3 (0.79), R2-R4 (0.91), R3-R4 (0.80)
N1-N2 (0.84), N1-N3 (0.81), N2-N3 (0.87)

No edges between Rafale and Naval articles (all < 0.75)
No edges to O1 (all < 0.75)
```

The graph:

```
  R1 --- R2          N1 --- N2
  | \    |           | \    |
  |  \   |           |  \   |
  R3 --- R4          N3 --+         O1

  [Community 0]     [Community 1]   [no edges, singleton]
```

#### Step 3 — Run Leiden Community Detection

Leiden optimizes **modularity** — a measure of how much denser the connections are
within communities compared to what you'd expect by random chance.

**Modularity intuition:** If a group of 4 articles has 6 edges between them, but
you'd only expect 2 edges by random chance, that group has high modularity. It's
a real community, not a random coincidence.

The Leiden algorithm works in three phases, iterated until convergence:

**Phase 1 — Local moving.** Each node is moved to the community of its neighbor
that gives the largest increase in modularity. This is fast and greedy.

**Phase 2 — Refinement.** Unlike its predecessor (Louvain), Leiden refines each
community by checking if it can be split into better sub-communities. This
guarantees that communities are well-connected (no disconnected sub-parts).

**Phase 3 — Aggregation.** Collapse each community into a single super-node,
creating a coarser graph. Repeat from Phase 1 on the coarser graph.

The algorithm converges when no movement improves modularity.

**Result for our example:**
- Community 0: {R1, R2, R3, R4} — Rafale narrative
- Community 1: {N1, N2, N3} — Naval narrative
- O1: singleton, below min_cluster_size → discarded

#### Step 4 — Filter Small Communities

Communities smaller than `clustering_min_cluster_size` (default: 2) are discarded.
A singleton article with no similar articles doesn't form a cluster — it stays
unclustered until more similar articles arrive.

#### Step 5 — Persist Clusters

For each community (same logic as before, unchanged):
- Compute **centroid**: mean of member embeddings, L2-normalized
- Count **independent_source_count**: distinct platforms in the cluster
- Count **item_count**: total articles
- Generate **cluster_id**: deterministic UUID5 from topic_id + community label
- **Upsert** into `narrative_clusters` table
- **Link** content items to cluster via `narrative_cluster_id`

---

## How the Full Pipeline Works

### Fresh Topic (No Existing Clusters)

```
New topic "Indian Defence" gets first scrape → 30 articles arrive

1. Load unclustered embeddings (narrative_cluster_id IS NULL)
2. No existing clusters → run Leiden on all 30 articles
3. Compute blended similarity matrix (30x30)
4. Build graph: edges where similarity >= 0.75
5. Leiden finds communities: e.g., 3 communities
6. Persist each community as a narrative_cluster
7. Signal engine checks: independent_source_count >= signal_threshold?
```

### Incremental Scrape (Existing Clusters)

```
Next scrape → 10 new articles arrive

1. Load unclustered embeddings (only new articles)
2. Load existing cluster centroids
3. For each new article:
   - Compute cosine similarity to each cluster centroid
   - If best similarity >= 0.75 → assign to that cluster
   - Otherwise → mark as unassigned
4. Update cluster centroids and ISC for assigned items
5. If unassigned items remain → run Leiden only on those
6. New communities from Leiden become new clusters
7. Signal engine re-checks
```

This incremental path is O(new_items x existing_clusters) — fast. Leiden only runs
on the truly unassigned items, not the entire corpus.

---

## The Bridge Article Problem

### The Scenario

An article about "IAF Rafale jets deployed to Ladakh amid India-China LAC tensions"
mentions entities from two narratives:

- **Narrative A** (Rafale deployment): entities IAF, Rafale, Dassault
- **Narrative B** (India-China border): entities LAC, India, China, border

With the 0.7 cosine + 0.3 entity blend, this article has:
- High blended similarity to Narrative A articles (~0.80)
- Moderate blended similarity to Narrative B articles (~0.65)

### How Leiden Handles It

The bridge article has edges to Narrative A articles (similarity >= 0.75) but not to
Narrative B articles (similarity < 0.75). Leiden places it in Community A.

Even if the bridge article had edges to both narratives, Leiden's modularity
optimization would not merge the two communities. Merging would decrease modularity
because the internal density of the merged group would be lower than the two
separate communities.

### Our Approach: Hard Assignment

The article belongs to **exactly one cluster**. This is the right choice for Anveshak:

1. **Reports are immutable evidence chains.** An article appearing in multiple
   reports creates ambiguity — "which report is authoritative?"

2. **Signal engine counts `independent_source_count`.** If one article inflates
   ISC for two clusters, you get false signals.

3. **Audit trail clarity.** One article → one cluster → one chain of evidence.

A future enhancement could store **cross-references** in a lightweight table when
an article has high similarity to a second cluster (>= 0.6), giving analysts
visibility into narrative overlap without complicating the clustering pipeline.

---

## Why Leiden Is Better Than HDBSCAN for Anveshak

| Property | HDBSCAN | Leiden |
|----------|---------|-------|
| Question it answers | "Where are dense regions?" | "Which articles are about the same thing?" |
| Single narrative | Fails — no density contrast | Works naturally — one community |
| Multiple narratives | Works if well-separated | Works — separate communities |
| Noise points | Yes, many items become noise | No noise concept — every connected item clusters |
| Parameters to tune | min_cluster_size, min_samples, allow_single_cluster | One threshold (0.75) |
| Deterministic | No (can vary between runs) | Yes (with fixed resolution parameter) |
| Interpretable | "Density persistence in condensed tree" | "These articles are similar enough" |
| Incremental | Needs full re-run on unassigned | Same incremental path |
| Chaining risk | N/A (not graph-based) | Handled by modularity optimization |

HDBSCAN is a powerful algorithm for discovering clusters in spatial data, genomics,
and anomaly detection. But Anveshak's problem is simpler and more specific: group
articles by narrative similarity with a known threshold. Leiden directly answers
that question.

---

## Configuration

All clustering settings are in `services/analyst/anveshak/analyst/settings.py`:

```python
# Clustering — Leiden community detection on blended similarity graph
clustering_similarity_threshold: float = 0.75  # min blended similarity to form an edge
clustering_min_cluster_size: int = 2            # communities smaller than this are discarded
clustering_window_days: int = 30                # only cluster content from last N days
cluster_assign_threshold: float = 0.75          # cosine sim to assign new item to existing cluster
entity_blend_weight: float = 0.3                # weight of entity similarity (0=cosine only, 1=entity only)
minhash_num_perm: int = 128                     # MinHash permutations for Jaccard estimation
```

All settings come from environment variables (hardware independence rule).

---

## Dependencies

```toml
# Previous
"hdbscan>=0.8"

# Current
"leidenalg>=0.10"   # Leiden community detection algorithm
"igraph>=0.11"       # Graph library (required by leidenalg)
```

---

## Test Coverage

### Unit Tests (`tests/unit/test_leiden_clustering.py`)

| Scenario | Articles | What it validates |
|----------|----------|-------------------|
| Single narrative, small batch | 6 (3 platforms) | Leiden handles single-narrative without density contrast |
| Bridge article with entity overlap | 16 (7+7+1+1) | Entity overlap doesn't merge two narratives |
| Chaining risk | 9 (chain + support) | Leiden breaks weak chains (connected components wouldn't) |
| Sparse topic | 3 | Graceful handling of tiny datasets |
| All articles different | 20 | Zero clusters formed from dissimilar data |

### Integration Tests (`tests/integration/test_cluster_signal_pipeline.py`)

| Scenario | Articles | What it validates |
|----------|----------|-------------------|
| Multi-platform cluster formation | 6 | Cluster forms, ISC counted correctly |
| ISC reflects platform diversity | 15 | ISC = platforms, not item count |
| Signal fires on threshold | 4 | Signal engine works with Leiden clusters |
| No duplicate signals | 4 | Dedup prevents double-firing |
| WebSocket delivery | 4 | Signal delivery within 10s |
| Production load (100 articles) | 100 (5 narratives x 20) | 5 clusters, ISC=4 each, <2s |
| Incremental arrival | 10+4 | New items join existing clusters |

---

## Key Code Locations

| Component | File |
|-----------|------|
| Leiden clustering | `services/analyst/anveshak/analyst/clustering.py` → `find_narrative_clusters()` |
| Blended similarity | `services/analyst/anveshak/analyst/clustering.py` → `_compute_blended_similarity()` |
| Entity MinHash | `services/analyst/anveshak/analyst/entity_minhash.py` |
| Incremental assignment | `services/analyst/anveshak/analyst/clustering.py` → `assign_to_nearest_cluster()` |
| Orchestrator | `services/analyst/anveshak/analyst/clustering.py` → `run_clustering()` |
| Settings | `services/analyst/anveshak/analyst/settings.py` |

---

## References

- [Newscatcher — Clustering news articles (Leiden in production)](https://www.newscatcherapi.com/docs/news-api/guides-and-concepts/clustering-news-articles)
- [From Louvain to Leiden — guaranteeing well-connected communities](https://www.nature.com/articles/s41598-019-41695-z)
- [ACL 2025 — Structured clustering for narrative induction](https://arxiv.org/html/2604.10368)
- [Mapping news narratives with LLMs and narrative-structured embeddings](https://arxiv.org/html/2409.06540v1)
- [Chronicle — MinHash + HDBSCAN event detection](https://github.com/dukeblue1994-glitch/chronicle)
- [Clustering news articles for topic detection — technical deep dive](https://dev.to/mayankcse/clustering-news-articles-for-topic-detection-a-technical-deep-dive-2692)
