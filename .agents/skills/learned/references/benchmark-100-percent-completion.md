# Pattern: Benchmark Must Wait for 100% Pipeline Completion

## When to load: modifying benchmark framework, debugging inconsistent benchmark results

---

## Problem

The benchmark accepted 90% embedding completion (`done >= total * 0.9`) then immediately
triggered clustering. Topics whose items were in the remaining 10% never got clustered —
clustering runs once and doesn't retry for topics with incomplete data.

This made benchmark results non-deterministic: which topics happened to complete first
affected recall. Runs varied by ±10% recall depending on embedding order.

## Solution

Wait for 100% completion in `benchmark/run.py`:
```python
# Before (broken):
if total > 0 and done >= total * 0.9:

# After (correct):
if total > 0 and done >= total:
```

## Why 90% Was Wrong

The 90% threshold was added to handle items filtered by the quality gate (which sets
`content_quality = 'low_quality'` instead of generating embeddings). But quality-filtered
items still count in `COUNT(*)` — they have NULL embeddings, inflating the denominator.

The fix: wait for 100%. Quality-filtered items eventually get their quality column set,
and the embedding count converges. The benchmark timeout (1800s) is the safety net.

## Pitfall: Redis FLUSHDB During Benchmark

Never run `redis-cli FLUSHDB` while containers are running. It kills:
- ARQ worker heartbeats → workers stop picking up jobs
- ARQ job dedup cache → but also the worker registration

Use `benchmark-clean` (selective `arq:job:*` deletion) or restart containers cleanly.

## Files

- `benchmark/run.py` — `wait_for_embeddings()` function
