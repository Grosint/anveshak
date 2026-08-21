# Pattern: Realistic Test Embeddings for Clustering

## When to load: writing clustering tests, debugging test failures in similarity-based algorithms, creating synthetic ML test data

---

## Problem

Test embeddings using uniform vectors like `[0.1]*384` produce degenerate clustering results regardless of algorithm. Two specific failures:

### 1. Not L2-normalized

Sentence-transformers outputs unit vectors. `[0.1]*384` has L2 norm ~1.96, so `dot(a, b) > 1.0` and distances go negative. Clustering algorithms produce garbage.

### 2. No per-dimension diversity

Even after normalization, uniform vectors have identical values in every dimension. Random perturbation produces nearly identical pairwise distances — the algorithm sees all pairs as equidistant and can't distinguish clusters from noise.

## Solution

Use diverse, seeded, L2-normalized base vectors:

```python
def _make_narrative_base(seed: int, dim: int = 384) -> np.ndarray:
    """Deterministic diverse base vector (mimics sentence-transformers)."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    return vec / np.linalg.norm(vec)

def _make_article(base: np.ndarray, rng: np.random.RandomState, noise: float = 0.03) -> np.ndarray:
    """Perturb base to simulate an article (cosine sim ~0.88-0.95 to base)."""
    perturbed = base + rng.uniform(-noise, noise, size=len(base))
    return (perturbed / np.linalg.norm(perturbed)).astype(np.float32)
```

### Calibration table

| Noise | Intra-cluster cosine sim | Use case |
|-------|-------------------------|----------|
| 0.02 | ~0.93-0.97 | Very tight cluster, near-duplicates |
| 0.03 | ~0.88-0.95 | Same narrative, realistic spread |
| 0.05 | ~0.75-0.90 | Same broad topic, some divergence |

### Key rules

1. **Always L2-normalize** — both base and perturbed vectors
2. **Use `np.random.RandomState(seed)`** — deterministic, reproducible tests
3. **Use different seeds per narrative** — ensures inter-narrative similarity is low (~0.02-0.30)
4. **Verify similarity math in test** — assert pairwise sims match expectations before testing the algorithm

## Pitfall: Wasted debugging time

In this session, we spent 4 iterations debugging test failures that were all caused by uniform base vectors. The clustering algorithm was correct — the test data was degenerate. Always verify test data realism before blaming the algorithm.

## Files

- `tests/unit/test_leiden_clustering.py` — `_make_narrative_base()`, `_make_article()`
- `tests/integration/test_cluster_signal_pipeline.py` — `_random_base()`, `_similar_embedding()`
