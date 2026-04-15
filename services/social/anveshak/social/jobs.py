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
from .ingest import ingest_raw_item
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

    candidates: list = []
    if settings.reddit_adapter_enabled:
        candidates.append(RedditAdapter())
    if settings.bluesky_adapter_enabled:
        candidates.append(BlueskyAdapter())
    if settings.telegram_adapter_enabled:
        candidates.append(TelegramAdapter())
    if settings.x_adapter_enabled:
        candidates.append(make_x_adapter(ctx["arq_pool"]))

    for adapter in candidates:
        try:
            await adapter.authenticate()
            _ADAPTERS[adapter.adapter_id] = adapter
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
            "SELECT id, keywords FROM topics WHERE id = $1 AND status = 'active'",
            topic_id,
        )
    if not topic_row:
        log.warning("social.poll.topic_not_found", topic_id=topic_id)
        return {"inserted": 0}

    keywords: list[str] = list(topic_row["keywords"] or [])
    summary: dict[str, int] = {}

    for adapter_id, adapter in _ADAPTERS.items():
        platform = adapter.platform

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
        try:
            async for raw_item in adapter.collect(keywords, source_handles, topic_id):
                try:
                    new = await ingest_raw_item(
                        raw_item, topic_id, db_pool, arq_pool, adapter_id
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

        except AdapterRateLimitError as exc:
            log.warning("social.rate_limited", adapter_id=adapter_id, error=str(exc))
        except AdapterDegradedError as exc:
            log.warning("social.degraded", adapter_id=adapter_id, error=str(exc))
        except Exception as exc:
            log.error("social.adapter_error", adapter_id=adapter_id, error=str(exc))

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
