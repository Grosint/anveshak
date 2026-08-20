# Source Adapter SDK

## When to load: any task involving creating or modifying a source adapter

> See also: `.claude/skills/learned/additive-backfill-join-table.md` — pattern for associating existing content with new topics without copying rows
> See also: `.claude/skills/learned/identifier-type-wiring-checklist.md` — 13-file checklist for adding a new identifier type (backend, frontend, migration, tests)
> See also: `.claude/skills/learned/cross-service-metadata-enrichment.md` — API enqueues ARQ job on social worker to fetch profile metadata; fail-open pattern
> See also: `.claude/skills/learned/keyword-tag-granularity-mismatch.md` — normalize multi-word keywords to single-word tags before array overlap; silent zero-result failure
> See also: `.claude/skills/learned/unified-discriminator-table.md` — single discovered_sources table with discovery_method discriminator vs per-method tables
> See also: `.claude/skills/learned/migration-not-visible-in-container.md` — docker cp or rebuild before alembic upgrade; file not visible in running container
> See also: `.claude/skills/learned/telethon-peer-id-extraction.md` — str() on Telethon TypePeer produces repr, not numeric ID; use utils.get_peer_id()
> See also: `.claude/skills/learned/adapter-circuit-breaker-redis.md` — Redis-backed circuit breaker for adapter failure isolation
> See also: `.claude/skills/learned/isc-count-sources-not-platforms.md` — ISC must count distinct source_id, not platform; consolidating to RSS collapses ISC to 1
> See also: `.claude/skills/learned/source-consolidation-cascading-breakage.md` — changing source platforms silently breaks downstream metrics (ISC, signals, credibility)
> See also: `.claude/skills/learned/credential-refresh-before-circuit-break.md` — attempt refresh_credentials() before circuit breaking
> See also: `.claude/skills/learned/startup-credential-validation.md` — validate env vars at startup, not at first API call
> See also: `.claude/skills/learned/cross-topic-join-table-queries.md` — every topic-scoped SQL must include topic_content_items OR subquery; backfilled items are invisible otherwise
> See also: `.claude/skills/learned/global-sources-org-visibility.md` — sources are global; use org_sources join table for org-scoped visibility, not org_id on sources
> See also: `.claude/skills/learned/org-id-root-tables-only.md` — add org_id to root tables only; children inherit via topic_id FK
> See also: `.claude/skills/learned/seed-sql-must-match-migration.md` — after adding NOT NULL columns, update ALL seed SQL INSERTs
> See also: `.claude/skills/learned/archive-then-delete-retention.md` — archive to JSONL.gz before deleting from PostgreSQL; record in tracking table; disabled by default
> See also: `.claude/skills/learned/scheduler-prioritized-topic-selection.md` — HAVING + ORDER BY pending DESC + LIMIT for scheduler loops; skip idle topics
> See also: `.claude/skills/learned/url-level-media-dedup.md` — in-memory URL set per scrape job to skip duplicate media downloads
> See also: `.claude/skills/learned/uv-workspace-restructure.md` — safe sequence for moving packages; namespace flattening limits
> See also: `.claude/skills/learned/redis-atomic-budget-guard.md` — X/Twitter spend guard (atomic Redis INCR, monthly TTL)
> See also: `.claude/skills/learned/per-adapter-interval-scheduling.md` — independent poll cadence per adapter
> See also: `.claude/skills/learned/phase-check-pitfalls.md` — pitfall 4 (thread topic_id through collect), pitfall 5 (wire every setting), pitfall 6 (disabled warning)
> See also: `.claude/skills/learned/causal-arq-job-chaining.md` — enqueue dependent job at end of parent job instead of using a cron timer; scope by topic_id
> See also: `.claude/skills/learned/docker-compose-build-context.md` — context: path is relative to compose file, not CWD; `infra/compose.yml` needs `context: ..`
> See also: `.claude/skills/learned/seed-sql-schema-sync.md` — seed SQL drifts from schema silently; verify with \d tablename before debugging logic
> See also: `.claude/skills/learned/makefile-infrastructure-first-setup.md` — start infra before app services; health-poll instead of sleep; `@printf` pitfall in Make shell blocks
> See also: `.claude/skills/learned/compose-overlay-core-feature-trap.md` — core features must be in base compose.yml; overlays only for GPU/optional services
> See also: `.claude/skills/learned/nginx-dynamic-dns-resolver.md` — resolver 127.0.0.11 + set $upstream to avoid 502s after container restarts
> See also: `.claude/skills/learned/volume-mounted-models-silent-failure.md` — empty volume = silent 0.0 scores; need make download-models + health check
> See also: `.claude/skills/learned/post-embedding-relevance-gate.md` — filter off-topic scraped content via topic query embedding similarity before clustering
> See also: `.claude/skills/learned/orphan-sweep-safety-net.md` — safety net for content_items where enqueue_job("analyse_content") failed after DB insert
> See also: `.claude/skills/learned/scraper-must-enqueue-not-rely-on-sweep.md` — scraper must enqueue analyse_content directly; orphan sweep is safety net, not primary delivery
> See also: `.claude/skills/learned/scraper-source-page-not-content.md` — when follow_links=True, source URL is for link discovery only, never stored as content
> See also: `.claude/skills/learned/redis-url-dedup-sha256-ttl.md` — Redis URL dedup with sha256 key, 24h TTL, fail-open; mark after insert not before fetch
> See also: `.claude/skills/learned/quality-ratio-bypass-on-length.md` — bypass clean/raw ratio check if clean_text >= 500 chars; must fire AFTER paywall/nav-icon gates
> See also: `.claude/skills/learned/per-topic-relevance-auto-calibration.md` — auto-calibrate relevance threshold per topic from score distribution percentile
> See also: `.claude/skills/learned/scheduler-worker-split.md` — analyst split into scheduler (clustering/signals) + ARQ worker (NLP/embedding); import chain safety
> See also: `.claude/skills/learned/rss-fetch-paywall-validation.md` — validate fetched content before replacing RSS summary; paywall indicator counting
> See also: `.claude/skills/learned/quality-gate-all-consumers.md` — apply quality/relevance filters at every consumption point, not just clustering
> See also: `.claude/skills/learned/compose-environment-consistency.md` — feature flag env vars must be in compose environment block; silently defaults to false
> See also: `.claude/skills/learned/docker-exec-integration-test.md` — host→docker cp→docker exec→JSON stdout pattern for testing real code paths in containers
> See also: `.claude/skills/learned/container-integration-test-orchestration.md` — single make test-integration runs host DB tests + container model tests
> See also: `.claude/skills/learned/httpx-socks-optional-extra.md` — httpx[socks] required for Tor SOCKS5; unit tests don't catch missing optional extras
> See also: `.claude/skills/learned/test-db-same-container-isolation.md` — anveshak_test DB in same container; pool-based tests can't use transaction rollback
> See also: `.claude/skills/learned/fk-cascade-teardown-order.md` — full 13-table delete order for topic/source teardown; circular FK trap with narrative_clusters
> See also: `.claude/skills/learned/pytest-exit-safety-guard.md` — pytest.exit() to hard-block tests from running against production DB
> See also: `.claude/skills/learned/arq-queue-name-all-callers.md` — every enqueue_job must match target worker's queue_name; grep ALL callers
> See also: `.claude/skills/learned/compose-worker-for-every-arq-scheduler.md` — every service calling enqueue_job needs a matching worker container in compose
> See also: `.claude/skills/learned/local-file-media-downloader.md` — download_media_asset() local file support; path validation pitfalls; volume permission issues
> See also: `.claude/skills/learned/sidecar-bridge-redis-buffer.md` — Node.js sidecar → RPUSH Redis → Python LPOP pattern for cross-language adapters
> See also: `.claude/skills/learned/baileys-405-version-override.md` — Baileys 405 Connection Failure fix; version array [2,3000,1033893291] override

---

### SourceAdapterBase — canonical contract (Phase 3 implemented)

```python
from anveshak.social.adapters.base import SourceAdapterBase, RawItem
from typing import AsyncIterator

class MyAdapter(SourceAdapterBase):
    adapter_id = "myadapter-v1"    # kebab-case
    platform = "myplatform"        # matches sources.platform column
    adapter_version = "1.0.0"

    async def authenticate(self) -> None:
        if not settings.myadapter_enabled:
            log.warning("social.adapter_disabled", adapter=self.adapter_id,
                        hint="Set MYADAPTER_ENABLED=true to activate")
            return                                    # pitfall 6: always log on disabled
        # ... load credentials, raise AdapterAuthError on failure

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,             # REQUIRED — used for media/{topic_id}/... path
    ) -> AsyncIterator[RawItem]:
        # yield RawItem per piece of content found
        ...

    async def health(self) -> dict:
        return {"status": "HEALTHY"|"DEGRADED"|"DOWN", "checked_at": ISO8601}
```

### collect() signature — why topic_id is required

`topic_id` must be passed through to leaf helpers that download media (pitfall 4).
Media path: `media/{topic_id}/{YYYY}/{MM}/{DD}/{content_hash}.{ext}` (criteria 3.10).

### RawItem — what collect() yields

```python
RawItem(
    raw_text="...",             # untransformed text from platform
    url="https://...",          # canonical URL for this item
    platform="reddit",          # matches sources.platform value
    captured_at=datetime.now(UTC),  # timezone-aware — never naive
    source_handle="r/worldnews",    # matches sources.url_or_handle
    media_urls=["https://..."],     # images/videos for Phase 4 ingestion
    language=None,              # None = detect in analyst pipeline
)
```

### Ingesting a RawItem (call from jobs.py, not from collect())

```python
from anveshak.social.ingest import ingest_raw_item

new = await ingest_raw_item(raw, topic_id, db_pool, arq_pool, adapter_id)
# Returns True = new row inserted + analyse_content ARQ job enqueued
# Returns False = content_hash already existed (dedup hit, no-op)
```

### Content hash (mandatory, handled by RawItem)
```python
# RawItem.content_hash() computes sha256(normalise(raw_text))
# normalise = lowercase + collapse whitespace
# Same algorithm as scraper/normalise.py — consistent dedup across services
```

### X/Twitter adapter — spend guard (CRITICAL — use redis-atomic-budget-guard.md)
```python
# CORRECT — atomic Redis INCR, never a read-compare-write
allowed = await spend_guard.check_and_increment()
if not allowed:
    return   # hard stop — do NOT make the API call

# WRONG — race condition
if self._monthly_reads < cap:
    self._monthly_reads += 1   # two workers can both pass
```

### Error hierarchy
| Exception | When to raise |
|---|---|
| AdapterAuthError | Credentials invalid/expired |
| AdapterRateLimitError | Source rate-limited |
| AdapterDegradedError | Partial data / impaired |

### SourceAdapterConformanceSuite — 5 required assertions per adapter

Every new adapter must pass all 5 in `tests/unit/test_social_conformance.py`:
1. `assert_platform_defined` — platform attr exists and is a known value
2. `assert_content_hash_deterministic` — same input → same 64-char hex SHA-256
3. `assert_url_non_empty` — url field is a non-empty string
4. `assert_captured_at_timezone_aware` — captured_at.tzinfo is not None
5. `assert_raw_item_platform_matches` — RawItem.platform == adapter.platform
