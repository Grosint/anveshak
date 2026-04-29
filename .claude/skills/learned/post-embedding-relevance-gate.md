# Pattern: Post-Embedding Relevance Gate (filter off-topic content before clustering)

## When to load: adding semantic filtering to clustering pipelines, or when general news sources pollute narrow topics with irrelevant content

---

## Problem

When a user links a general source (e.g. `hindustantimes.com`) to a narrow topic (e.g. "China PLA Near Border"), the scraper fetches ALL articles — sports, entertainment, etc. These all get embedded, clustered, and can fire false signals.

## Solution: Cosine similarity gate between content and topic query embeddings

After `encode_text()` produces the content embedding, compute a second embedding from the topic's `name + keywords`, then dot-product the two (both L2-normalized). Store the score on the content item. Filter at clustering time.

### Key design decisions

1. **Store score, never discard** — Intelligence platform, no silent deletion. Low-scoring items remain in DB for auditability but are excluded from HDBSCAN.

2. **Filter at clustering time, not at write time** — The embedding is needed to compute the score, so you must write it first. Clustering SQL adds `AND (ci.topic_relevance_score IS NULL OR ci.topic_relevance_score >= $threshold)`.

3. **NULL = include (backward compat)** — Pre-feature items have NULL scores and must still be clustered until the backfill job scores them.

4. **Per-topic override + global default** — Nullable column on `topics` table; `resolve_threshold(per_topic)` returns override if set, else global from settings.

### Threshold calibration (critical — don't guess)

```
# WRONG: guess a threshold
topic_relevance_threshold: float = 0.30  # "seems reasonable"

# RIGHT: seed real data, observe histogram, then set threshold
# Real data showed: relevant clusters avg 0.45+, junk 0.30–0.40
# So 0.42 cleanly separates signal from noise
topic_relevance_threshold: float = 0.42
```

The Prometheus histogram (`analyst_topic_relevance_score`) is essential — deploy with a permissive threshold first, observe the bimodal distribution, then tighten.

### Reuse the backfill pattern for topic query embedding

```python
# Same logic as backfill._build_query_text — inline to avoid circular import
def build_topic_query_text(name: str, keywords: list[str]) -> str:
    return " ".join([name] + list(keywords))

# Both vectors are L2-normalized by encode_text(), so cosine = dot product
def compute_topic_relevance(content_emb, topic_query_emb) -> float:
    return float(np.dot(np.asarray(content_emb), np.asarray(topic_query_emb)))
```

### SQL parameter ordering pitfall

When adding a new parameter to existing SQL queries, all positional params shift:

```sql
-- Before: $1=topic_id, $2=window_days
-- After:  $1=topic_id, $2=relevance_threshold, $3=window_days
-- Every caller and every test assertion must be updated
```

## Implementation reference

- `services/analyst/anveshak/analyst/relevance.py` — pure functions
- `services/analyst/anveshak/analyst/jobs.py` — score computed after embedding (step 4a)
- `services/analyst/anveshak/analyst/clustering.py` — SQL filter + threshold resolution
- `services/api/migrations/versions/009_topic_relevance.py` — schema
