---
name: onboard
description: "Orientation on a running Anveshak stack, and triage of a pipeline that has stopped moving. Reports which containers are up, how deep each ARQ queue is, and which stage the work is held at. Use when arriving at a deployment you have not looked at yet, when scraped content stops appearing, when a queue looks backed up, or when a job never finishes."
---

# Onboard

An item travels five stages from source to report.
This skill walks the stages in order and ends by naming the single stage the work is **held** at.

Run it against a stack that is already up.
It reads state and never restarts, rebuilds, or re-enqueues anything.

## Stage map

| Stage | Work | Container | ARQ queue | Liveness key |
|-------|------|-----------|-----------|--------------|
| 1 | Web, RSS, darkweb scraping | `scrape-web-worker` | `arq:scraper` | `arq:scraper:health-check` |
| 1 | Social adapter polling | `scrape-social-worker` | `arq:social` | `arq:social:health-check` |
| 1 | Poll scheduling | `scrape-web-scheduler`, `scrape-social-scheduler` | none | `anveshak:scheduler:scrape-web:health-check`, `anveshak:scheduler:scrape-social:health-check` |
| 2 | NLP, embedding, identifiers, quality | `analyse-worker` | `arq:analyst` | `arq:analyst:health-check` |
| 3 | Clustering, signals, convergence, orphan sweep | `analyse-scheduler` | none | HTTP `localhost:8007/health` |
| 4 | Deepfake and image analysis | `analyse-vision-worker` | `arq:vision` | `arq:vision:health-check` |
| 5 | LLM report generation | `report-worker` | `arq:reporter` | `arq:reporter:health-check` |

Every queue is explicitly named, because a worker on the default queue steals another service's jobs.
A job sitting in a queue no container listens on is the most common cause of a stage that looks alive and moves nothing.

## 1. Containers

Run `make ps` for state and `make health` for the HTTP endpoints.

A worker's healthcheck is `sdk/arq_health.sh`, which probes that worker's heartbeat key in Redis.
`healthy` therefore means the event loop ticked within the last 30 seconds, not merely that PID 1 is alive.
A **wedged** worker, one whose loop is blocked by CPU-bound work, goes `unhealthy` on its own rather than passing the probe.
Treat `unhealthy` on a worker as a blocked event loop until the logs say otherwise.

Done when every container in the stage map has a state, and each missing, `restarting`, or `unhealthy` one is recorded against its stage.

## 2. Queues

ARQ holds pending jobs in a sorted set per queue, so depth is `ZCARD`:

```bash
for q in arq:scraper arq:social arq:analyst arq:vision arq:reporter; do
  printf '%-14s %s\n' "$q" "$(docker exec anveshak-redis-1 redis-cli ZCARD "$q")"
done
```

That count is queued plus deferred work.
A job currently executing has left the sorted set, so count running work separately:

```bash
docker exec anveshak-redis-1 redis-cli --scan --pattern 'arq:in-progress:*' | wc -l
```

The two numbers together separate the two failure shapes:

- Depth high, in-progress zero: nothing is consuming the queue. Go back to that queue's container.
- Depth high, in-progress non-zero: the stage is slow, not stuck. Read its logs for the job it is on.
- Depth zero, nothing arriving downstream: the producer never enqueued. Stage is upstream of this one.

Done when all five depths and the in-progress count are recorded.

## 3. Where the work is held

`uv run python scripts/pipeline_health.py --hours 24` prints the stage report: container liveness, queue depth, insert-against-embed flow rate, per-source staleness, and cluster freshness.
Read its `STAGE CRITICALS` block first, since it already correlates a queue depth with the container that owns it.

Then read the dead letter queue, which the stage report does not cover:

```bash
docker exec anveshak-postgres-1 psql -U anveshak -d anveshak -c \
  "SELECT queue_name, function_name, COUNT(*), MAX(failed_at) \
   FROM failed_jobs WHERE failed_at > NOW() - INTERVAL '24 hours' \
   GROUP BY queue_name, function_name ORDER BY 3 DESC"
```

A stage with a healthy container, an empty queue, and rows in `failed_jobs` is failing rather than holding.

Symptom to stage:

- `content_items` rising, `embedding` NULL: stage 2. The analyst never received the item, or it received it and failed. Check `arq:analyst` depth against `failed_jobs`, then `.agents/skills/learned/references/scraper-must-enqueue-not-rely-on-sweep.md`.
- Embeddings present, no new clusters: stage 3. `analyse-scheduler` is down, or the orphan sweep is carrying the load alone. See `.agents/skills/learned/references/orphan-sweep-safety-net.md`.
- Vision scores uniformly 0.0 with no error: stage 4 model volume is empty. See `.agents/skills/learned/references/volume-mounted-models-silent-failure.md`.
- Report queued and never finishing: stage 5. Ollama on CPU returns 500 on a large prompt. See `.agents/skills/learned/references/ollama-500-large-prompt-cpu.md`.
- A source reported `NEVER_SCRAPED`: stage 1 adapter auth or access, which is upstream of the pipeline rather than part of it.
- Every stage healthy but the schema looks wrong: migrations did not run inside the container. See `.agents/skills/learned/references/migration-not-visible-in-container.md`.

Done when each of the five stages carries a verdict of moving, held, or failing, backed by the number that decided it.

## 4. Report

Print the stage table with one row per stage: container state, queue depth, verdict.
Close with the single blocking stage and the evidence that names it, or state that no stage is blocking.
Stop there.
Repairing the stage is separate work, and the person reading this needs the diagnosis before the fix.
