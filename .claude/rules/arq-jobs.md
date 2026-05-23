# ARQ Jobs & Async Orchestration

Consolidated from 10 learned instincts. These apply to all ARQ job design and async workflows.

## Worker Design

- Load ML models once per worker process using module-level lazy globals
  Never load in `on_startup` unless all models are always used — avoids OOM on restart
  See: `learned/arq-worker-ml-singleton.md`

- Split monolithic services into lightweight scheduler (512 MiB) and heavy worker (6 GiB)
  Scheduler runs clustering, signal checks, orphan sweeps. Worker handles ML inference.
  Scheduler must NOT import ML libraries — verify import safety
  See: `learned/scheduler-worker-split.md`

## Job Chaining

- Enqueue child jobs from the end of a parent job, not from the scheduler
  Pass scope (e.g., `topic_id`) to avoid wasteful re-evaluation
  Always guard enqueue with result existence check: `if clusters: enqueue(...)`
  Register child jobs in `functions`, not `cron_jobs`
  See: `learned/causal-arq-job-chaining.md`

## Delivery

- Every service that inserts content_items MUST enqueue `analyse_content` directly
  Never rely on the orphan sweep as the primary delivery mechanism — it's a safety net
  The scraper missing this caused 243 permanently orphaned items over 8 days
  Wrap enqueue in try/except so Redis failures don't crash the insert path
  See: `learned/scraper-must-enqueue-not-rely-on-sweep.md`

## Reliability

- Periodic orphan sweep: query rows with null completion columns from the last 1 hour,
  every 5 minutes, in batches of 100. Runs in scheduler, not workers.
  Insert + enqueue is not atomic (Redis isn't transactional) — sweep catches missed jobs
  Sweep is SECONDARY to direct enqueue — not the primary mechanism
  See: `learned/orphan-sweep-safety-net.md`

- Circuit breaker: skip unhealthy sources at the SQL level using `health_status` column
  Database-backed status survives restarts and is visible to all workers
  Track state transitions with Prometheus counters. Automatic recovery via daily health checks
  See: `learned/circuit-breaker-sql-filter.md`

## Scheduling

- Track per-adapter timestamps (`last_adapter_poll_at`) instead of a single global interval
  Different adapters have different natural cadences (Telegram: 5min, X: 1hr, RSS: 30min)
  Base loop stays fast; individual adapters skip based on elapsed time
  See: `learned/per-adapter-interval-scheduling.md`

## Atomic State

- Use Redis `INCR` (atomic) for quota/budget guards — never GET→compare→SET (race condition)
  INCR then check, decrement on block to keep counter accurate
  Month-keyed keys with TTL auto-reset at boundaries
  See: `learned/redis-atomic-budget-guard.md`

## Replay Safety

- One-time writes: guard with sentinel column `WHERE generated_at IS NULL`
  Replayed ARQ jobs must not overwrite completed work
  See: `learned/immutable-write-idempotency.md`

- Cron jobs that insert rows: use UNIQUE constraint + `ON CONFLICT DO NOTHING`
  Prevents duplicate rows when cron fires while a previous run is still processing
  See: `learned/idempotent-cron-insert.md`

## Testing

- Flush ARQ job results from Redis at benchmark cleanup
  ARQ deduplicates by hashing function name + arguments — deterministic test UUIDs
  cause repeated jobs to be silently skipped. Production is unaffected (fresh uuid4)
  See: `learned/benchmark-arq-dedup-flush.md`
