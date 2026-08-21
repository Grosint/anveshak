# ARQ Queue Name Must Match at All Call Sites

## Problem

Social `ingest_raw_item()` enqueued `analyse_content` without `_queue_name="arq:analyst"`.
Analyst worker listens on `arq:analyst` queue. Jobs went to default queue — analyst never
saw them. Content was inserted but never embedded, clustered, or analyzed.

Scraper had the correct `_queue_name` — only social was wrong. Bug was invisible because
social-worker didn't exist yet (jobs expired in Redis silently).

## Rule

When enqueuing a job, the `_queue_name` must match the target worker's `WorkerSettings.queue_name`.
Grep ALL callers of `enqueue_job("function_name")` and verify they all use the same queue.

Checklist after adding any `enqueue_job` call:
1. Find the worker that processes this function: `grep -r "functions.*=.*function_name"`
2. Find that worker's queue_name: check `WorkerSettings.queue_name`
3. Verify YOUR enqueue uses `_queue_name=` matching step 2
4. Grep all OTHER callers of the same function — verify they match too

## Detection

- `pipeline_health.py` flow rate check: items inserted vs items embedded
- If ratio < 50% → queue mismatch or worker down
- ARQ queue depth > 0 on a queue with no worker → immediate flag

## Extended (2026-06-28)

Found 5 MORE instances of this bug class in same codebase:
- Social WorkerSettings had NO queue_name (defaulted to arq:queue)
- Scheduled report cron and reporter main.py had NO _queue_name on enqueue
- Assessment endpoint used literal "arq:queue"

All caught by `tests/contracts/test_service_contracts.py` source-scan contract tests.
Every WorkerSettings MUST have explicit `queue_name`. Every `enqueue_job()` call
MUST have explicit `_queue_name`. No service may rely on ARQ default queue.

## See also

- `contract-test-source-scan.md` — source-scan detection pattern
- `scheduler-worker-split.md` — correct queue usage pattern
- `scraper-must-enqueue-not-rely-on-sweep.md` — every inserter must enqueue directly
