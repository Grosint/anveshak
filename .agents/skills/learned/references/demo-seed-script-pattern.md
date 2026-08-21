---
name: demo-seed-script-pattern
description: Multi-stage demo seed scripts — SQL insert + ARQ enqueue + poll + report gen + PDF download
type: pattern
---

# Demo Seed Script Pattern

## Problem
Demo workflows require 8+ sequential stages across DB, Redis/ARQ workers, API,
and file output. Running them manually is error-prone. Running them all in parallel
saturates Ollama on CPU and causes timeouts.

## Pattern

```python
async def run():
    pool = await asyncpg.create_pool(POSTGRES_URL)

    # 1. DB seed (idempotent)
    print("[1/8] Seeding database...")
    async with pool.acquire() as conn:
        await _insert_topic(conn)      # ON CONFLICT DO NOTHING
        await _insert_sources(conn)    # + topic_sources linking
        content_ids = await _insert_content(conn)

    # 2. ARQ enqueue + poll (wait for workers)
    print("[2/8] NLP analysis...")
    await _enqueue_analysis_jobs(content_ids)  # arq:analyst queue
    await _poll_embeddings(pool, content_ids, timeout=240)

    # 3. Clustering (enqueue + poll)
    print("[3/8] Clustering...")
    await _enqueue_clustering(TOPIC_ID)
    await _poll_clusters(pool, TOPIC_ID, timeout=120)

    # 4. Pre-seed signals (deterministic demo)
    print("[4/8] Seeding signals...")
    await _seed_signals(pool)  # INSERT with investigative descriptions

    # 5-8. Auth → credibility adjust → report gen → PDF download
```

## Key Lessons

1. **Run ONE seed at a time on CPU** — 3 concurrent report generations all timeout
2. **Pre-seed signals** — don't rely on clustering to fire them; demo reliability > pipeline purity
3. **Idempotent inserts** — `ON CONFLICT DO NOTHING` allows reruns without cleanup
4. **Poll with timeout + logging** — `embeddings.waiting done=5 total=11 elapsed=25.1s`
5. **Explicit step counters** — `[3/8]` makes it obvious which step hangs
6. **PDF via reporter service** — port 8005, not API gateway port 8000
7. **Clean up failed reports** before re-running: `DELETE FROM reports WHERE generated_at IS NULL`
8. **`--replay` vs `--live`** flags with `ANVESHAK_ALLOW_LIVE=1` env guard

## Pitfalls
- `topic_sources` column is `added_at`, not `created_at` — verify schema before INSERT
- Postgres password from `.env` (`change-me-in-production`), not the default
- `arq.close()` is deprecated → use `arq.aclose()`
- Content items with duplicate `content_hash` are silently skipped — count returns may be 0
