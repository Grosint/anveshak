"""ARQ job definitions — Social service (M3).

WorkerSettings is the entry point for `arq anveshak.social.jobs.WorkerSettings`.

poll_social_topic: polls all enabled adapters for a given topic.
"""
from __future__ import annotations

import asyncio
import structlog
import asyncpg
from arq import ArqRedis
from arq.connections import RedisSettings

from .adapters.base import AdapterAuthError, AdapterRateLimitError, AdapterDegradedError
from .circuit_breaker import AdapterCircuitBreaker
from .ingest import ingest_raw_item
from .metrics import social_api_calls_total, social_rate_limit_total, social_poll_duration_seconds
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_GET_ACTIVE_TOPICS = """
    SELECT id, keywords
    FROM topics
    WHERE status = 'active'
"""

SQL_GET_SOURCES_FOR_PLATFORM = """
    SELECT id, url_or_handle, credibility_score
    FROM sources
    WHERE platform = $1 AND is_active = TRUE
"""

# ---------------------------------------------------------------------------
# Global adapter registry (populated at worker startup)
# ---------------------------------------------------------------------------

_ADAPTERS: dict = {}   # adapter_id → SourceAdapterBase instance
_CIRCUIT_BREAKERS: dict[str, AdapterCircuitBreaker] = {}  # adapter_id → breaker


# ---------------------------------------------------------------------------
# Credential validation — checked at startup before instantiation
# ---------------------------------------------------------------------------

_REQUIRED_CREDENTIALS: dict[str, list[tuple[str, str]]] = {
    "bluesky": [
        ("bluesky_handle", "BLUESKY_HANDLE"),
        ("bluesky_password", "BLUESKY_PASSWORD"),
    ],
    "reddit": [
        ("reddit_client_id", "REDDIT_CLIENT_ID"),
        ("reddit_client_secret", "REDDIT_CLIENT_SECRET"),
    ],
    "telegram": [
        ("telegram_api_id", "TELEGRAM_API_ID"),
        ("telegram_api_hash", "TELEGRAM_API_HASH"),
        ("telegram_session_string", "TELEGRAM_SESSION_STRING"),
    ],
    "x": [
        ("x_bearer_token", "X_BEARER_TOKEN"),
    ],
    "instagram": [
        ("instagram_username", "INSTAGRAM_USERNAME"),
        ("instagram_password", "INSTAGRAM_PASSWORD"),
    ],
}


def _validate_adapter_credentials(adapter_name: str, s) -> list[str]:
    """Return list of missing credential env var names for the adapter.

    Empty list means all required credentials are present.
    """
    required = _REQUIRED_CREDENTIALS.get(adapter_name, [])
    missing = []
    for attr, env_name in required:
        val = getattr(s, attr, None)
        if val is None:
            missing.append(env_name)
    return missing


# ---------------------------------------------------------------------------
# ARQ startup / shutdown hooks
# ---------------------------------------------------------------------------

async def startup(ctx: dict) -> None:
    """Initialise DB pool, ARQ pool, and authenticate all enabled adapters."""
    ctx["db_pool"] = await asyncpg.create_pool(
        settings.postgres_url, min_size=2, max_size=5
    )
    ctx["arq_pool"] = ctx["redis"]   # ARQ passes redis connection in ctx["redis"]

    # Import adapters here to avoid circular imports
    from .adapters.reddit import RedditAdapter
    from .adapters.bluesky import BlueskyAdapter
    from .adapters.telegram import TelegramAdapter
    from .adapters.x_adapter import make_x_adapter
    from .adapters.instagram import (
        InstagramAdapter, InstagramRateLimitGuard,
        INSTAGRAM_CIRCUIT_BREAKER_THRESHOLD, INSTAGRAM_CIRCUIT_BREAKER_COOLDOWN_S,
    )

    candidates: list = []

    # Validate credentials before instantiation — clear warnings, no crash
    adapter_configs = [
        (settings.reddit_adapter_enabled, "reddit", lambda: RedditAdapter()),
        (settings.bluesky_adapter_enabled, "bluesky", lambda: BlueskyAdapter(
            quota_guard=__import__("anveshak.social.adapters.bluesky", fromlist=["BlueskyQuotaGuard"]).BlueskyQuotaGuard(
                ctx["arq_pool"], settings.bluesky_daily_call_cap
            )
        )),
        (settings.telegram_adapter_enabled, "telegram", lambda: TelegramAdapter()),
        (settings.x_adapter_enabled, "x", lambda: make_x_adapter(ctx["arq_pool"])),
        (settings.instagram_adapter_enabled, "instagram", lambda: InstagramAdapter(
            rate_guard=InstagramRateLimitGuard(ctx["arq_pool"], settings.instagram_hourly_call_cap)
        )),
    ]

    for enabled, name, factory in adapter_configs:
        if not enabled:
            continue
        missing = _validate_adapter_credentials(name, settings)
        if missing:
            log.warning(
                "social.adapter_missing_credentials",
                adapter=name,
                missing=missing,
                hint=f"Set {', '.join(missing)} to enable {name} adapter",
            )
            continue
        candidates.append(factory())

    for adapter in candidates:
        try:
            await adapter.authenticate()
            _ADAPTERS[adapter.adapter_id] = adapter
            # Instagram uses higher threshold + longer cooldown (Meta bans are 24h)
            if adapter.platform == "instagram":
                cb_threshold = INSTAGRAM_CIRCUIT_BREAKER_THRESHOLD
                cb_cooldown = INSTAGRAM_CIRCUIT_BREAKER_COOLDOWN_S
            else:
                cb_threshold = settings.social_circuit_breaker_threshold
                cb_cooldown = settings.social_circuit_breaker_cooldown_s
            _CIRCUIT_BREAKERS[adapter.adapter_id] = AdapterCircuitBreaker(
                ctx["arq_pool"],
                adapter.adapter_id,
                threshold=cb_threshold,
                cooldown_s=cb_cooldown,
            )
            log.info("social.adapter_ready", adapter_id=adapter.adapter_id)
        except AdapterAuthError as exc:
            log.error(
                "social.adapter_auth_failed",
                adapter_id=adapter.adapter_id,
                error=str(exc),
            )
            # Do NOT crash — other adapters may still work (criteria 3.5)

    log.info("social.worker_ready", adapters=list(_ADAPTERS.keys()))


async def shutdown(ctx: dict) -> None:
    await ctx["db_pool"].close()


# ---------------------------------------------------------------------------
# ARQ job: poll_social_topic
# ---------------------------------------------------------------------------

async def poll_social_topic(ctx: dict, topic_id: str, include_x: bool = True) -> dict:
    """Poll all enabled adapters for a single topic.

    Enqueued once per topic per poll cycle by main.py.
    include_x: when False, X adapter is skipped this cycle (x_poll_interval_s not yet elapsed,
               criteria 3.25 — X respects its own independent polling interval).
    Returns summary of inserted counts per platform.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    arq_pool: ArqRedis = ctx["arq_pool"]

    async with db_pool.acquire() as conn:
        topic_row = await conn.fetchrow(
            "SELECT id, keywords, org_id FROM topics WHERE id = $1 AND status = 'active'",
            topic_id,
        )
    if not topic_row:
        log.warning("social.poll.topic_not_found", topic_id=topic_id)
        return {"inserted": 0}

    keywords: list[str] = list(topic_row["keywords"] or [])
    topic_org_id: str | None = topic_row.get("org_id")
    summary: dict[str, int] = {}

    for adapter_id, adapter in _ADAPTERS.items():
        platform = adapter.platform

        # Circuit breaker — skip adapters that are in OPEN state
        cb = _CIRCUIT_BREAKERS.get(adapter_id)
        if cb and not await cb.allows_call():
            log.info("social.circuit_breaker.skipped", adapter_id=adapter_id)
            continue

        # Respect X-specific poll interval — skip if not yet due (criteria 3.25)
        if platform == "twitter" and not include_x:
            log.debug("social.x_poll_skipped", adapter_id=adapter_id,
                      reason="x_poll_interval_s not elapsed")
            continue

        async with db_pool.acquire() as conn:
            source_rows = await conn.fetch(
                SQL_GET_SOURCES_FOR_PLATFORM, platform
            )
        source_handles = [r["url_or_handle"] for r in source_rows]

        inserted = 0
        import time as _time
        _poll_t0 = _time.monotonic()
        try:
            social_api_calls_total.labels(platform=platform).inc()
            async for raw_item in adapter.collect(keywords, source_handles, topic_id):
                try:
                    new = await ingest_raw_item(
                        raw_item, topic_id, db_pool, arq_pool, adapter_id,
                        org_id=topic_org_id,
                    )
                    if new:
                        inserted += 1
                except Exception as exc:
                    log.warning(
                        "social.ingest_error",
                        adapter_id=adapter_id,
                        url=raw_item.url,
                        error=str(exc),
                    )

        except AdapterAuthError as exc:
            log.warning("social.auth_error_during_collect", adapter_id=adapter_id, error=str(exc))
            refreshed = await adapter.refresh_credentials()
            if refreshed:
                log.info("social.credentials_refreshed", adapter_id=adapter_id)
            elif cb:
                await cb.record_failure()
        except AdapterRateLimitError as exc:
            log.warning("social.rate_limited", adapter_id=adapter_id, error=str(exc))
            social_rate_limit_total.labels(platform=platform).inc()
            if cb:
                await cb.record_failure()
        except AdapterDegradedError as exc:
            log.warning("social.degraded", adapter_id=adapter_id, error=str(exc))
            if cb:
                await cb.record_failure()
        except Exception as exc:
            log.error("social.adapter_error", adapter_id=adapter_id, error=str(exc))
            if cb:
                await cb.record_failure()
        else:
            if cb:
                await cb.record_success()

        social_poll_duration_seconds.labels(platform=platform).observe(
            _time.monotonic() - _poll_t0
        )
        summary[platform] = inserted
        log.info(
            "social.poll.done",
            topic_id=topic_id,
            adapter_id=adapter_id,
            inserted=inserted,
        )

    return {"topic_id": topic_id, "inserted_by_platform": summary}


# ---------------------------------------------------------------------------
# ARQ WorkerSettings
# ---------------------------------------------------------------------------

class WorkerSettings:
    functions = [poll_social_topic]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
