"""Anveshak Analyst Scheduler — lightweight loops that need global state.

Runs cluster_loop, signal_check_loop, convergence_loop, and orphan_sweep.
Does NOT import spaCy, sentence-transformers, NLLB, VADER, or YAKE.
All per-item ML work runs in analyst-worker via ARQ.

Entry point: python -m anveshak.analyst.scheduler
"""
from __future__ import annotations

import asyncio

import asyncpg
import structlog
from arq import create_pool as create_redis_pool
from arq.connections import RedisSettings
from anveshak.logging import configure_logging

configure_logging("analyst-scheduler")
from prometheus_client import start_http_server

from .clustering import run_clustering
from .dedup import detect_near_duplicates, upsert_near_duplicates
from .labeller import check_label_staleness
from .metrics import REGISTRY as ANALYST_REGISTRY
from .settings import settings
from .signal_engine import signal_engine_loop

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_ACTIVE_TOPICS = """
    SELECT id FROM topics WHERE status = 'active'
"""

SQL_ARCHIVE_OLD_CLUSTERS = """
    UPDATE narrative_clusters
    SET archived_at = NOW()
    WHERE archived_at IS NULL
      AND updated_at < NOW() - MAKE_INTERVAL(days => $1)
"""

SQL_ORPHANED_CONTENT = """
    SELECT id FROM content_items
    WHERE embedding IS NULL
      AND created_at > NOW() - INTERVAL '1 hour'
    ORDER BY captured_at ASC
    LIMIT 100
"""

# ---------------------------------------------------------------------------
# Scheduler metrics port (separate from worker)
# ---------------------------------------------------------------------------

SCHEDULER_METRICS_PORT = 8007


# ---------------------------------------------------------------------------
# No-op broadcast — signal engine needs a broadcast fn but scheduler has no WS
# ---------------------------------------------------------------------------

async def _noop_broadcast(payload: dict) -> None:
    """No-op broadcast: API service owns WebSocket delivery, not the scheduler."""
    pass


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------

async def cluster_loop(pool: asyncpg.Pool, redis: object) -> None:
    """Cluster content_items by topic using HDBSCAN (criteria 2.1-2.5).

    After clustering, enqueues label generation and cross-verification
    to ARQ worker instead of calling Ollama inline.
    """
    while True:
        await asyncio.sleep(300)
        try:
            # Archive stale clusters before processing
            if settings.cluster_archive_after_days > 0:
                async with pool.acquire() as conn:
                    archived = await conn.execute(
                        SQL_ARCHIVE_OLD_CLUSTERS,
                        settings.cluster_archive_after_days,
                    )
                    if archived and archived != "UPDATE 0":
                        log.info("scheduler.cluster_loop.archived", result=archived)

            async with pool.acquire() as conn:
                topic_rows = await conn.fetch(SQL_ACTIVE_TOPICS)

            for row in topic_rows:
                topic_id: str = row["id"]
                try:
                    # Detect near-duplicates before clustering so ISC is accurate
                    pairs = await detect_near_duplicates(topic_id, pool)
                    if pairs:
                        await upsert_near_duplicates(pairs, pool)

                    cluster_ids = await run_clustering(topic_id, pool)
                    if cluster_ids:
                        log.info(
                            "scheduler.cluster_loop.clustered",
                            topic_id=topic_id,
                            clusters=len(cluster_ids),
                        )
                        # Enqueue label generation for stale/new clusters (ARQ worker)
                        for cid in cluster_ids:
                            try:
                                if await check_label_staleness(cid, pool):
                                    await redis.enqueue_job(
                                        "generate_cluster_label",
                                        cid,
                                        _queue_name="arq:analyst",
                                    )
                            except Exception as label_exc:
                                log.warning(
                                    "scheduler.cluster_loop.label_enqueue_failed",
                                    cluster_id=cid,
                                    error=str(label_exc),
                                )

                        # Enqueue cross-verification boost (criteria 7.1)
                        await redis.enqueue_job(
                            "run_cross_verification",
                            topic_id,
                            _queue_name="arq:analyst",
                        )
                except Exception as exc:
                    log.warning(
                        "scheduler.cluster_loop.topic_failed",
                        topic_id=topic_id,
                        error=str(exc),
                    )
        except Exception as exc:
            log.error("scheduler.cluster_loop.error", error=str(exc))


async def signal_check_loop(pool: asyncpg.Pool) -> None:
    """Check if any clusters cross topic.signal_threshold -> fire Signal (criteria 2.11)."""
    await signal_engine_loop(pool, _noop_broadcast)


async def convergence_loop(pool: asyncpg.Pool) -> None:
    """Cross-topic cluster convergence detection (Phase 6 - P2b)."""
    from .convergence import check_cross_topic_convergence

    if settings.cross_topic_check_interval_s <= 0:
        log.info("scheduler.convergence_loop.disabled")
        return

    log.info(
        "scheduler.convergence_loop.started",
        interval_s=settings.cross_topic_check_interval_s,
    )
    while True:
        await asyncio.sleep(settings.cross_topic_check_interval_s)
        try:
            fired = await check_cross_topic_convergence(pool)
            if fired:
                log.info("scheduler.convergence_loop.cycle_done", signals_fired=fired)
        except Exception as exc:
            log.error("scheduler.convergence_loop.error", error=str(exc))


async def orphan_sweep(pool: asyncpg.Pool, redis: object) -> None:
    """Safety net: re-enqueue content_items that missed ARQ enqueue after insert.

    Catches items where the scraper/social inserted a row but the
    enqueue_job('analyse_content', ...) call failed or was skipped.
    """
    log.info("scheduler.orphan_sweep.started", interval_s=300)
    while True:
        await asyncio.sleep(300)
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(SQL_ORPHANED_CONTENT)

            if rows:
                log.info("scheduler.orphan_sweep.found", pending=len(rows))
                for row in rows:
                    try:
                        await redis.enqueue_job(
                            "analyse_content",
                            row["id"],
                            _queue_name="arq:analyst",
                        )
                    except Exception as exc:
                        log.warning(
                            "scheduler.orphan_sweep.enqueue_failed",
                            content_item_id=row["id"],
                            error=str(exc),
                        )
        except Exception as exc:
            log.error("scheduler.orphan_sweep.error", error=str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    """Start the analyst scheduler with 4 concurrent loops."""
    start_http_server(SCHEDULER_METRICS_PORT, registry=ANALYST_REGISTRY)
    log.info("scheduler.metrics_server_started", port=SCHEDULER_METRICS_PORT)

    log.info("scheduler.starting")

    pool = await asyncpg.create_pool(settings.postgres_url, min_size=2, max_size=5)
    redis = await create_redis_pool(RedisSettings.from_dsn(settings.redis_url))

    log.info("scheduler.ready")

    await asyncio.gather(
        cluster_loop(pool, redis),
        signal_check_loop(pool),
        convergence_loop(pool),
        orphan_sweep(pool, redis),
    )


if __name__ == "__main__":
    asyncio.run(main())
