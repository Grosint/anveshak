# ARQ Jobs & Async Orchestration

10 learned instincts. All ARQ job design + async workflows.

## Worker Design

- Load ML models once per worker via module-level lazy globals
  Never in `on_startup` unless all models always used — OOM risk
  See: `learned/arq-worker-ml-singleton.md`

- Split into lightweight scheduler (512 MiB) + heavy worker (6 GiB)
  Scheduler: clustering, signals, orphan sweeps. Worker: ML inference.
  Scheduler must NOT import ML libs — verify import safety
  See: `learned/scheduler-worker-split.md`

## Job Chaining

- Enqueue children from end of parent job, not scheduler
  Pass scope (e.g., `topic_id`) — avoid wasteful re-eval
  Guard: `if clusters: enqueue(...)`
  Register in `functions`, not `cron_jobs`
  See: `learned/causal-arq-job-chaining.md`

## Delivery

- Every service inserting content_items MUST enqueue `analyse_content` directly
  Orphan sweep = safety net, not primary mechanism
  Missing this caused 243 orphaned items over 8 days
  Wrap enqueue in try/except — Redis failure must not crash insert
  See: `learned/scraper-must-enqueue-not-rely-on-sweep.md`

## Reliability

- Orphan sweep: null completion rows from last 1hr, every 5min, batches of 100. Runs in scheduler.
  Insert+enqueue not atomic (Redis non-transactional) — sweep catches misses
  SECONDARY to direct enqueue
  See: `learned/orphan-sweep-safety-net.md`

- Circuit breaker: skip unhealthy sources via SQL `health_status` column
  DB-backed status survives restarts, visible to all workers
  Prometheus counters on transitions. Auto-recovery via daily health checks
  See: `learned/circuit-breaker-sql-filter.md`

## Scheduling

- Per-adapter timestamps (`last_adapter_poll_at`) not single global interval
  Cadences differ (Telegram: 5min, X: 1hr, RSS: 30min)
  Base loop fast; adapters skip on elapsed time
  See: `learned/per-adapter-interval-scheduling.md`

## Atomic State

- Redis `INCR` (atomic) for quota/budget — never GET→compare→SET (race condition)
  INCR then check, decrement on block
  Month-keyed keys with TTL auto-reset
  See: `learned/redis-atomic-budget-guard.md`

## Replay Safety

- One-time writes: sentinel `WHERE generated_at IS NULL`
  Replayed jobs must not overwrite completed work
  See: `learned/immutable-write-idempotency.md`

- Cron inserts: UNIQUE constraint + `ON CONFLICT DO NOTHING`
  Prevents dupes when cron fires during previous run
  See: `learned/idempotent-cron-insert.md`

## Testing

- Flush ARQ results from Redis at benchmark cleanup
  ARQ dedups by hashing fn+args — deterministic test UUIDs cause silent skips
  Prod unaffected (fresh uuid4)
  See: `learned/benchmark-arq-dedup-flush.md`