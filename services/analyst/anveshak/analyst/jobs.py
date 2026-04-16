"""ARQ job definitions — Analyst service (criteria 1.11–1.18, 2.1–2.8).

WorkerSettings is the entry point for `arq services.analyst.jobs.WorkerSettings`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import arq
import asyncpg
import structlog
from arq.connections import RedisSettings

from .backfill import backfill_topic as _backfill_topic
from .clustering import run_clustering as _run_clustering
from .credibility import run_credibility_update, run_cross_verification_update, run_contradiction_update
from .embeddings import encode_text, load_encoder
from .labeller import generate_label_for_cluster
from .metrics import analyst_nlp_jobs_total, analyst_nlp_duration_seconds, analyst_clusters_created_total, arq_jobs_failed_total
from .nlp import detect_language, load_models, parse_entities
from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_GET_CONTENT = """
    SELECT id, clean_text
    FROM content_items
    WHERE id = $1
"""

SQL_UPDATE_CONTENT_NLP = """
    UPDATE content_items
    SET embedding = $1::vector,
        language  = $2,
        updated_at = $3
    WHERE id = $4
"""

SQL_INSERT_ENTITY = """
    INSERT INTO extracted_entities (
        id, content_item_id, entity_type, entity_text, confidence,
        language, created_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""

_LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


# ---------------------------------------------------------------------------
# ARQ job
# ---------------------------------------------------------------------------

async def analyse_content(ctx: dict, content_item_id: str) -> None:
    """NLP pipeline: langdetect → spaCy NER → sentence embedding → DB (criteria 1.11–1.16).

    Writes embedding + language to content_items.
    Inserts rows into extracted_entities.
    Both writes are in a single transaction.
    """
    import time as _time
    _t0 = _time.monotonic()

    db_pool: asyncpg.Pool = ctx["db_pool"]

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(SQL_GET_CONTENT, content_item_id)

    if not row:
        log.warning("analyst.content_not_found", content_item_id=content_item_id)
        analyst_nlp_jobs_total.labels(status="failed").inc()
        return

    clean_text: str = row["clean_text"]

    try:
        # Language detection (criteria 1.12, 1.13)
        lang = detect_language(clean_text)

        # NER (criteria 1.14)
        entities = parse_entities(clean_text, lang)

        # Embedding (criteria 1.15)
        embedding = encode_text(clean_text)
        # pgvector expects "[x1,x2,...]" string when using $1::vector cast in asyncpg
        embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

        now = datetime.now(UTC)

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # criteria 1.16: UPDATE content_items SET embedding, language
                await conn.execute(
                    SQL_UPDATE_CONTENT_NLP,
                    embedding_str, lang, now, content_item_id,
                )
                # criteria 1.14: insert extracted_entities rows
                for ent in entities:
                    await conn.execute(
                        SQL_INSERT_ENTITY,
                        str(uuid.uuid4()),
                        content_item_id,
                        ent.entity_type,
                        ent.entity_text,
                        ent.confidence,
                        ent.language,
                        now,
                        _LABELS_JSON,
                    )

        analyst_nlp_jobs_total.labels(status="success").inc()
        analyst_nlp_duration_seconds.observe(_time.monotonic() - _t0)
        log.info(
            "analyst.content_analysed",
            content_item_id=content_item_id,
            language=lang,
            entities=len(entities),
        )
    except Exception:
        analyst_nlp_jobs_total.labels(status="failed").inc()
        raise


# ---------------------------------------------------------------------------
# Phase 2 ARQ jobs
# ---------------------------------------------------------------------------

async def run_clustering(ctx: dict, topic_id: str) -> None:
    """HDBSCAN clustering for a topic (criteria 2.1–2.5).

    Creates/updates narrative_clusters rows and enqueues label generation
    for each cluster formed. Also enqueues cross-verification boost (7.1)
    so the feedback loop fires immediately after fresh clusters exist.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    cluster_ids = await _run_clustering(topic_id, db_pool)

    from arq import create_pool
    redis = await create_pool(WorkerSettings.redis_settings)

    # Enqueue label generation for each new/updated cluster (criteria 2.6)
    for cluster_id in cluster_ids:
        await redis.enqueue_job("generate_cluster_label", cluster_id)

    # Enqueue cross-verification boost for this topic (7.1)
    if cluster_ids:
        await redis.enqueue_job("run_cross_verification", topic_id)

    analyst_clusters_created_total.labels(topic_id=topic_id).inc(len(cluster_ids))
    log.info("jobs.run_clustering.done", topic_id=topic_id, clusters=len(cluster_ids))


async def generate_cluster_label(ctx: dict, cluster_id: str) -> None:
    """Generate and persist an Ollama-powered label for a cluster (criteria 2.6–2.8)."""
    db_pool: asyncpg.Pool = ctx["db_pool"]
    label = await generate_label_for_cluster(cluster_id, db_pool)
    log.info("jobs.generate_cluster_label.done", cluster_id=cluster_id, label=label)


async def update_source_credibility(ctx: dict) -> None:
    """Auto-update source credibility scores based on deepfake amplification (criteria 2.21–2.24)."""
    db_pool: asyncpg.Pool = ctx["db_pool"]
    await run_credibility_update(db_pool)
    log.info("jobs.update_source_credibility.done")


async def backfill_topic_job(ctx: dict, topic_id: str) -> None:
    """Backfill historically relevant content_items into a new topic (criterion 2.9).

    Embeds topic keywords and performs pgvector cosine search over the entire
    corpus.  Matching items are inserted into topic_content_items.
    Safe to re-run — ON CONFLICT DO NOTHING.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    inserted = await _backfill_topic(topic_id, db_pool)
    log.info("jobs.backfill_topic.done", topic_id=topic_id, inserted=inserted)


# ---------------------------------------------------------------------------
# Phase 7 ARQ jobs — M1 credibility hardening
# ---------------------------------------------------------------------------

async def run_cross_verification(ctx: dict, topic_id: str) -> None:
    """Boost credibility of high-credibility sources confirmed by multi-platform clusters (7.1).

    Enqueued by run_clustering — not a cron. Scoped to a single topic_id so
    only the relevant cluster data is queried.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    updated = await run_cross_verification_update(db_pool, topic_id)
    log.info("jobs.run_cross_verification.done", topic_id=topic_id, updated=updated)


async def run_contradiction_scoring(ctx: dict) -> None:
    """Daily global pass: reduce credibility for sources with high noise-item ratio (7.2).

    Registered as an ARQ cron job — runs once per day at 02:00 UTC.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    updated = await run_contradiction_update(db_pool)
    log.info("jobs.run_contradiction_scoring.done", updated=updated)


# ---------------------------------------------------------------------------
# ARQ worker lifecycle
# ---------------------------------------------------------------------------

async def on_startup(ctx: dict) -> None:
    ctx["db_pool"] = await asyncpg.create_pool(
        settings.postgres_url, min_size=2, max_size=5
    )
    # criteria 1.17, 1.18: models loaded ONCE at startup
    load_models()
    load_encoder()
    log.info("analyst_worker.ready")


async def on_shutdown(ctx: dict) -> None:
    await ctx["db_pool"].close()
    log.info("analyst_worker.stopped")


async def on_job_result(ctx: dict, result) -> None:  # type: ignore[type-arg]
    """8A.19 — increment failure counter when an ARQ job exhausts all retries."""
    if getattr(result, "success", True) is False:
        job_name = getattr(result, "function", "unknown")
        arq_jobs_failed_total.labels(job_name=job_name).inc()
        log.warning("analyst_worker.job_failed", job=job_name)


class WorkerSettings:
    """Entry point: arq services.analyst.jobs.WorkerSettings"""

    queue_name = "arq:analyst"   # Isolated queue — avoids cross-worker job theft

    functions = [
        # 8C.1 — NLP: transient DB/embedding errors; ON CONFLICT DO NOTHING makes it safe to retry
        arq.func(analyse_content, max_tries=3),
        # 8C.2 — Clustering: deterministic; retry safe
        arq.func(run_clustering, max_tries=2),
        # 8C.3 — Label generation: Ollama may need warm-up; allow 3 attempts
        arq.func(generate_cluster_label, max_tries=3),
        update_source_credibility,
        backfill_topic_job,
        arq.func(run_cross_verification, max_tries=2),
    ]
    cron_jobs = [
        arq.cron(run_contradiction_scoring, hour={2}),  # 7.2 — daily at 02:00 UTC
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_result = on_job_result
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 180    # 8C.2 — clustering is the heaviest job at ~180s on CPU
    keep_result = 3600   # 8C.6 — keep results 1h for UI polling
