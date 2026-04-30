# Anveshak Product Audit: 4-Week Improvement Roadmap

**Date:** 2026-04-29
**Scope:** Full-stack audit for defence/LEA production deployment readiness

## Context

Full-stack audit of the Anveshak sovereign AI-OSINT platform, evaluated for deployment
to Indian defence forces and LEAs. Platform is ~85% feature-complete (M1-M5 working)
but has critical gaps blocking multi-analyst, air-gapped production deployment.

---

## What's Strong (Don't Break These)

- Immutability discipline (reports, audit logs, content hashes)
- 3-layer deduplication (content_hash, near-duplicate, pHash)
- Hardware independence (all ML params from env vars)
- Scheduler/worker split (124 MiB scheduler + 6 GiB ML worker)
- Offline geocoding (geonamescache, zero external calls)
- Signal engine (threshold-based, cross-topic convergence, WebSocket push)
- 50 well-designed DB indexes (partial, HNSW, trigram)

---

## Critical Weak Links (Blocks Deployment)

### 1. NO ACCESS CONTROL / RBAC

The single biggest gap. Currently all authenticated analysts see ALL topics, ALL sources,
ALL reports. There is zero authorization — only authentication.

- `users.role` column exists in DB but is **never checked** in any route
- No `topic_ownership` table — no way to assign topics to analysts
- No `require_role()` or `require_topic_access()` dependency in FastAPI
- An analyst can pause/archive/delete any other analyst's topics
- Reports generated on any topic are visible to everyone

**Risk:** In a defence context with compartmentalized intelligence, this is a showstopper.
Multiple units sharing one Anveshak instance would see each other's operations.

### 2. NO TOKEN REVOCATION / REFRESH

- JWT tokens valid for 8 hours with no revocation mechanism
- No refresh token — user must re-login after expiry
- No token blacklist — compromised tokens stay valid until natural expiry
- JWT secret defaults to `"change-me-in-production"` — if unchanged, all tokens forgeable
- WebSocket passes token as query parameter — visible in logs, browser history, proxy logs

**Risk:** Stolen token = 8 hours of unrestricted access with no kill switch.

### 3. NO DATA RETENTION POLICY

- No configuration for how long to keep content_items, media_assets, reports
- No hard-delete mechanism — `archived_at` soft-archives but data persists forever
- No table partitioning — 1M+ content_items will degrade query performance
- Media assets accumulate in Docker volume with no cleanup

**Risk:** Storage fills up silently. On a field-deployed single-machine setup, this is fatal.

### 4. NO USER ACTION AUDIT TRAIL

- credibility_audit_log exists (good) but that's it
- No logging of: who dismissed a signal, who viewed a report, who edited a source
- No data lineage — signals don't record which items triggered them
- Reports don't record which RAG chunks were included

**Risk:** In a defence/LEA context, "who saw what when" is not optional.

### 5. REPORTER-WORKER UNHEALTHY

- `reporter-worker` container showing `unhealthy` status
- No circuit breaker — if Ollama is slow, reporter hangs indefinitely
- `call_ollama_with_retry()` has only 2 retries with no exponential backoff

---

## WEEK 1: Security & Auth

### 1.1 RBAC Implementation

**Migration 010_rbac.py** — new `token_blocklist` table, CHECK constraint on `users.role`

**New file: `services/api/anveshak/api/auth/rbac.py`**
- `Role` enum: admin, analyst, viewer
- Permission map: admin (all), analyst (read+write+delete), viewer (read)
- `require_role(*roles)` FastAPI dependency factory
- `require_permission(permission)` dependency factory

**Modify: `services/api/anveshak/api/auth/jwt.py`**
- Add `jti` (UUID) + `role` to token payload
- `verify_token()` checks `jti` against Redis cache `blocklist:{jti}`, falls back to DB
- New `revoke_token(jti, user_id, expires_at)` function

**Modify: `services/api/anveshak/api/routes/auth.py`**
- Add `POST /api/v1/auth/logout` (revokes current token)
- Add `GET /api/v1/auth/me` (returns current user + role)
- Include `role` from DB in token creation

**Apply RBAC to all route files:**
- `routes/topics.py`: create/update = analyst+admin, read = all roles
- `routes/sources.py`: create/delete/update_credibility = analyst+admin, read = all
- `routes/signals.py`: acknowledge/dismiss = analyst+admin, list = all
- `routes/reports.py`: generate = analyst+admin, read = all
- `routes/vision.py`: analyse = analyst+admin

**New env vars:** `RBAC_ENABLED=true`, `TOKEN_BLOCKLIST_CLEANUP_S=3600`

### 1.2 Fix Reporter Worker (Currently Unhealthy)

**Modify: `services/reporter/anveshak/reporter/worker.py`**
- `call_ollama_with_retry()`: add exponential backoff (`2^attempt` seconds), increase to 3 retries
- Add Ollama health pre-flight: `GET /api/tags` before first attempt
- Catch `httpx.ConnectError` separately from LLM parse errors

**Modify: `services/reporter/anveshak/reporter/settings.py`**
- Add `ollama_retry_max=3`, `ollama_retry_backoff_base_s=2.0`, `ollama_health_check_timeout_s=10`

**Check:** `infra/compose.yml` reporter healthcheck — fix endpoint/command if broken

### 1.3 Frontend Auth

**Modify: `frontend/src/api/client.ts`**
- Add 403 handler in response interceptor (currently only handles 401)

### Week 1 Tests
- `tests/unit/test_rbac.py` — require_role with each role, 403 on insufficient
- `tests/unit/test_token_revocation.py` — revoked jti returns 401, cleanup removes expired
- `tests/unit/test_reporter_retry_backoff.py` — exponential backoff with mocked Ollama

### Week 1 Verification
1. `make migrate` — migration 010 applies
2. Create viewer user, attempt `POST /topics` — expect 403
3. Login, logout, reuse token — expect 401
4. `make ps` — reporter-worker shows healthy
5. `make test` passes

---

## WEEK 2: Data Governance

### 2.1 Retention Policy

**Migration 011_retention_policy.py** — add `retention_days` column to topics, create `retention_log` table

**New file: `services/analyst/anveshak/analyst/retention.py`**
- `run_retention_sweep(pool)` — per-topic batch-delete content older than `retention_days`
- Deletes in batches of `RETENTION_BATCH_SIZE` (avoid lock contention)
- Logs to `retention_log` table

**Modify: `services/analyst/anveshak/analyst/scheduler.py`**
- Add `retention_loop()` running every `RETENTION_CHECK_INTERVAL_S` (default 24h)

**New env vars:** `RETENTION_CHECK_INTERVAL_S=86400`, `RETENTION_DEFAULT_DAYS=365`, `RETENTION_MIN_DAYS=30`, `RETENTION_BATCH_SIZE=1000`

### 2.2 Audit Trail

**Migration 012_audit_trail.py** — create `audit_trail` table (user_id, action, resource_type, resource_id, details JSONB, ip_address, created_at, labels)

**New file: `services/api/anveshak/api/db/audit.py`**
- `log_action(conn, user_id, action, resource_type, resource_id, details, ip_address)`
- `get_audit_trail(conn, resource_type, resource_id, since, limit)`

**Modify all route files** — call `log_action()` after successful mutations:
- topic.create, topic.status_change, source.create, source.delete, source.credibility_update
- signal.acknowledge, signal.dismiss, report.generate

**New endpoint:** `GET /api/v1/system/audit-trail` (admin only)

### 2.3 Missing Indexes

**Migration 013_performance_indexes.py** — 5 new indexes:
```sql
idx_credibility_audit_changed_by (changed_by, created_at DESC)
idx_reports_topic_generated (topic_id, generated_at DESC) WHERE generated_at IS NOT NULL
idx_topic_sources_source (source_id)
idx_content_items_language_topic (language, topic_id)
idx_content_items_topic_captured (topic_id, captured_at DESC)
```

### 2.4 Backup Automation

**New file: `scripts/backup_db.sh`** — pg_dump with verification (`pg_restore --list`), retention cleanup (delete backups older than N days)

**New env vars:** `BACKUP_ENABLED=true`, `BACKUP_RETENTION_DAYS=30`, `BACKUP_PATH=/backups`

### Week 2 Tests
- `tests/unit/test_retention_sweep.py` — batch delete, age filtering, logging
- `tests/unit/test_audit_trail.py` — log_action inserts, query filters
- `tests/integration/test_retention_pipeline.py` — insert old content, sweep, verify gone

### Week 2 Verification
1. `make migrate` — 011, 012, 013 apply
2. Insert content_item 400 days old, run retention sweep — verify deleted
3. CRUD operations populate `audit_trail` table
4. `EXPLAIN ANALYZE` on signal dedup query — new index used
5. `scripts/backup_db.sh` creates dump, `pg_restore --list` succeeds

---

## WEEK 3: Resilience

### 3.1 Redis-Backed Rate Limiting

**Rewrite: `services/api/anveshak/api/middleware/rate_limit.py`**
- Replace in-memory `deque` with Redis sorted sets (`ZADD`/`ZRANGEBYSCORE`/`ZCARD`)
- Key pattern: `ratelimit:{category}:{identity}` with TTL
- Fail-open if Redis unreachable (log warning, allow request)
- Same tiers: login 10/min, vision 30/min, auth 120/min, anon 60/min

**New env var:** `RATE_LIMIT_BACKEND=redis`

### 3.2 DB Connection Resilience

**New shared utility (SDK or each service):**
```python
async def create_pool_with_retry(dsn, max_retries=5, backoff_base=2.0, **kwargs):
    # Exponential backoff on asyncpg.create_pool
```

**Apply to:** API main.py, analyst scheduler.py, social jobs.py, reporter worker.py

### 3.3 Social Adapter Token Refresh

**Modify: `services/social/anveshak/social/adapters/base.py`**
- Add `async def reauthenticate() -> bool` method

**Modify: `services/social/anveshak/social/jobs.py`**
- On `AdapterAuthError` during `collect()`: call `reauthenticate()`, retry once
- If reauth fails, mark adapter `needs_reauth=True`, skip until next cycle

### 3.4 Circuit Breakers

**New file: `services/api/anveshak/api/circuit_breaker.py`** (or in SDK)
- `CircuitBreaker(name, failure_threshold=5, recovery_timeout_s=120)`
- States: closed -> open (after N failures) -> half_open (after timeout) -> closed (on success)

**Apply to:**
- `services/reporter/anveshak/reporter/worker.py` — wrap Ollama calls
- `services/social/anveshak/social/jobs.py` — per-adapter breakers

**New env vars:** `CIRCUIT_BREAKER_FAILURE_THRESHOLD=5`, `CIRCUIT_BREAKER_RECOVERY_TIMEOUT_S=120`

### Week 3 Tests
- `tests/unit/test_rate_limit_redis.py` — sliding window with fakeredis, 429 on exceed, fail-open on disconnect
- `tests/unit/test_db_pool_retry.py` — mock pool failure N times, verify backoff
- `tests/unit/test_circuit_breaker.py` — state transitions (closed->open->half_open->closed)
- `tests/unit/test_adapter_reauth.py` — auth failure triggers reauth + retry

### Week 3 Verification
1. Restart API, repeat rate-limited requests — counter persists (Redis)
2. Stop PostgreSQL, start API — retries and connects when PG returns
3. Stop Ollama, submit 5 report requests, 6th fails immediately (circuit open)
4. `make test` passes

---

## WEEK 4: Scale & Deploy

### 4.1 Clustering Guards

**Modify: `services/analyst/anveshak/analyst/clustering.py`**
- Guard: if items > `CLUSTERING_MAX_ITEMS`, sample most recent N items
- Timeout: wrap HDBSCAN with `asyncio.wait_for(clustering_timeout_s)`
- Prometheus metric: `analyst_clustering_items_sampled_total`

**New env vars:** `CLUSTERING_MAX_ITEMS=10000`, `CLUSTERING_TIMEOUT_S=300`

### 4.2 k3s Hardening

**New files:**
- `infra/k3s/networkpolicy.yml` — default deny + explicit allow (api->postgres, frontend->api, etc.)
- `infra/k3s/reporter.yml`, `social.yml`, `frontend.yml` — missing service manifests

**Modify existing k3s manifests:**
- Add `securityContext: runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation: false`
- Add liveness probes to all pods
- Add PodDisruptionBudget for api (minAvailable: 1)
- Update `kustomization.yml` to include all new resources

### 4.3 Frontend Offline Mode

**New files:**
- `frontend/src/sw.ts` — service worker (cache-first for static, network-first for API with cache fallback)
- `frontend/src/components/ui/OfflineBanner.tsx` — offline/online status indicator
- `frontend/public/manifest.json` — PWA manifest

**Modify: `frontend/vite.config.ts`** — add `vite-plugin-pwa`
**Modify: `frontend/src/api/client.ts`** — offline detection + cached response fallback

### 4.4 Backup Verification

**New file: `scripts/backup_verify.sh`** — restore to temp DB, run table/row checks, drop temp DB

**New env vars:** `BACKUP_VERIFY_ENABLED=true`

### Week 4 Tests
- `tests/unit/test_clustering_guard.py` — sampling, timeout, metrics
- `tests/e2e/test_k3s_deploy.py` — pods reach Ready, NetworkPolicy enforced

### Week 4 Verification
1. Seed 15K items in one topic, trigger clustering — completes < 5min, log shows sampling
2. `kubectl apply -k infra/k3s/` — all pods Ready, network policies active
3. Frontend: disconnect network in DevTools — cached pages still render, banner shows
4. `scripts/backup_db.sh && scripts/backup_verify.sh` — exit 0

---

## Summary Tables

### Migration Summary

| Migration | Week | Purpose |
|-----------|------|---------|
| 010_rbac | 1 | token_blocklist, role constraint |
| 011_retention_policy | 2 | retention_days, retention_log |
| 012_audit_trail | 2 | audit_trail table |
| 013_performance_indexes | 2 | 5 new composite/partial indexes |

### New Env Vars Summary

| Variable | Default | Week |
|----------|---------|------|
| RBAC_ENABLED | true | 1 |
| TOKEN_BLOCKLIST_CLEANUP_S | 3600 | 1 |
| RETENTION_CHECK_INTERVAL_S | 86400 | 2 |
| RETENTION_DEFAULT_DAYS | 365 | 2 |
| RETENTION_MIN_DAYS | 30 | 2 |
| RETENTION_BATCH_SIZE | 1000 | 2 |
| BACKUP_ENABLED | true | 2 |
| BACKUP_RETENTION_DAYS | 30 | 2 |
| BACKUP_PATH | /backups | 2 |
| RATE_LIMIT_BACKEND | redis | 3 |
| CIRCUIT_BREAKER_FAILURE_THRESHOLD | 5 | 3 |
| CIRCUIT_BREAKER_RECOVERY_TIMEOUT_S | 120 | 3 |
| CLUSTERING_MAX_ITEMS | 10000 | 4 |
| CLUSTERING_TIMEOUT_S | 300 | 4 |
| BACKUP_VERIFY_ENABLED | true | 4 |

### Critical Files to Modify

| File | Week | Change |
|------|------|--------|
| `services/api/anveshak/api/auth/jwt.py` | 1 | jti + role in token, revocation |
| `services/api/anveshak/api/routes/*.py` | 1 | RBAC on all mutating endpoints |
| `services/reporter/anveshak/reporter/worker.py` | 1,3 | Retry backoff, circuit breaker |
| `services/api/anveshak/api/middleware/rate_limit.py` | 3 | Rewrite to Redis-backed |
| `services/analyst/anveshak/analyst/scheduler.py` | 2 | Retention loop |
| `services/analyst/anveshak/analyst/clustering.py` | 4 | Max-items guard, timeout |
| `services/social/anveshak/social/jobs.py` | 3 | Reauth + circuit breaker |

---

## Post-Beta Improvements (Not in 4-week scope)

- Intelligence classification markings on reports (UNCLASSIFIED/RESTRICTED/SECRET)
- Report versioning (track how intelligence evolved)
- Social conversation threading
- Bot detection for social adapters
- Engagement metrics (likes/retweets) for weighted analysis
- Dark web/Tor source adapter
- Batch image upload in vision module
- Credibility score reasoning widget in frontend
- Incremental scraping (ETag/Last-Modified)
- Source health-based scheduling (backoff dead sources)
- CSRF protection, mTLS between services
- Frontend test coverage from 30% to 80%

---

## End-to-End Verification (After All 4 Weeks)

1. `make test` — all unit + integration tests pass
2. `make demo-check` — full 8-step demo arc passes
3. RBAC test — create 2 analysts, verify topic isolation
4. Load test — 15K items in one topic, clustering completes < 5min
5. Kill Ollama mid-report — circuit breaker fires, analyst gets error not hang
6. `make backup && make restore` — round-trip succeeds
7. Token revocation — logout, old token rejected
8. Retention — old content auto-deleted after configured days
9. Audit trail — all mutations logged with user + IP
10. k3s — pods Ready, NetworkPolicy blocks unauthorized access
