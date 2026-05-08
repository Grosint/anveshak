# Source Adapter SDK

## When to load: any task involving creating or modifying a source adapter

> See also: `learned/additive-backfill-join-table.md` — pattern for associating existing content with new topics without copying rows
> See also: `learned/url-level-media-dedup.md` — in-memory URL set per scrape job to skip duplicate media downloads
> See also: `learned/uv-workspace-restructure.md` — safe sequence for moving packages; namespace flattening limits
> See also: `learned/redis-atomic-budget-guard.md` — X/Twitter spend guard (atomic Redis INCR, monthly TTL)
> See also: `learned/per-adapter-interval-scheduling.md` — independent poll cadence per adapter
> See also: `learned/phase-check-pitfalls.md` — pitfall 4 (thread topic_id through collect), pitfall 5 (wire every setting), pitfall 6 (disabled warning)
> See also: `learned/causal-arq-job-chaining.md` — enqueue dependent job at end of parent job instead of using a cron timer; scope by topic_id
> See also: `learned/docker-compose-build-context.md` — context: path is relative to compose file, not CWD; `infra/compose.yml` needs `context: ..`
> See also: `learned/alembic-migrate-in-container.md` — run alembic inside container; host alembic uses wrong DB URL
> See also: `learned/postgres-volume-password-mismatch.md` — stale volume keeps old password; fix with ALTER USER, not volume wipe
> See also: `learned/seed-sql-schema-sync.md` — seed SQL drifts from schema silently; verify with \d tablename before debugging logic
> See also: `learned/makefile-infrastructure-first-setup.md` — start infra before app services; health-poll instead of sleep; `@printf` pitfall in Make shell blocks
> See also: `learned/docker-nuke-graduated-cleanup.md` — graduated cleanup (clean→purge→nuke); `docker image prune` misses tagged images
> See also: `learned/compose-overlay-core-feature-trap.md` — core features must be in base compose.yml; overlays only for GPU/optional services
> See also: `learned/nginx-dynamic-dns-resolver.md` — resolver 127.0.0.11 + set $upstream to avoid 502s after container restarts
> See also: `learned/volume-mounted-models-silent-failure.md` — empty volume = silent 0.0 scores; need make download-models + health check
> See also: `learned/post-embedding-relevance-gate.md` — filter off-topic scraped content via topic query embedding similarity before clustering
> See also: `learned/orphan-sweep-safety-net.md` — safety net for content_items where enqueue_job("analyse_content") failed after DB insert
> See also: `learned/scheduler-worker-split.md` — analyst split into scheduler (clustering/signals) + ARQ worker (NLP/embedding); import chain safety
> See also: `learned/rss-fetch-paywall-validation.md` — validate fetched content before replacing RSS summary; paywall indicator counting
> See also: `learned/quality-gate-all-consumers.md` — apply quality/relevance filters at every consumption point, not just clustering
> See also: `learned/compose-env-var-silent-disable.md` — feature flag env vars must be in compose environment block; silently defaults to false
> See also: `learned/docker-exec-integration-test.md` — host→docker cp→docker exec→JSON stdout pattern for testing real code paths in containers
> See also: `learned/container-integration-test-orchestration.md` — single make test-integration runs host DB tests + container model tests
> See also: `learned/httpx-socks-optional-extra.md` — httpx[socks] required for Tor SOCKS5; unit tests don't catch missing optional extras

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
