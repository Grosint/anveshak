"""Anveshak Social Service — M3: Social media platform adapters.

Polls all enabled adapters for every active topic on a configurable interval.
Enqueues poll_social_topic ARQ jobs rather than running inline so each topic
is processed independently and failures are isolated.

X/Twitter uses its own poll interval (settings.x_poll_interval_s, default 900s)
which may differ from the global poll_interval_s used by other adapters (criteria 3.25).
Both default to 900s. Adjust x_poll_interval_s independently to control X API spend.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
import structlog
from anveshak.logging import configure_logging

configure_logging("social")
import asyncpg
from arq import create_pool
from arq.connections import RedisSettings
from prometheus_client import start_http_server

from .metrics import REGISTRY as SOCIAL_REGISTRY
from .settings import settings

log = structlog.get_logger(__name__)

SQL_GET_ACTIVE_TOPICS = "SELECT id FROM topics WHERE status = 'active'"


async def main() -> None:
    # 8A.17 — start Prometheus metrics HTTP server (isolated registry, 8A.18)
    start_http_server(settings.metrics_port, registry=SOCIAL_REGISTRY)
    log.info("social.metrics_server_started", port=settings.metrics_port)

    log.info(
        "social.starting",
        poll_interval_s=settings.poll_interval_s,
        x_poll_interval_s=settings.x_poll_interval_s,
    )

    enabled = []
    if settings.telegram_adapter_enabled:
        enabled.append("telegram")
    if settings.reddit_adapter_enabled:
        enabled.append("reddit")
    if settings.bluesky_adapter_enabled:
        enabled.append("bluesky")
    if settings.x_adapter_enabled:
        enabled.append(f"x/{settings.x_adapter_mode}")

    if not enabled:
        log.warning(
            "social.no_adapters_enabled",
            hint="Set TELEGRAM_ADAPTER_ENABLED=true, REDDIT_ADAPTER_ENABLED=true, "
                 "BLUESKY_ADAPTER_ENABLED=true, or X_ADAPTER_ENABLED=true",
        )

    db_pool = await asyncpg.create_pool(settings.postgres_url, min_size=1, max_size=3)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_pool(redis_settings)

    log.info("social.ready", adapters=enabled)

    # Detect missed polling window on restart
    from .backfill import get_last_poll_at, save_last_poll_at, detect_poll_gap
    last_poll = await get_last_poll_at(arq_pool)
    gap = detect_poll_gap(last_poll, settings.poll_interval_s)
    if gap:
        log.warning("social.startup_gap", missed_duration=str(gap))

    # Track last X poll time separately — X uses x_poll_interval_s (criteria 3.25)
    last_x_poll_at: datetime | None = None

    try:
        while True:
            now = datetime.now(UTC)
            x_due = (
                settings.x_adapter_enabled
                and (
                    last_x_poll_at is None
                    or (now - last_x_poll_at).total_seconds() >= settings.x_poll_interval_s
                )
            )

            await enqueue_topic_polls(db_pool, arq_pool, include_x=x_due)
            await save_last_poll_at(arq_pool, now)

            if x_due:
                last_x_poll_at = now
                log.debug(
                    "social.x_poll_scheduled",
                    next_in_s=settings.x_poll_interval_s,
                )

            await asyncio.sleep(settings.poll_interval_s)
    finally:
        await db_pool.close()
        await arq_pool.aclose()


async def enqueue_topic_polls(
    db_pool: asyncpg.Pool,
    arq_pool,
    include_x: bool = True,
) -> None:
    """Enqueue one poll_social_topic ARQ job per active topic.

    include_x: if False, X adapter jobs are skipped this cycle (interval not yet elapsed).
    """
    async with db_pool.acquire() as conn:
        topics = await conn.fetch(SQL_GET_ACTIVE_TOPICS)

    if not topics:
        log.debug("social.no_active_topics")
        return

    for topic in topics:
        await arq_pool.enqueue_job("poll_social_topic", topic["id"], include_x=include_x)
        log.debug("social.topic_enqueued", topic_id=topic["id"], include_x=include_x)

    log.info("social.topics_enqueued", count=len(topics), include_x=include_x)


if __name__ == "__main__":
    asyncio.run(main())
