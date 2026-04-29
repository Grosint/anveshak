# Scheduler-Worker Split Pattern

## When to load: any task splitting a monolithic service into scheduler + worker

---

## Pattern

When a service mixes **lightweight reactive loops** (clustering, signal checks, polling)
with **heavy ML inference** (NLP, embedding, LLM), split into two containers from the
same Docker image:

### Scheduler (lightweight, single instance)
```yaml
analyst-scheduler:
  command: ["python", "-m", "anveshak.analyst.scheduler"]
  mem_limit: 512m    # no ML models — just asyncpg + numpy + arq
  depends_on: [postgres, redis]          # does NOT depend on ollama
```

Runs loops that need **global state** (all embeddings for a topic, all clusters):
- Clustering (HDBSCAN on DB-loaded vectors)
- Signal threshold checks
- Cross-topic convergence
- Orphan sweep (see `orphan-sweep-safety-net.md`)

After producing results, **enqueues downstream work to ARQ** instead of calling inline:
```python
# scheduler.py — cluster_loop
cluster_ids = await run_clustering(topic_id, pool)
for cid in cluster_ids:
    if await check_label_staleness(cid, pool):
        await redis.enqueue_job("generate_cluster_label", cid, _queue_name="arq:analyst")
await redis.enqueue_job("run_cross_verification", topic_id, _queue_name="arq:analyst")
```

### Worker (heavy, horizontally scalable)
```yaml
analyst-worker:
  command: ["python", "-m", "arq", "anveshak.analyst.jobs.WorkerSettings"]
  mem_limit: 6g
  deploy:
    replicas: ${ANALYST_WORKER_REPLICAS:-1}  # 1 on laptop, 4 on server
  depends_on: [postgres, redis, ollama]
```

Handles all per-item ML work via ARQ jobs. Loads models once in `on_startup`.

### Periodic batch work → ARQ cron (not scheduler loops)
```python
cron_jobs = [
    arq.cron(update_source_credibility, hour={3}),       # daily
    arq.cron(backfill_all_topics, hour={0, 6, 12, 18}),  # every 6h
]
```

**Why cron instead of loop:** These jobs need the ML worker's DB pool context,
can be expensive, get ARQ retry semantics, and can be paused by stopping the worker.

---

## Import Safety Rule

The scheduler must NEVER transitively import ML libraries. Verify:

| Safe to import in scheduler | Must NOT import |
|---|---|
| `clustering.py` (numpy, hdbscan) | `nlp.py` (spaCy) |
| `dedup.py` (numpy) | `embeddings.py` (sentence-transformers) |
| `labeller.check_label_staleness` (SQL only) | `translation.py` (NLLB/transformers) |
| `signal_engine.py` (SQL + thresholds) | `sentiment.py` (VADER) |
| `convergence.py` (SQL + pgvector) | `keywords.py` (YAKE) |

**Key insight:** `embeddings.py` defers `from sentence_transformers import ...` inside
`load_encoder()` (not at module level), so importing the module is safe. But importing
functions that CALL `encode_text()` will fail at runtime if `load_encoder()` wasn't called.

Separate code into **query layer** (safe anywhere) and **inference layer** (worker only).

---

## Memory Results (2026-04-29)

| Container | Memory | Limit | What's loaded |
|---|---|---|---|
| analyst-scheduler | 124 MiB | 512 MiB | asyncpg, arq, numpy, hdbscan |
| analyst-worker | 1.5 GiB | 6 GiB | spaCy x3, sentence-transformers, VADER, YAKE |

48x memory difference. Worker grows to ~5.6 GiB when NLLB translation loads lazily.

---

## When to apply

- Service has `asyncio.gather()` mixing reactive loops with ML inference
- NLP/ML blocks the event loop, starving signal checks and clustering
- Need horizontal scaling for ML work but not for coordination loops
- Different dependency chains (scheduler doesn't need Ollama/GPU)
