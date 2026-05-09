# Pattern: Leiden Similarity Threshold Must Match Embedding Model

## When to load: changing embedding model, tuning clustering parameters, upgrading to GPU models

---

## Problem

Leiden community detection builds a graph where edges exist between items with
blended similarity >= threshold. The threshold must be calibrated for the specific
embedding model's similarity distribution.

`all-MiniLM-L6-v2` (384d) produces cosine similarities of 0.55–0.75 for semantically
similar but differently-worded articles about the same event. Only near-duplicate
phrasings consistently exceed 0.75.

## Calibration results (2026-05-09)

| Threshold | Precision | Recall | F1 | Notes |
|-----------|-----------|--------|-----|-------|
| 0.75 | 100% | 23.3% | 37.8% | Too strict — most cross-source pairs below threshold |
| **0.70** | **100%** | **40.0%** | **57.1%** | Sweet spot for MiniLM |
| 0.65 | untested | — | — | Risk: merging unrelated narratives in production |

## Rule

When changing the embedding model, re-calibrate the threshold:
1. Run `make benchmark` with current threshold
2. Check pairwise similarity distribution within known-same-event articles
3. Set threshold at the valley between same-event and different-event distributions

Expected thresholds per model (from hardware.md upgrade path):
- `all-MiniLM-L6-v2` (384d): **0.70**
- `BAAI/bge-large-en-v1.5` (1024d): likely ~0.75–0.80 (tighter similarity bands)
- Domain-finetuned model: needs fresh calibration

## Also update

When changing threshold in `settings.py`, also update:
- `infra/compose.yml` — `CLUSTERING_SIMILARITY_THRESHOLD` default
- `infra/compose.yml` — `CLUSTER_ASSIGN_THRESHOLD` default (usually same value)

## Files

- `services/analyst/anveshak/analyst/settings.py` — `clustering_similarity_threshold`
- `infra/compose.yml` — compose defaults for both analyst services
