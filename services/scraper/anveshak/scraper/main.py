"""Anveshak Scraper Service — M2: Open-source web content ingestion."""
import asyncio
import structlog
import asyncpg
from anveshak.logging import configure_logging

configure_logging("scraper")
from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from prometheus_client import start_http_server
from .metrics import REGISTRY as SCRAPER_REGISTRY
from .settings import settings

log = structlog.get_logger(__name__)


async def main():
    # 8A.17 — start Prometheus metrics HTTP server (isolated registry, 8A.18)
    start_http_server(settings.metrics_port, registry=SCRAPER_REGISTRY)
    log.info("scraper.metrics_server_started", port=settings.metrics_port)

    log.info("scraper.starting",
             concurrency=settings.scraper_concurrency,
             timeout_s=settings.scraper_request_timeout_s,
             poll_interval_s=settings.scraper_poll_interval_s)

    from anveshak.db import create_db_pool
    db_pool = await create_db_pool(settings.postgres_url)
    redis = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
    log.info("scraper.ready")

    try:
        while True:
            await _enqueue_active_topics(db_pool, redis)
            await asyncio.sleep(settings.scraper_poll_interval_s)
    finally:
        await db_pool.close()


async def _enqueue_active_topics(pool: asyncpg.Pool, redis) -> None:
    """Enqueue scrape_topic and poll_rss_sources ARQ jobs for every active topic."""
    async with pool.acquire() as conn:
        topics = await conn.fetch(
            "SELECT id, name FROM topics WHERE status = 'active'"
        )
    log.info("scraper.enqueuing", count=len(topics))
    for topic in topics:
        await redis.enqueue_job("scrape_topic", topic["id"], _queue_name="arq:scraper")
        await redis.enqueue_job("poll_rss_sources", topic["id"], _queue_name="arq:scraper")
        await redis.enqueue_job("scrape_darkweb_topic", topic["id"], _queue_name="arq:scraper")
        log.debug("scraper.enqueued", topic_id=topic["id"], name=topic["name"])


if __name__ == "__main__":
    asyncio.run(main())
