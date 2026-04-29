"""ARQ worker for the reporter service — M5: LLM report generation.

Jobs:
  generate_report   — RAG → LLM → geocode → store. Idempotent via generated_at IS NULL guard.

Cron jobs:
  check_scheduled_reports — every 15 min. Evaluate cron expressions on topics.
  check_source_warnings   — every 6 h. Detect credibility downgrades on cited sources.

CLAUDE.md rules enforced:
  Rule 4 : generated_at set ONCE via WHERE generated_at IS NULL.
  Rule 5 : All LLM calls are async background jobs (this module).
  Rule 9 : LLM output validated through Pydantic before storage.
"""
from __future__ import annotations

import json
from datetime import datetime, UTC, timedelta
from typing import Any

import arq
import structlog
from arq.connections import RedisSettings
from croniter import croniter
from anveshak.logging import configure_logging

configure_logging("reporter")

from . import db as db
from .geocoder import build_geojson, extract_locations_from_text, geocode_locations
from .llm import call_ollama_with_retry
from .metrics import reporter_jobs_total, reporter_job_duration_seconds, reporter_ollama_errors_total, arq_jobs_failed_total
from .prompt_templates import render_prompt
from .rag import assemble_context, generate_query_embedding
from .settings import settings as _default_settings

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

async def startup(ctx: dict) -> None:
    """Create DB pool, start Prometheus metrics server, attach settings to ARQ context."""
    from prometheus_client import start_http_server
    from .metrics import REGISTRY as REPORTER_REGISTRY

    start_http_server(_default_settings.metrics_port, registry=REPORTER_REGISTRY)
    log.info("reporter.metrics_server_started", port=_default_settings.metrics_port)

    ctx["settings"] = _default_settings
    ctx["db"] = await db.get_pool(_default_settings.postgres_url)
    log.info("reporter.worker_started")


async def shutdown(ctx: dict) -> None:
    """Close DB pool."""
    pool = ctx.get("db")
    if pool:
        await pool.close()
    log.info("reporter.worker_stopped")


# ---------------------------------------------------------------------------
# generate_report — main ARQ job
# ---------------------------------------------------------------------------

async def generate_report(ctx: dict, report_id: str) -> None:
    """RAG → LLM → geocode → store.

    Idempotent: the UPDATE uses WHERE generated_at IS NULL so a duplicate
    dispatch results in a no-op (set_report_generated returns False).
    """
    import time as _time
    _t0 = _time.monotonic()

    pool = ctx["db"]
    s = ctx["settings"]

    log.info("reporter.generate_report.start", report_id=report_id)

    # --- 1. Load report and topic rows ---
    report = await db.fetch_report(pool, report_id)
    if report is None:
        log.error("reporter.report_not_found", report_id=report_id)
        return

    topic_id: str = report["topic_id"]
    topic = await db.fetch_topic(pool, topic_id)
    if topic is None:
        log.error("reporter.topic_not_found", topic_id=topic_id)
        await db.set_report_failed(pool, report_id, "Topic not found — it may have been deleted.")
        return

    topic_name: str = topic.get("name", "Unknown Topic")
    keywords: list[str] = topic.get("keywords") or []
    credibility_min: float = float(report.get("credibility_min_filter", 30.0))
    report_type: str = report.get("report_type", "intelligence_brief")

    # --- 2. Generate query embedding ---
    query_embedding = generate_query_embedding(topic_name, keywords, s.embedding_model)

    # --- 3. Fetch RAG chunks ---
    chunks = await db.fetch_rag_chunks(
        pool,
        topic_id,
        query_embedding,
        credibility_min,
        s.rag_top_k,
    )

    if not chunks:
        log.warning("reporter.no_rag_chunks", report_id=report_id, topic_id=topic_id)
        await db.set_report_failed(
            pool, report_id,
            "No scraped content available for this topic yet. "
            "Add sources to the topic and run a scrape job first, then generate the report."
        )
        return

    # --- 4. Assemble context and render prompt ---
    context, source_count, date_range = assemble_context(chunks, max_tokens=s.rag_max_context_tokens)
    prompt = render_prompt(
        report_type, topic_name, keywords, context,
        source_count=source_count, date_range=date_range,
    )

    # --- 5. Call LLM ---
    report_content = await call_ollama_with_retry(prompt, s, max_retries=s.ollama_retry_max)

    if report_content is None:
        reporter_ollama_errors_total.labels(error_type="no_valid_output").inc()
        reporter_jobs_total.labels(status="failed").inc()
        reporter_job_duration_seconds.observe(_time.monotonic() - _t0)
        log.error("reporter.llm_failed", report_id=report_id)
        await db.set_report_failed(
            pool, report_id,
            "LLM returned no valid output. Check that Ollama is running and the configured model is loaded "
            f"(model: {s.ollama_model})."
        )
        return

    # --- 6. Build source snapshot ---
    source_ids = list({c["source_id"] for c in chunks if c.get("source_id")})
    sources = await db.fetch_sources_for_snapshot(pool, source_ids)

    # --- 7. Geocode locations (3-layer: NER entities → regex fallback → custom overlay) ---
    # Layer 1: High-quality NER entities from the analyst pipeline
    ner_entities = await db.fetch_topic_location_entities(pool, topic_id)
    # Layer 2: Regex extraction from LLM output (catches synthesized locations)
    combined_text = " ".join(
        [report_content.executive_summary]
        + report_content.key_findings
        + report_content.recommendations
    )
    regex_names = extract_locations_from_text(combined_text)
    # Merge (NER first, regex adds any extras) — dedup by lowercase key
    seen_lower: set[str] = set()
    location_names: list[str] = []
    for name in ner_entities + regex_names:
        key = name.lower().strip()
        if key not in seen_lower:
            seen_lower.add(key)
            location_names.append(name)
    # Layer 3: custom overlay is handled inside geocode_locations()
    locations = geocode_locations(location_names)
    geojson = build_geojson(locations)

    # --- 8. Build content_md (Markdown format) ---
    content_md = _build_content_md(report_content)

    # --- 9. Store (idempotent via generated_at IS NULL guard) ---
    stored = await db.set_report_generated(
        pool,
        report_id=report_id,
        content_md=content_md,
        confidence_score=report_content.confidence_level,
        geojson=geojson,
        source_snapshot=sources,
        content_item_count=len(chunks),
    )

    if stored:
        reporter_jobs_total.labels(status="success").inc()
        reporter_job_duration_seconds.observe(_time.monotonic() - _t0)
        log.info(
            "reporter.report_generated",
            report_id=report_id,
            chunks=len(chunks),
            confidence=report_content.confidence_level,
        )
        await db.update_job_status(pool, report_id, "complete")
    else:
        # set_report_generated returned False → already generated (race or duplicate job)
        log.info("reporter.report_already_generated", report_id=report_id)


def _build_content_md(rc: Any) -> str:
    """Convert a ReportContent object to Markdown string."""
    lines = [
        f"## Executive Summary\n\n{rc.executive_summary}\n",
        "## Key Findings\n",
    ]
    for finding in rc.key_findings:
        lines.append(f"- {finding}")
    lines.append("\n## Recommendations\n")
    for rec in rc.recommendations:
        lines.append(f"- {rec}")
    lines.append("\n## Source Citations\n")
    for citation in rc.source_citations:
        lines.append(f"- {citation}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# check_scheduled_reports — cron every 15 min
# ---------------------------------------------------------------------------

async def check_scheduled_reports(ctx: dict) -> None:
    """Evaluate scheduled_report_cron on each active topic.

    Uses croniter to determine if the cron expression has fired since the
    last report was generated for that topic.
    """
    pool = ctx["db"]
    s = ctx["settings"]

    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        topics = await conn.fetch("""
            SELECT id, name, keywords, scheduled_report_cron, scheduled_report_type,
                   credibility_min,
                   (SELECT MAX(created_at) FROM reports r WHERE r.topic_id = t.id) AS last_report_at
            FROM topics t
            WHERE status = 'active'
              AND scheduled_report_cron IS NOT NULL
        """)

    for topic in topics:
        cron_expr: str = topic["scheduled_report_cron"]
        last_at: datetime | None = topic["last_report_at"]

        try:
            cron = croniter(cron_expr, last_at or (now - timedelta(hours=25)))
            next_fire = cron.get_next(datetime)
        except Exception as exc:
            log.warning(
                "reporter.invalid_cron",
                topic_id=topic["id"],
                cron=cron_expr,
                error=str(exc),
            )
            continue

        if next_fire <= now:
            # Create report row and enqueue job
            import uuid
            from . import db as dbmod

            report_id = str(uuid.uuid4())
            report_type = topic.get("scheduled_report_type") or "intelligence_brief"
            time_end = now
            time_start = now - timedelta(hours=168)  # 7-day window for weekly digest

            await dbmod.create_report_row(
                pool,
                report_id=report_id,
                topic_id=topic["id"],
                report_type=report_type,
                time_window_start=time_start,
                time_window_end=time_end,
                credibility_min=float(topic.get("credibility_min", 30.0)),
            )

            arq_pool = ctx.get("arq_pool")
            if arq_pool:
                await arq_pool.enqueue_job("generate_report", report_id)
                log.info(
                    "reporter.scheduled_report_enqueued",
                    topic_id=topic["id"],
                    report_id=report_id,
                )


# ---------------------------------------------------------------------------
# check_source_warnings — cron every 6 h
# ---------------------------------------------------------------------------

async def check_source_warnings(ctx: dict) -> None:
    """Detect credibility downgrades on sources cited in recent reports.

    Compares current source credibility_score against source_snapshot saved
    at report generation time. Inserts a report_source_warnings row if downgraded.
    CLAUDE.md rule 8: credibility changes are audit-logged.
    """
    pool = ctx["db"]
    s = ctx["settings"]

    reports = await db.fetch_reports_for_warning_check(pool, s.source_warning_lookback_days)

    for report in reports:
        snapshot = report.get("source_snapshot") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except (json.JSONDecodeError, TypeError):
                continue
        if not snapshot:
            continue

        source_ids = list(snapshot.keys())
        current_sources = await db.fetch_sources_for_snapshot(pool, source_ids)

        for source_id, snap_data in snapshot.items():
            current = current_sources.get(source_id)
            if current is None:
                continue
            old_score = float(snap_data.get("credibility_score", 100.0))
            new_score = float(current.get("credibility_score", 100.0))

            if new_score < old_score:
                await db.insert_source_warning(
                    pool,
                    report_id=report["id"],
                    source_id=source_id,
                    source_name=current.get("name", source_id),
                    old_score=old_score,
                    new_score=new_score,
                )


# ---------------------------------------------------------------------------
# ARQ WorkerSettings
# ---------------------------------------------------------------------------

async def on_job_result(ctx: dict, result) -> None:  # type: ignore[type-arg]
    """8A.19 — increment failure counter when an ARQ job exhausts all retries."""
    if getattr(result, "success", True) is False:
        job_name = getattr(result, "function", "unknown")
        arq_jobs_failed_total.labels(job_name=job_name).inc()
        reporter_jobs_total.labels(status="failed").inc()
        log.warning("reporter_worker.job_failed", job=job_name)


class WorkerSettings:
    queue_name = "arq:reporter"  # Isolated queue — avoids cross-worker job theft
    redis_settings = RedisSettings.from_dsn(_default_settings.redis_url)
    functions = [
        # 8C.4 — generate_report: max_tries=2; retry safe via generated_at IS NULL guard (8C.7)
        arq.func(generate_report, max_tries=2),
    ]
    cron_jobs = [
        arq.cron(check_scheduled_reports, minute={0, 15, 30, 45}),
        arq.cron(check_source_warnings, hour={0, 6, 12, 18}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    on_job_result = on_job_result
    job_timeout = 600    # 8C.4 — Ollama report generation ceiling (600s for CPU inference)
    keep_result = 3600   # 8C.6 — keep results 1h for UI polling
