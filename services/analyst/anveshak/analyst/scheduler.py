"""Anveshak Analyst Scheduler — lightweight loops + internal embedding API.

Runs cluster_loop, signal_check_loop, convergence_loop, and orphan_sweep
as background tasks inside a FastAPI app. Also serves:
  - /internal/embed   — embedding endpoint for API/reporter (avoids PyTorch in those images)
  - /metrics          — Prometheus metrics
  - /health           — health check

Does NOT eagerly import spaCy, NLLB, VADER, or YAKE.
The sentence-transformers encoder is lazy-loaded on first /internal/embed request.

Entry point: python -m anveshak.analyst.scheduler
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import structlog
import uvicorn
from anveshak.logging import configure_logging
from arq import ArqRedis
from arq import create_pool as create_redis_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

configure_logging("analyst-scheduler")
from prometheus_client import generate_latest

from .clustering import run_clustering
from .dedup import detect_near_duplicates, upsert_near_duplicates
from .discovery import (  # noqa: E501
    discover_entity_sources,
    discover_snowball_sources,
    discover_telegram_channels,
)
from .effectiveness import compute_source_effectiveness
from .identifier_clustering import ContentIdentifier, build_clusters
from .labeller import check_label_staleness
from .metrics import REGISTRY as ANALYST_REGISTRY
from .metrics import analyst_identifier_clusters_total, analyst_orphan_sweep_total
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
      AND (orphan_enqueued_at IS NULL
           OR orphan_enqueued_at < NOW() - INTERVAL '10 minutes')
    ORDER BY captured_at ASC
    LIMIT 100
"""

SQL_EXPIRED_CONTENT_ITEMS = """
    SELECT ci.id, ci.topic_id, TO_CHAR(ci.captured_at, 'YYYY-MM') AS month
    FROM content_items ci
    WHERE ci.captured_at < NOW() - MAKE_INTERVAL(days => $1)
      AND ci.narrative_cluster_id IS NOT NULL
    ORDER BY ci.captured_at ASC
    LIMIT 500
"""

SQL_CONTENT_FOR_ARCHIVE = """
    SELECT ci.id, ci.topic_id, ci.source_id, ci.raw_text, ci.clean_text,
           ci.language, ci.translated_text, ci.content_hash, ci.url,
           ci.captured_at, ci.credibility_score_at_capture,
           ci.topic_relevance_score, ci.narrative_cluster_id,
           ci.labels,
           COALESCE(
               json_agg(json_build_object(
                   'entity_type', ee.entity_type,
                   'entity_text', ee.entity_text,
                   'confidence', ee.confidence
               )) FILTER (WHERE ee.id IS NOT NULL), '[]'
           ) AS entities
    FROM content_items ci
    LEFT JOIN extracted_entities ee ON ee.content_item_id = ci.id
    WHERE ci.id = ANY($1)
    GROUP BY ci.id
"""

SQL_UPSERT_CONTENT_ARCHIVE = """
    INSERT INTO content_archives (id, topic_id, month, file_path, item_count, file_size, labels)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (topic_id, month)
    DO UPDATE SET item_count = content_archives.item_count + EXCLUDED.item_count,
                  file_size = EXCLUDED.file_size
"""

SQL_ACTIVE_TOPICS_PRIORITIZED = """
    SELECT t.id,
           COUNT(ci.id) FILTER (WHERE ci.narrative_cluster_id IS NULL
                                  AND ci.embedding IS NOT NULL) AS pending
    FROM topics t
    LEFT JOIN content_items ci ON ci.topic_id = t.id
    WHERE t.status = 'active'
    GROUP BY t.id
    HAVING COUNT(ci.id) FILTER (WHERE ci.narrative_cluster_id IS NULL
                                  AND ci.embedding IS NOT NULL) > 0
    ORDER BY pending DESC
"""

# ---------------------------------------------------------------------------
# Embedding endpoint — lazy-loaded, avoids PyTorch in API/reporter images
# ---------------------------------------------------------------------------

_encoder = None


def _get_encoder():
    """Lazy-load sentence-transformers on first embed request."""
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer

        _encoder = SentenceTransformer(settings.embedding_model)
        log.info(
            "scheduler.encoder_loaded",
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return _encoder


class EmbedRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    texts: list[str]


class EmbedResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    embeddings: list[list[float]]


# ---------------------------------------------------------------------------
# No-op broadcast — signal engine needs a broadcast fn but scheduler has no WS
# ---------------------------------------------------------------------------


async def _noop_broadcast(payload: dict) -> None:
    """No-op broadcast: API service owns WebSocket delivery, not the scheduler."""
    pass


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------


def write_archive_batch(
    topic_id: str,
    month: str,
    items: list[dict],
    archive_root: str,
) -> str:
    """Write items to a gzipped JSONL archive file. Returns the file path."""
    topic_dir = Path(archive_root) / topic_id
    topic_dir.mkdir(parents=True, exist_ok=True)
    path = str(topic_dir / f"{month}.jsonl.gz")

    with gzip.open(path, "at") as f:
        for item in items:
            row = {}
            for k, v in item.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                elif isinstance(v, str) and k in ("entities", "labels"):
                    try:
                        row[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        row[k] = v
                else:
                    row[k] = v
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return path


async def archive_and_delete_expired(pool: asyncpg.Pool) -> dict:
    """Archive old clustered content to compressed JSONL, then delete from DB.

    Returns dict with archived/deleted/errors counts.
    """
    if settings.content_retention_days == 0:
        log.info("scheduler.content_retention.disabled", reason="CONTENT_RETENTION_DAYS=0")
        return {"skipped": "retention_disabled"}

    async with pool.acquire() as conn:
        expired_rows = await conn.fetch(
            SQL_EXPIRED_CONTENT_ITEMS,
            settings.content_retention_days,
        )

    if not expired_rows:
        return {"archived": 0, "deleted": 0, "errors": 0}

    # Group by topic_id + month
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in expired_rows:
        groups[(row["topic_id"], row["month"])].append(row["id"])

    archived = 0
    deleted = 0
    errors = 0

    for (topic_id, month), item_ids in groups.items():
        try:
            # Fetch full data for archive
            async with pool.acquire() as conn:
                archive_rows = await conn.fetch(SQL_CONTENT_FOR_ARCHIVE, item_ids)

            items = [dict(r) for r in archive_rows]

            # Write to compressed JSONL
            path = write_archive_batch(
                topic_id,
                month,
                items,
                settings.content_archive_root,
            )
            file_size = os.path.getsize(path)

            # Record in content_archives table
            async with pool.acquire() as conn:
                await conn.execute(
                    SQL_UPSERT_CONTENT_ARCHIVE,
                    str(uuid.uuid4()),
                    topic_id,
                    month,
                    path,
                    len(items),
                    file_size,
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}',
                )

                # Delete from PostgreSQL (CASCADE handles children)
                result = await conn.execute(
                    "DELETE FROM content_items WHERE id = ANY($1)",
                    item_ids,
                )
                count = int(result.split()[-1]) if result else 0
                deleted += count

            archived += len(items)
            log.info(
                "scheduler.content_retention.batch",
                topic_id=topic_id,
                month=month,
                archived=len(items),
                deleted=count,
                path=path,
            )

        except Exception as exc:
            errors += 1
            log.warning(
                "scheduler.content_retention.batch_error",
                topic_id=topic_id,
                month=month,
                error=str(exc),
            )

    log.info(
        "scheduler.content_retention.complete",
        cutoff_days=settings.content_retention_days,
        archived=archived,
        deleted=deleted,
        errors=errors,
    )
    return {"archived": archived, "deleted": deleted, "errors": errors}


async def get_prioritized_topics(pool: asyncpg.Pool) -> list[dict]:
    """Get active topics with pending unclustered items, sorted by most pending first.

    When max_topics_per_cycle > 0, limits to that many topics.
    When max_topics_per_cycle == 0, returns all topics with pending items.
    """
    async with pool.acquire() as conn:
        if settings.max_topics_per_cycle > 0:
            rows = await conn.fetch(
                SQL_ACTIVE_TOPICS_PRIORITIZED + " LIMIT $1",
                settings.max_topics_per_cycle,
            )
        else:
            rows = await conn.fetch(SQL_ACTIVE_TOPICS_PRIORITIZED)
    return [dict(r) for r in rows]


async def content_retention_loop(pool: asyncpg.Pool) -> None:
    """Daily loop: archive old clustered items, then delete from DB."""
    while True:
        await asyncio.sleep(86400)  # daily
        try:
            await archive_and_delete_expired(pool)
        except Exception as exc:
            log.error("scheduler.content_retention.error", error=str(exc))


async def cluster_loop(pool: asyncpg.Pool, redis: ArqRedis) -> None:
    """Cluster content_items by topic using Leiden community detection (criteria 2.1-2.5).

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

            topic_rows = await get_prioritized_topics(pool)

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


async def orphan_sweep(pool: asyncpg.Pool, redis: ArqRedis) -> None:
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
                analyst_orphan_sweep_total.inc(len(rows))
                for row in rows:
                    try:
                        await redis.enqueue_job(
                            "analyse_content",
                            row["id"],
                            _queue_name="arq:analyst",
                        )
                        # Stamp to prevent re-enqueue within 10 minutes
                        async with pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE content_items SET orphan_enqueued_at = NOW() WHERE id = $1",
                                row["id"],
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
# Relevance threshold auto-calibration
# ---------------------------------------------------------------------------


async def relevance_calibration_loop(pool: asyncpg.Pool) -> None:
    """Periodically calibrate per-topic relevance thresholds from score distributions."""
    from .relevance import calibrate_topic_thresholds

    log.info(
        "scheduler.relevance_calibration.started",
        interval_s=settings.relevance_calibration_interval_s,
    )
    # Run immediately on startup for fast initial convergence
    try:
        updated = await calibrate_topic_thresholds(pool)
        log.info("scheduler.relevance_calibration.initial_run", topics_updated=updated)
    except Exception as exc:
        log.error("scheduler.relevance_calibration.initial_error", error=str(exc))

    while True:
        await asyncio.sleep(settings.relevance_calibration_interval_s)
        try:
            updated = await calibrate_topic_thresholds(pool)
            if updated:
                log.info(
                    "scheduler.relevance_calibration.cycle_done",
                    topics_updated=updated,
                )
        except Exception as exc:
            log.error("scheduler.relevance_calibration.error", error=str(exc))


# ---------------------------------------------------------------------------
# Engine C — Identifier Clustering
# ---------------------------------------------------------------------------

# Engine C identifier types (must match identifiers.py extraction output)
_ENGINE_C_TYPES = (
    "PHONE_IN",
    "PHONE_INTL",
    "UPI",
    "EMAIL",
    "CRYPTO_BTC",
    "CRYPTO_ETH",
    "CRYPTO_TRC20",
    "TELEGRAM_HANDLE",
    "INSTAGRAM_HANDLE",
    "FACEBOOK_HANDLE",
    "X_HANDLE",
    "URL_DOMAIN",
    "GSTIN",
    "UDYAM",
    "PAN",
    "BANK_ACCOUNT",
    "SEBI_REG",
    "IFSC",
)

SQL_UNCLUSTERED_IDENTIFIERS = """
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.source_id, ci.captured_at,
           ci.topic_id
    FROM extracted_entities ee
    JOIN content_items ci ON ci.id = ee.content_item_id
    WHERE ci.topic_id = $1
      AND ee.entity_type = ANY($2)
      AND NOT EXISTS (
          SELECT 1 FROM identifier_cluster_items ici
          WHERE ici.content_item_id = ee.content_item_id
            AND ici.identifier_cluster_id IN (
                SELECT ic.id FROM identifier_clusters ic
                WHERE ic.identifier_type = ee.entity_type
                  AND ic.identifier_value = ee.entity_text
                  AND ic.topic_id = ci.topic_id
            )
      )
    LIMIT 1000
"""

SQL_UPSERT_IDENTIFIER_CLUSTER = """
    INSERT INTO identifier_clusters (
        id, topic_id, identifier_type, identifier_value,
        source_count, content_item_count,
        first_seen_at, last_seen_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (topic_id, identifier_type, identifier_value)
    DO UPDATE SET
        source_count = EXCLUDED.source_count,
        content_item_count = EXCLUDED.content_item_count,
        last_seen_at = EXCLUDED.last_seen_at
    RETURNING id
"""

SQL_INSERT_IDENTIFIER_CLUSTER_ITEM = """
    INSERT INTO identifier_cluster_items (
        identifier_cluster_id, content_item_id, source_id
    )
    VALUES ($1, $2, $3)
    ON CONFLICT DO NOTHING
"""


async def _run_identifier_cluster_cycle(pool: asyncpg.Pool) -> int:
    """One pass: query unclustered identifiers per topic, build clusters, upsert to DB.

    Returns total clusters upserted.
    """
    total = 0

    async with pool.acquire() as conn:
        topics = await conn.fetch(SQL_ACTIVE_TOPICS)

    for topic_row in topics:
        topic_id = topic_row["id"]
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    SQL_UNCLUSTERED_IDENTIFIERS,
                    topic_id,
                    list(_ENGINE_C_TYPES),
                )

            if not rows:
                continue

            # Build ContentIdentifier objects
            identifiers = [
                ContentIdentifier(
                    identifier_type=r["entity_type"],
                    normalized_value=r["entity_text"],
                    content_item_id=r["content_item_id"],
                    source_id=r["source_id"],
                    seen_at=r["captured_at"],
                )
                for r in rows
            ]

            clusters = build_clusters(identifiers)

            if not clusters:
                continue

            async with pool.acquire() as conn:
                async with conn.transaction():
                    for cluster in clusters:
                        row = await conn.fetchrow(
                            SQL_UPSERT_IDENTIFIER_CLUSTER,
                            str(uuid.uuid4()),
                            topic_id,
                            cluster.identifier_type,
                            cluster.identifier_value,
                            cluster.source_count,
                            cluster.content_item_count,
                            cluster.first_seen_at,
                            cluster.last_seen_at,
                        )
                        cluster_id = row["id"]

                        for ci_id in cluster.content_item_ids:
                            # Find the source_id for this content item
                            source_id = next(
                                (i.source_id for i in identifiers if i.content_item_id == ci_id),
                                None,
                            )
                            if source_id:
                                await conn.execute(
                                    SQL_INSERT_IDENTIFIER_CLUSTER_ITEM,
                                    cluster_id,
                                    ci_id,
                                    source_id,
                                )

                        total += 1
                        analyst_identifier_clusters_total.inc()

            log.info(
                "scheduler.identifier_cluster.topic_done",
                topic_id=topic_id,
                clusters=len(clusters),
            )

        except Exception as exc:
            log.warning(
                "scheduler.identifier_cluster.topic_failed",
                topic_id=topic_id,
                error=str(exc),
            )

    return total


async def identifier_cluster_loop(pool: asyncpg.Pool) -> None:
    """Periodic loop: build identifier clusters at configured interval."""
    interval = settings.identifier_cluster_interval_s
    log.info("scheduler.identifier_cluster_loop.started", interval_s=interval)
    while True:
        await asyncio.sleep(interval)
        try:
            total = await _run_identifier_cluster_cycle(pool)
            if total:
                log.info(
                    "scheduler.identifier_cluster_loop.cycle_done",
                    clusters_upserted=total,
                )
        except Exception as exc:
            log.error("scheduler.identifier_cluster_loop.error", error=str(exc))


# ---------------------------------------------------------------------------
# Tracker auto-matching
# ---------------------------------------------------------------------------


SQL_ACTIVE_TRACKERS = """
    SELECT t.id, t.topic_id, t.centroid, t.centroid_threshold
    FROM trackers t
    WHERE t.status IN ('watching', 'active')
      AND t.centroid IS NOT NULL
"""

SQL_TRACKER_CANDIDATES = """
    SELECT ci.id, 1 - (ci.embedding <=> $1) AS similarity
    FROM content_items ci
    WHERE (ci.topic_id = $2
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $2))
      AND ci.embedding IS NOT NULL
      AND ci.captured_at >= NOW() - INTERVAL '24 hours'
      AND ci.id NOT IN (SELECT content_item_id FROM tracker_content_items WHERE tracker_id = $3)
      AND ci.id NOT IN (SELECT content_item_id FROM tracker_content_exclusions WHERE tracker_id = $3)
      AND 1 - (ci.embedding <=> $1) >= $4
    ORDER BY similarity DESC
    LIMIT 50
"""

SQL_INSERT_TRACKER_PENDING = """
    INSERT INTO tracker_content_items (
        tracker_id, content_item_id, attached_by, status, similarity_score, attached_at
    ) VALUES ($1, $2, 'auto', 'pending', $3, NOW())
    ON CONFLICT DO NOTHING
"""


async def _run_tracker_matching_cycle(pool: asyncpg.Pool) -> int:
    """Match newly processed content against active tracker centroids.

    Runs AFTER clustering completes. Inserts matches as 'pending' —
    analyst must accept/reject via review queue. Never auto-inserts.
    """
    total = 0
    async with pool.acquire() as conn:
        trackers = await conn.fetch(SQL_ACTIVE_TRACKERS)

        for tracker in trackers:
            try:
                candidates = await conn.fetch(
                    SQL_TRACKER_CANDIDATES,
                    tracker["centroid"],
                    tracker["topic_id"],
                    tracker["id"],
                    tracker["centroid_threshold"],
                )

                for item in candidates:
                    await conn.execute(
                        SQL_INSERT_TRACKER_PENDING,
                        tracker["id"],
                        item["id"],
                        item["similarity"],
                    )
                    total += 1

                if candidates:
                    log.info(
                        "scheduler.tracker_matching.matched",
                        tracker_id=tracker["id"],
                        candidates=len(candidates),
                    )
            except Exception as exc:
                log.warning(
                    "scheduler.tracker_matching.error",
                    tracker_id=tracker["id"],
                    error=str(exc),
                )

    return total


async def tracker_matching_loop(pool: asyncpg.Pool) -> None:
    """Periodic loop: match new content to active tracker centroids."""
    interval = settings.identifier_cluster_interval_s
    log.info("scheduler.tracker_matching_loop.started", interval_s=interval)
    while True:
        await asyncio.sleep(interval)
        try:
            total = await _run_tracker_matching_cycle(pool)
            if total:
                log.info("scheduler.tracker_matching_loop.cycle_done", pending_items=total)
        except Exception as exc:
            log.error("scheduler.tracker_matching_loop.error", error=str(exc))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
# Source Discovery + Effectiveness loops
# ---------------------------------------------------------------------------


async def discovery_loop(pool: asyncpg.Pool, redis: ArqRedis) -> None:
    """Daily loop: run all discovery methods for each active topic.

    Runs once immediately on startup, then every 24 hours.
    Snowball + forwarding run inline (lightweight SQL).
    LLM suggestions dispatched via ARQ (AGENTS.md rule 5).
    """
    while True:
        try:
            async with pool.acquire() as conn:
                topics = await conn.fetch(SQL_ACTIVE_TOPICS)

            for row in topics:
                topic_id = row["id"]
                try:
                    await discover_snowball_sources(pool, topic_id)
                    await discover_telegram_channels(pool, topic_id)
                    await discover_entity_sources(pool, topic_id)
                    # LLM suggestions dispatched to ARQ worker (rule 5: async LLM)
                    await redis.enqueue_job(
                        "suggest_source_types_job",
                        topic_id,
                        _queue_name="arq:analyst",
                    )
                except Exception as exc:
                    log.warning(
                        "scheduler.discovery.topic_error", topic_id=topic_id, error=str(exc)
                    )

        except Exception as exc:
            log.error("scheduler.discovery.error", error=str(exc))
        await asyncio.sleep(86400)  # daily


async def effectiveness_loop(pool: asyncpg.Pool) -> None:
    """Weekly loop: compute source effectiveness analytics.

    Runs once immediately on startup, then every 7 days.
    """
    while True:
        try:
            await compute_source_effectiveness(pool)
        except Exception as exc:
            log.error("scheduler.effectiveness.error", error=str(exc))
        await asyncio.sleep(604800)  # weekly (7 days)


# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler loops as background tasks."""
    from anveshak.db import create_db_pool

    pool = await create_db_pool(settings.postgres_url)
    redis = await create_redis_pool(RedisSettings.from_dsn(settings.redis_url))

    log.info("scheduler.ready")

    tasks = [
        asyncio.create_task(cluster_loop(pool, redis)),
        asyncio.create_task(signal_check_loop(pool)),
        asyncio.create_task(convergence_loop(pool)),
        asyncio.create_task(orphan_sweep(pool, redis)),
        asyncio.create_task(content_retention_loop(pool)),
        asyncio.create_task(relevance_calibration_loop(pool)),
        asyncio.create_task(discovery_loop(pool, redis)),
        asyncio.create_task(effectiveness_loop(pool)),
        asyncio.create_task(identifier_cluster_loop(pool)),
        asyncio.create_task(tracker_matching_loop(pool)),
    ]

    yield

    for t in tasks:
        t.cancel()
    await pool.close()


app = FastAPI(title="Anveshak Analyst Scheduler", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "analyst-scheduler"}


@app.get("/metrics")
async def metrics():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        generate_latest(ANALYST_REGISTRY).decode(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.post("/internal/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    """Encode texts to normalised embedding vectors.

    Used by API (/search) and reporter (RAG) to avoid installing
    PyTorch/sentence-transformers in those lighter containers.
    """
    encoder = _get_encoder()
    vectors = encoder.encode(req.texts, normalize_embeddings=True)
    return EmbedResponse(embeddings=[v.tolist() for v in vectors])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    """Start the analyst scheduler with FastAPI + background loops."""
    config = uvicorn.Config(
        app,
        # metrics endpoint inside a container; must bind all interfaces to be reachable
        host="0.0.0.0",  # nosec B104
        port=settings.metrics_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
