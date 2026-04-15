# Causal ARQ Job Chaining

## When to load: any multi-stage ARQ pipeline where stage B is only meaningful after stage A completes

---

## The Problem

A follow-on job (e.g. cross-verification boost) needs to run after a parent job (e.g. clustering)
finishes — but on the same scoped data (same `topic_id`).

Two wrong approaches:
- **Cron timer**: Runs on a fixed schedule regardless of whether a clustering pass just happened.
  Scans all topics for fresh clusters even when nothing changed. Wastes DB work, can scan stale data.
- **Upstream enqueue without scoping**: Enqueuing a global sweep job ignores which topic was updated
  and forces the entire corpus to be re-evaluated on each trigger.

---

## The Pattern: Enqueue from the end of the parent job, pass scope

```python
# jobs.py

async def run_clustering(ctx: dict, topic_id: str) -> None:
    """HDBSCAN clustering for a topic."""
    db_pool = ctx["db_pool"]
    cluster_ids = await _run_clustering(topic_id, db_pool)

    from arq import create_pool
    redis = await create_pool(WorkerSettings.redis_settings)

    # 1. Fan out per-cluster label generation (existing pattern)
    for cluster_id in cluster_ids:
        await redis.enqueue_job("generate_cluster_label", cluster_id)

    # 2. Enqueue dependent job — only if clusters were actually formed
    if cluster_ids:
        await redis.enqueue_job("run_cross_verification", topic_id)
    #   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #   Causal guarantee: cross-verify only runs when fresh clusters exist.
    #   Scope is topic_id — only the relevant subset is queried.
```

```python
async def run_cross_verification(ctx: dict, topic_id: str) -> None:
    """Boost credibility of high-credibility sources in multi-platform clusters."""
    db_pool = ctx["db_pool"]
    updated = await run_cross_verification_update(db_pool, topic_id)
    log.info("jobs.run_cross_verification.done", topic_id=topic_id, updated=updated)
```

Register the child job in `WorkerSettings.functions` — NOT in `cron_jobs`:

```python
class WorkerSettings:
    functions = [
        run_clustering,
        run_cross_verification,   # NOT a cron — triggered by run_clustering
    ]
    cron_jobs = [
        arq.cron(run_daily_sweep, hour={2}),  # genuinely time-driven tasks go here
    ]
```

---

## When to use this vs. a cron

| Trigger type | Use case |
|---|---|
| **Post-job enqueue** (this pattern) | Stage B is only useful right after stage A. Data is scoped (topic_id, media_asset_id). |
| **Cron job** | Stage B is time-driven regardless of other activity (daily sweeps, report scheduling). |
| **Both** | Stage B has a "catch-up" cron for missed triggers + post-job enqueue for freshness. |

---

## Pitfall: the guard condition

Always guard the enqueue with `if result_exists:` — don't enqueue the child job when the parent
produced no output. Enqueueing a cross-verify job for a topic with no clusters wastes a DB round-trip
and produces confusing log entries.

```python
if cluster_ids:              # guard — only enqueue when parent produced output
    await redis.enqueue_job("run_cross_verification", topic_id)
```

---

## Implementation reference
`services/analyst/anveshak/analyst/jobs.py` — `run_clustering` → enqueues `run_cross_verification`
