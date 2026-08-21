# Pattern: ARQ Job Dedup Flush for Benchmark Re-runs

## When to load: benchmark framework, testing with repeated data, ARQ job debugging

---

## Problem

ARQ generates job IDs by hashing function name + arguments. When benchmark re-injects the same content (deterministic UUIDs from content_hash), ARQ sees the same job_id in Redis and skips it — "already done." Embeddings never get generated on subsequent runs.

## Solution

Flush all ARQ job results from Redis at benchmark cleanup:

```python
r = aioredis.from_url(settings.redis_url)
job_keys = [k async for k in r.scan_iter("arq:job:*")]
if job_keys:
    await r.delete(*job_keys)
```

## Why This Is Benchmark-Only

In production:
- Every scraped article gets a fresh `uuid4()` content_item_id
- That ID is never re-used
- `analyse_content("fresh-uuid")` is always a new job to ARQ
- No deduplication ever happens

The benchmark reuses deterministic IDs (same fixture text → same content_hash → same UUID) across runs.

## Pitfall: Don't flush in production

The flush deletes ALL ARQ job results — not just benchmark ones. Fine for benchmarks (isolated environment), catastrophic for production (loses job tracking for in-flight work).

## Files

- `benchmark/inject.py` — `cleanup()` function
