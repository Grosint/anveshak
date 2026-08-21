---
name: analysis-jobs-db-source-of-truth
description: analysis_jobs PostgreSQL table is authoritative for job status — don't rely on ARQ Redis alone
type: feedback
---

ARQ jobs expire from Redis. The `analysis_jobs` PostgreSQL table is the **permanent,
authoritative record** of every job including its result.

**Pitfall:** using `arq_pool.job(job_id)` to poll job status:
```python
# WRONG — ArqRedis has no .job() method; also fails for seeded/completed jobs
job = arq_pool.job(job_id)
job_info = await job.info()
```
This fails with `AttributeError: 'ArqRedis' object has no attribute 'job'`.

**Correct pattern:** query `analysis_jobs` table directly:
```python
row = await db.fetchrow(
    "SELECT id, job_type, status, result, error, created_at, updated_at "
    "FROM analysis_jobs WHERE id = $1",
    job_id,
)
if row is None:
    raise HTTPException(status_code=404, detail="Job not found")

return {
    "job_id": str(row["id"]),
    "status": row["status"],
    "result": (json.loads(row["result"]) if isinstance(row["result"], str) else row["result"])
              if row["result"] else None,
    ...
}
```

**JSONB caveat:** asyncpg returns JSONB columns as Python dicts normally, but in some
configurations (e.g. when the column is returned via a plain SELECT, not a typed query)
it may return a JSON string. Always guard with `isinstance(row["result"], str)` check.

**How to apply:** any API endpoint that polls job status — query `analysis_jobs` table,
not ARQ Redis. ARQ Redis is ephemeral; the DB is permanent.
