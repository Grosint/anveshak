"""Anveshak Analyst Service — M1+M2: NLP pipeline, clustering, Signals engine."""
import asyncio
import structlog
import asyncpg
from anveshak.logging import configure_logging

configure_logging("analyst")
from prometheus_client import start_http_server
from .metrics import REGISTRY as ANALYST_REGISTRY
from .clustering import run_clustering
from .credibility import run_credibility_update
from .embeddings import load_encoder
from .jobs import analyse_content
from .nlp import load_models
from .settings import settings
from .signal_engine import signal_engine_loop

log = structlog.get_logger(__name__)

SQL_UNPROCESSED_CONTENT = """
    SELECT id FROM content_items
    WHERE embedding IS NULL
    ORDER BY captured_at ASC
    LIMIT 50
"""

SQL_ACTIVE_TOPICS = """
    SELECT id FROM topics WHERE status = 'active'
"""


async def _noop_broadcast(payload: dict) -> None:
    """No-op broadcast used when signal engine runs standalone (no WS server here).

    The API service owns the WebSocket connections; the analyst service fires
    signals into the DB. The API's signal polling loop delivers them over WS.
    """
    pass


async def main():
    # 8A.17 — start Prometheus metrics HTTP server (isolated registry, 8A.18)
    start_http_server(settings.metrics_port, registry=ANALYST_REGISTRY)
    log.info("analyst.metrics_server_started", port=settings.metrics_port)

    log.info("analyst.starting",
             spacy_en=settings.spacy_en_model,
             embedding_model=settings.embedding_model,
             cluster_model=settings.ollama_cluster_model)

    # criteria 1.17, 1.18: load models ONCE before starting loops
    load_models()
    load_encoder()

    pool = await asyncpg.create_pool(settings.postgres_url, min_size=2, max_size=5)
    log.info("analyst.ready")

    await asyncio.gather(
        nlp_loop(pool),
        cluster_loop(pool),
        signal_check_loop(pool),
        credibility_update_loop(pool),
    )


async def nlp_loop(pool: asyncpg.Pool):
    """Sweep content_items without embeddings and run NLP pipeline."""
    ctx = {"db_pool": pool}
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_UNPROCESSED_CONTENT)

        if rows:
            log.info("analyst.nlp_sweep", pending=len(rows))
            for row in rows:
                try:
                    await analyse_content(ctx, row["id"])
                except Exception as exc:
                    log.warning("analyst.nlp_item_failed",
                                content_item_id=row["id"], error=str(exc))
        await asyncio.sleep(30)


async def cluster_loop(pool: asyncpg.Pool):
    """Cluster content_items by topic using HDBSCAN (criteria 2.1–2.5)."""
    while True:
        await asyncio.sleep(300)
        try:
            async with pool.acquire() as conn:
                topic_rows = await conn.fetch(SQL_ACTIVE_TOPICS)

            for row in topic_rows:
                topic_id: str = row["id"]
                try:
                    cluster_ids = await run_clustering(topic_id, pool)
                    if cluster_ids:
                        log.info(
                            "analyst.cluster_loop.clustered",
                            topic_id=topic_id,
                            clusters=len(cluster_ids),
                        )
                except Exception as exc:
                    log.warning(
                        "analyst.cluster_loop.topic_failed",
                        topic_id=topic_id,
                        error=str(exc),
                    )
        except Exception as exc:
            log.error("analyst.cluster_loop.error", error=str(exc))


async def signal_check_loop(pool: asyncpg.Pool):
    """Check if any clusters cross topic.signal_threshold → fire Signal (criteria 2.11)."""
    await signal_engine_loop(pool, _noop_broadcast)


async def credibility_update_loop(pool: asyncpg.Pool):
    """Auto-update source credibility based on deepfake amplification (criteria 2.21)."""
    while True:
        await asyncio.sleep(settings.credibility_update_interval_s)
        try:
            await run_credibility_update(pool)
        except Exception as exc:
            log.error("analyst.credibility_loop.error", error=str(exc))


if __name__ == "__main__":
    asyncio.run(main())
