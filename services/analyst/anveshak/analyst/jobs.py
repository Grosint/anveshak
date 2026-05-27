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
from .metrics import (
    analyst_nlp_jobs_total, analyst_nlp_duration_seconds,
    analyst_clusters_created_total, analyst_relevance_score, arq_jobs_failed_total,
    analyst_embedding_completed_total, analyst_content_skipped_quality_total,
)
from .nlp import detect_language, is_model_loaded, load_models, parse_entities
from .settings import settings
from .keywords import extract_keywords
from .sentiment import analyse_sentiment
from .translation import needs_translation, translate_to_english
from .content_quality import is_quality_content
from .relevance import compute_topic_relevance, build_topic_query_embedding
from .entity_minhash import compute_entity_minhash
from .llm_discovery import suggest_source_types_job

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_GET_CONTENT = """
    SELECT ci.id, ci.clean_text, ci.topic_id,
           t.name AS topic_name, t.keywords AS topic_keywords,
           t.topic_relevance_threshold
    FROM content_items ci
    JOIN topics t ON ci.topic_id = t.id
    WHERE ci.id = $1
"""

SQL_UPDATE_CONTENT_NLP = """
    UPDATE content_items
    SET embedding              = $1::vector,
        language               = $2,
        translated_text        = $3,
        translation_model      = $4,
        labels                 = $5::jsonb,
        updated_at             = $6,
        topic_relevance_score  = $7,
        entity_minhash         = $9
    WHERE id = $8
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
    """NLP pipeline: langdetect → translate → spaCy NER → sentence embedding → DB.

    For non-English articles (zh, hi, ar, ur, ru):
      1. Detects language via langdetect
      2. Translates clean_text → English via NLLB-200 (stored as translated_text)
      3. Runs English NER on translated text — entities come out in English
      4. Embeds translated text — all vectors in English semantic space
      5. Writes embedding, language, translated_text, translation_model to content_items

    For English articles: translation step is skipped; clean_text used directly.

    Criteria 1.11–1.16.
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

    # --- Quality gate: skip embedding for boilerplate/nav text ---
    quality_passed, quality_gate = is_quality_content(clean_text)
    if not quality_passed:
        log.info(
            "analyst.content_skipped_quality",
            content_item_id=content_item_id,
            text_len=len(clean_text),
            gate=quality_gate,
        )
        analyst_nlp_jobs_total.labels(status="skipped").inc()
        analyst_content_skipped_quality_total.labels(gate=quality_gate).inc()
        return

    try:
        # --- Step 1: Language detection (criteria 1.12, 1.13) ---
        lang = detect_language(clean_text)

        # --- Step 2: Translation (non-English → English) ---
        translated_text: str | None = None
        translation_model_used: str | None = None

        if settings.translation_enabled and needs_translation(lang):
            translated_text = translate_to_english(clean_text, lang)
            if translated_text:
                translation_model_used = settings.translation_model
                log.info(
                    "analyst.translated",
                    content_item_id=content_item_id,
                    src_lang=lang,
                    model=translation_model_used,
                )
            else:
                # Translation failed — fall back to original text and warn
                log.warning(
                    "analyst.translation_failed_fallback",
                    content_item_id=content_item_id,
                    lang=lang,
                )

        # work_text: what NER and embedding operate on.
        # Use English translation if available; fall back to original.
        work_text = translated_text if translated_text else clean_text

        # --- Step 3: NER on work_text (English after translation) (criteria 1.14) ---
        # Always use English model when work_text is the translated version.
        nlp_lang = "en" if translated_text else lang
        if is_model_loaded(nlp_lang):
            entities = parse_entities(work_text, nlp_lang)
        else:
            log.error(
                "analyst.ner_unavailable",
                lang=nlp_lang,
                content_item_id=content_item_id,
                hint=f"spaCy model for '{nlp_lang}' not loaded — NER skipped",
            )
            entities = []

        # --- Step 4: Embedding on work_text (English semantic space) (criteria 1.15) ---
        embedding = encode_text(work_text)
        # pgvector expects "[x1,x2,...]" string when using $1::vector cast in asyncpg
        embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

        # --- Step 4a: Topic relevance score ---
        topic_query_emb = build_topic_query_embedding(
            row["topic_name"], list(row["topic_keywords"] or []),
        )
        relevance_score = compute_topic_relevance(embedding, topic_query_emb)
        analyst_relevance_score.observe(relevance_score)

        # --- Step 4b: Sentiment + keyword extraction (CPU-only, no extra ML) ---
        sentiment = analyse_sentiment(work_text)
        kw_results = extract_keywords(work_text, language="en", max_keywords=10)

        import json
        labels_dict = {
            "classification": "OPEN",
            "domain": "osint",
            "owner_org": "anveshak",
            "sentiment": {
                "compound": sentiment.compound,
                "positive": sentiment.positive,
                "negative": sentiment.negative,
                "neutral": sentiment.neutral,
            },
            "keywords": [kw.keyword for kw in kw_results],
        }
        labels_json = json.dumps(labels_dict)

        now = datetime.now(UTC)

        # --- Step 4c: Entity MinHash fingerprint for clustering boost ---
        entity_texts = [ent.entity_text for ent in entities]
        minhash = compute_entity_minhash(entity_texts, settings.minhash_num_perm)

        # --- Step 5: Write to DB (criteria 1.16) ---
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    SQL_UPDATE_CONTENT_NLP,
                    embedding_str, lang, translated_text, translation_model_used,
                    labels_json, now, relevance_score, content_item_id, minhash,
                )
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
        analyst_embedding_completed_total.inc()
        analyst_nlp_duration_seconds.observe(_time.monotonic() - _t0)
        log.info(
            "analyst.content_analysed",
            content_item_id=content_item_id,
            language=lang,
            translated=translated_text is not None,
            entities=len(entities),
            topic_relevance_score=round(relevance_score, 4),
        )
    except Exception:
        analyst_nlp_jobs_total.labels(status="failed").inc()
        raise


# ---------------------------------------------------------------------------
# Phase 2 ARQ jobs
# ---------------------------------------------------------------------------

async def run_clustering(ctx: dict, topic_id: str) -> None:
    """Leiden clustering for a topic (criteria 2.1–2.5).

    Creates/updates narrative_clusters rows and enqueues label generation
    for each cluster formed. Also enqueues cross-verification boost (7.1)
    so the feedback loop fires immediately after fresh clusters exist.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    cluster_ids = await _run_clustering(topic_id, db_pool)

    from arq import create_pool
    redis = await create_pool(WorkerSettings.redis_settings)

    # Enqueue label generation only for stale/new clusters (criteria 2.6, P3)
    from .labeller import check_label_staleness
    for cluster_id in cluster_ids:
        if await check_label_staleness(cluster_id, db_pool):
            await redis.enqueue_job("generate_cluster_label", cluster_id, _queue_name="arq:analyst")

    # Enqueue cross-verification boost for this topic (7.1)
    if cluster_ids:
        await redis.enqueue_job("run_cross_verification", topic_id, _queue_name="arq:analyst")

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


async def backfill_all_topics(ctx: dict) -> None:
    """Periodic backfill for all active topics (replaces backfill_loop in main.py).

    Registered as an ARQ cron job — runs every 6 hours.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM topics WHERE status = 'active'")
    for row in rows:
        try:
            inserted = await _backfill_topic(row["id"], db_pool)
            if inserted:
                log.info("jobs.backfill_all.topic_done",
                         topic_id=row["id"], inserted=inserted)
        except Exception as exc:
            log.warning("jobs.backfill_all.topic_failed",
                        topic_id=row["id"], error=str(exc))


# ---------------------------------------------------------------------------
# One-time backfill: score existing content items that have embeddings but
# no topic_relevance_score (populated after migration 009).
# ---------------------------------------------------------------------------

SQL_UNSCORED_ITEMS_BY_TOPIC = """
    SELECT ci.id, ci.embedding::text AS embedding_text, ci.topic_id,
           t.name AS topic_name, t.keywords AS topic_keywords
    FROM content_items ci
    JOIN topics t ON ci.topic_id = t.id
    WHERE ci.embedding IS NOT NULL
      AND ci.topic_relevance_score IS NULL
    ORDER BY ci.topic_id, ci.captured_at ASC
    LIMIT $1
"""

SQL_UPDATE_RELEVANCE_SCORE = """
    UPDATE content_items SET topic_relevance_score = $1, updated_at = $2
    WHERE id = $3
"""


async def backfill_relevance_scores(ctx: dict) -> None:
    """One-time job: compute topic_relevance_score for existing content items.

    Groups by topic_id to compute each topic query embedding once.
    Processes in batches of 500 to avoid OOM.
    """
    db_pool: asyncpg.Pool = ctx["db_pool"]
    batch_size = 500
    total_scored = 0

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(SQL_UNSCORED_ITEMS_BY_TOPIC, batch_size)

    if not rows:
        log.info("backfill_relevance.nothing_to_score")
        return

    # Cache topic query embeddings to avoid recomputing per item
    topic_cache: dict[str, list[float]] = {}
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            for row in rows:
                tid = row["topic_id"]
                if tid not in topic_cache:
                    topic_cache[tid] = build_topic_query_embedding(
                        row["topic_name"], list(row["topic_keywords"] or []),
                    )

                from .clustering import _parse_pgvector
                content_vec = _parse_pgvector(row["embedding_text"]).tolist()
                score = compute_topic_relevance(content_vec, topic_cache[tid])

                await conn.execute(
                    SQL_UPDATE_RELEVANCE_SCORE, score, now, row["id"],
                )
                total_scored += 1

    log.info("backfill_relevance.done", scored=total_scored)

    # If there are more items, re-enqueue self
    if total_scored >= batch_size:
        from arq import create_pool
        redis = await create_pool(WorkerSettings.redis_settings)
        await redis.enqueue_job("backfill_relevance_scores", _queue_name="arq:analyst")
        log.info("backfill_relevance.re_enqueued", reason="more items remaining")


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
        backfill_all_topics,
        arq.func(run_cross_verification, max_tries=2),
        backfill_relevance_scores,
        arq.func(suggest_source_types_job, max_tries=2),
    ]
    cron_jobs = [
        arq.cron(run_contradiction_scoring, hour={2}),       # 7.2 — daily at 02:00 UTC
        arq.cron(update_source_credibility, hour={3}),       # 2.21 — daily at 03:00 UTC
        arq.cron(backfill_all_topics, hour={0, 6, 12, 18}),  # 2.9 — every 6 hours
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    on_job_result = on_job_result
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300    # increased from 180s — translation adds ~30s per article on CPU
    keep_result = 3600   # 8C.6 — keep results 1h for UI polling
