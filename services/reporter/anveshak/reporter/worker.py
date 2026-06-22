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
from .llm import BlufContent, call_ollama_with_retry, call_ollama_for_assessment, call_ollama_for_bluf
from .metrics import reporter_jobs_total, reporter_job_duration_seconds, reporter_ollama_errors_total, arq_jobs_failed_total
from .prompt_templates import render_prompt, render_assessment_prompt, render_bluf_prompt
from .rag import assemble_context, assemble_identifier_context, build_recommended_actions, generate_query_embedding
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

    # --- 2. Fetch data bundle (all structured data from SQL) ---
    data_bundle = await db.fetch_report_data_bundle(pool, topic_id)
    log.info("reporter.data_bundle_fetched", report_id=report_id, topic_id=topic_id)

    # --- 3. Generate query embedding (still needed for RAG chunks) ---
    query_embedding = await generate_query_embedding(topic_name, keywords)

    # --- 4. Fetch RAG chunks ---
    tracker_id = report.get("tracker_id")
    if tracker_id:
        chunks = await db.fetch_tracker_rag_chunks(
            pool, tracker_id, query_embedding, credibility_min, s.rag_top_k,
        )
        log.info("reporter.tracker_scoped_rag", tracker_id=tracker_id, chunks=len(chunks))
    else:
        relevance_threshold = float(topic["topic_relevance_threshold"]) if topic.get("topic_relevance_threshold") is not None else s.topic_relevance_threshold
        chunks = await db.fetch_rag_chunks(
            pool, topic_id, query_embedding, credibility_min, s.rag_top_k,
            relevance_threshold=relevance_threshold,
        )

    if not chunks:
        log.warning("reporter.no_rag_chunks", report_id=report_id, topic_id=topic_id)
        await db.set_report_failed(
            pool, report_id,
            "No scraped content available for this topic yet. "
            "Add sources to the topic and run a scrape job first, then generate the report."
        )
        return

    # --- 5. Fetch identifier intelligence (Engine C Step 9) ---
    try:
        identifiers = await db.fetch_topic_identifiers(pool, topic_id)
        template_matches = await db.fetch_topic_template_matches(pool, topic_id)
    except Exception:
        log.warning("reporter.identifier_fetch_failed", report_id=report_id, topic_id=topic_id)
        identifiers = []
        template_matches = []

    # --- 6. Render BLUF prompt and call LLM (minimal — 2-3 sentences only) ---
    stats = data_bundle.get("topic_stats", {})
    clusters = data_bundle.get("clusters", [])
    stats_summary = (
        f"{stats.get('content_count', 0)} items, "
        f"{stats.get('source_count', 0)} sources, "
        f"{stats.get('cluster_count', 0)} clusters, "
        f"{stats.get('signal_count', 0)} signals"
    )
    cluster_summary = ", ".join(
        f"{c.get('label', 'Unnamed')} ({c.get('item_count', 0)} items)"
        for c in clusters[:5]
    ) or "No clusters formed yet."
    bluf_prompt = render_bluf_prompt(topic_name, stats_summary, cluster_summary)
    bluf = await call_ollama_for_bluf(bluf_prompt, s, max_retries=s.ollama_retry_max)

    if bluf is None:
        # Fallback: generate a template-driven BLUF (no LLM needed)
        bluf = BlufContent(
            bluf=f"Monitoring of '{topic_name}' collected {stats.get('content_count', 0)} items "
                 f"from {stats.get('source_count', 0)} sources, forming "
                 f"{stats.get('cluster_count', 0)} narrative clusters with "
                 f"{stats.get('signal_count', 0)} active signals.",
            confidence_level=0.0,
            labels={"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
        )
        log.info("reporter.bluf_fallback_used", report_id=report_id)

    # --- 7. Build source snapshot ---
    source_ids = list({c["source_id"] for c in chunks if c.get("source_id")})
    sources = await db.fetch_sources_for_snapshot(pool, source_ids)

    # --- 8. Geocode locations ---
    ner_entities = await db.fetch_topic_location_entities(pool, topic_id)
    regex_names = extract_locations_from_text(bluf.bluf)
    seen_lower: set[str] = set()
    location_names: list[str] = []
    for name in ner_entities + regex_names:
        key = name.lower().strip()
        if key not in seen_lower:
            seen_lower.add(key)
            location_names.append(name)
    locations = geocode_locations(location_names)
    geojson = build_geojson(locations)

    # --- 9. Build content_md (v2 data-driven markdown) ---
    content_md = _build_content_md_v2(
        bluf=bluf,
        data_bundle=data_bundle,
        identifiers=identifiers,
        template_matches=template_matches,
        report_type=report_type,
    )

    # --- 10. Store (idempotent via generated_at IS NULL guard) ---
    stored = await db.set_report_generated(
        pool,
        report_id=report_id,
        content_md=content_md,
        confidence_score=bluf.confidence_level,
        geojson=geojson,
        source_snapshot=sources,
        content_item_count=len(chunks),
    )

    if stored:
        # --- 11. Generate PDF eagerly (so API can serve it immediately) ---
        try:
            from .pdf import generate_pdf
            pdf_data = {
                "id": report_id,
                "report_type": report_type,
                "topic_name": topic_name,
                "generated_at": str(datetime.now(UTC)),
                "confidence_score": bluf.confidence_level,
                "content_item_count": len(chunks),
                "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
                "bluf": bluf.bluf,
                **data_bundle,
                "identifiers": identifiers,
                "template_matches": template_matches,
            }
            pdf_path = await generate_pdf(report_id, pdf_data, s.pdf_output_dir)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE reports SET pdf_path = $1, updated_at = NOW() WHERE id = $2",
                    pdf_path, report_id,
                )
            log.info("reporter.pdf_generated", report_id=report_id, path=pdf_path)
        except Exception as exc:
            # PDF failure is non-fatal — report content is still stored
            log.warning("reporter.pdf_generation_failed", report_id=report_id, error=str(exc))

        reporter_jobs_total.labels(status="success").inc()
        reporter_job_duration_seconds.observe(_time.monotonic() - _t0)
        log.info(
            "reporter.report_generated",
            report_id=report_id,
            chunks=len(chunks),
            confidence=bluf.confidence_level,
        )
        await db.update_job_status(pool, report_id, "complete")
    else:
        log.info("reporter.report_already_generated", report_id=report_id)


def _build_content_md(
    rc: Any,
    identifiers: list[dict[str, Any]] | None = None,
    template_matches: list[dict[str, Any]] | None = None,
) -> str:
    """Convert a ReportContent object to Markdown string.

    When identifier data is provided (Engine C Step 9), appends factual
    sections between Key Findings and Source Citations.
    """
    lines = [
        f"## Executive Summary\n\n{rc.executive_summary}\n",
        "## Key Findings\n",
    ]
    for finding in rc.key_findings:
        lines.append(f"- {finding}")
    lines.append("\n## Recommendations\n")
    for rec in rc.recommendations:
        lines.append(f"- {rec}")

    # --- Engine C Step 9: Identifier intelligence sections ---
    if identifiers:
        lines.append("\n## Identified Indicators\n")
        lines.append("| Type | Value | Sources | Items |")
        lines.append("|------|-------|---------|-------|")
        for ident in identifiers:
            itype = ident.get("identifier_type", "")
            value = ident.get("identifier_value", "")
            sc = ident.get("source_count", 0)
            ic = ident.get("content_item_count", 0)
            lines.append(f"| {itype} | {value} | {sc} | {ic} |")

    if template_matches:
        lines.append("\n## Scam Template Matches\n")
        for match in template_matches:
            display = match.get("template_display", match.get("template_name", ""))
            severity = match.get("severity", "")
            confidence = float(match.get("confidence", 0) or 0)
            count = match.get("match_count", 0)
            legal = match.get("legal_sections") or []
            lines.append(f"**{display}** — Severity: {severity}, Confidence: {confidence:.0%}, Matches: {count}")
            if legal and isinstance(legal, list):
                lines.append(f"  Legal provisions: {', '.join(legal)}")
            lines.append("")

        # Recommended actions
        actions = build_recommended_actions(template_matches)
        if actions:
            lines.append("## Recommended Actions\n")
            for action in actions:
                lines.append(f"- {action}")

    lines.append("\n## Source Citations\n")
    for citation in rc.source_citations:
        lines.append(f"- {citation}")

    # Legal sections (when include_legal_mapping was True in prompt)
    if rc.legal_sections:
        lines.append("\n## Applicable Legal Provisions\n")
        lines.append("*AI-generated mappings — require verification by a qualified legal officer.*\n")
        for mapping in rc.legal_sections:
            finding = mapping.get("finding", "")
            lines.append(f"**Finding:** {finding}\n")
            for sec in mapping.get("sections", []):
                act = sec.get("act", "")
                section = sec.get("section", "")
                desc = sec.get("description", "")
                evidence = sec.get("evidence_ref", "")
                lines.append(f"- {act} Section {section}: {desc} — Evidence: {evidence}")
            lines.append("")

    # Three-lens evaluation (when include_three_lens was True in prompt)
    if rc.three_lens:
        lines.append("\n## Annexure: Three-Lens Evaluation\n")
        evaluations = rc.three_lens.get("evaluations", [])
        for ev in evaluations:
            perspective = ev.get("perspective", "")
            risk = ev.get("risk_level", "")
            assessment = ev.get("threat_assessment", "")
            actions = ev.get("priority_actions", [])
            lines.append(f"### {perspective} (Risk: {risk})\n")
            lines.append(f"{assessment}\n")
            lines.append("**Priority Actions:**")
            for action in actions:
                lines.append(f"- {action}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# _build_content_md_v2 — data-driven markdown (v2 reports)
# ---------------------------------------------------------------------------

def _build_content_md_v2(
    bluf: BlufContent,
    data_bundle: dict[str, Any],
    identifiers: list[dict[str, Any]] | None = None,
    template_matches: list[dict[str, Any]] | None = None,
    report_type: str = "intelligence_brief",
) -> str:
    """Build data-driven markdown report from SQL data with minimal LLM narrative.

    Sections included vary by report_type:
    - intelligence_brief: compact (top 10 sources/entities, active signals, no evidence appendix)
    - research_summary: full (all sources, top 30 entities, evidence appendix, methodology)
    - weekly_digest: medium (top 10, trend focus, new signals)
    """
    stats = data_bundle.get("topic_stats", {})
    sources = data_bundle.get("sources", [])
    clusters = data_bundle.get("clusters", [])
    signals = data_bundle.get("signals", [])
    entities = data_bundle.get("entities", [])
    keywords = data_bundle.get("keywords", [])
    evidence_items = data_bundle.get("evidence_items", [])
    language_breakdown = data_bundle.get("language_breakdown", [])

    is_full = report_type == "research_summary"
    source_limit = None if is_full else 10
    entity_limit = 30 if is_full else 10

    lines: list[str] = ["<!-- report-v2 -->"]

    # --- BLUF ---
    lines.append("## Bottom Line Up Front\n")
    lines.append(f"**{stats.get('content_count', 0)}** items | "
                 f"**{stats.get('source_count', 0)}** sources | "
                 f"**{stats.get('cluster_count', 0)}** clusters | "
                 f"**{stats.get('signal_count', 0)}** signals\n")
    lines.append(f"{bluf.bluf}\n")
    lines.append(f"*Confidence: {bluf.confidence_level:.0%}*\n")

    # --- Part I: Data Sheet ---
    lines.append("---\n## Part I: Data Sheet\n")

    # Source Inventory
    display_sources = sources[:source_limit] if source_limit else sources
    if display_sources:
        lines.append("### Source Inventory\n")
        lines.append("| Source | Platform | Credibility | Items |")
        lines.append("|--------|----------|-------------|-------|")
        for src in display_sources:
            lines.append(f"| {src.get('name', '')} | {src.get('platform', '')} | "
                         f"{src.get('credibility_score', 0):.0f} | {src.get('item_count', 0)} |")
        lines.append("")

    # Narrative Clusters
    if clusters:
        lines.append("### Narrative Clusters\n")
        lines.append("| Cluster | Items | Independent Sources | Summary |")
        lines.append("|---------|-------|--------------------:|---------|")
        for cl in clusters:
            summary = (cl.get("executive_summary") or "")[:80]
            lines.append(f"| {cl.get('label', '')} | {cl.get('item_count', 0)} | "
                         f"{cl.get('independent_source_count', 0)} | {summary} |")
        lines.append("")

    # Top Entities
    display_entities = entities[:entity_limit]
    if display_entities:
        lines.append("### Top Entities\n")
        lines.append("| Entity | Type | Mentions |")
        lines.append("|--------|------|----------|")
        for ent in display_entities:
            lines.append(f"| {ent.get('entity_text', '')} | {ent.get('entity_type', '')} | "
                         f"{ent.get('mention_count', 0)} |")
        lines.append("")

    # Trending Keywords
    if keywords:
        lines.append("### Trending Keywords\n")
        kw_display = ", ".join(f"**{kw.get('keyword', '')}** ({kw.get('frequency', 0)})" for kw in keywords[:15])
        lines.append(kw_display + "\n")

    # Language Breakdown
    if language_breakdown and is_full:
        lines.append("### Language Breakdown\n")
        lines.append("| Language | Items |")
        lines.append("|----------|-------|")
        for lang in language_breakdown:
            lines.append(f"| {lang.get('language', 'unknown')} | {lang.get('count', 0)} |")
        lines.append("")

    # --- Part II: Investigative Annex ---
    has_annex = signals or identifiers or template_matches
    if has_annex:
        lines.append("---\n## Part II: Investigative Annex\n")

        # Signals
        if signals:
            display_signals = signals
            if report_type == "intelligence_brief":
                display_signals = [s for s in signals if s.get("status") == "new"]
            if display_signals:
                lines.append("### Signals\n")
                lines.append("| Signal | Cluster | Status | Date |")
                lines.append("|--------|---------|--------|------|")
                for sig in display_signals[:20]:
                    desc = (sig.get("description") or "")[:120]
                    lines.append(f"| {desc} | {sig.get('cluster_label', '')} | "
                                 f"{sig.get('status', '')} | {str(sig.get('created_at', ''))[:10]} |")
                lines.append("")

        # Identifiers
        if identifiers:
            lines.append("### Identified Indicators\n")
            lines.append("| Type | Value | Sources | Items |")
            lines.append("|------|-------|---------|-------|")
            for ident in identifiers:
                lines.append(f"| {ident.get('identifier_type', '')} | "
                             f"{ident.get('identifier_value', '')} | "
                             f"{ident.get('source_count', 0)} | "
                             f"{ident.get('content_item_count', 0)} |")
            lines.append("")

        # Template Matches
        if template_matches:
            lines.append("### Scam Template Matches\n")
            for match in template_matches:
                display = match.get("template_display", match.get("template_name", ""))
                severity = match.get("severity", "")
                confidence = float(match.get("confidence", 0) or 0)
                count = match.get("match_count", 0)
                lines.append(f"**{display}** — Severity: {severity}, "
                             f"Confidence: {confidence:.0%}, Matches: {count}")
            lines.append("")

            # Recommended Actions (derived from template matches)
            actions = build_recommended_actions(template_matches)
            if actions:
                lines.append("## Recommended Actions\n")
                for action in actions:
                    lines.append(f"- {action}")
                lines.append("")

    # --- Part III: Evidence Appendix (research_summary only) ---
    if is_full and evidence_items:
        lines.append("---\n## Part III: Evidence Appendix\n")
        for item in evidence_items[:30]:
            title = item.get("title") or item.get("snippet", "")[:50] or "Untitled"
            lines.append(f"### {title}\n")
            lines.append(f"- **Source:** {item.get('source_name', 'Unknown')} ({item.get('platform', '')})")
            lines.append(f"- **URL:** {item.get('url', 'N/A')}")
            lines.append(f"- **Date:** {str(item.get('captured_at', ''))[:10]}")
            lines.append(f"- **Credibility:** {item.get('credibility_score_at_capture', 0):.0f}")
            if item.get("snippet"):
                lines.append(f"\n> {item['snippet']}\n")
            lines.append("")

    # --- Part IV: Methodology (research_summary only) ---
    if is_full:
        lines.append("---\n## Part IV: Methodology\n")
        lines.append("**Data acquisition:** Automated open-source collection via Anveshak platform.\n")
        lines.append(f"**Analysis period:** {stats.get('content_count', 0)} items from "
                     f"{stats.get('source_count', 0)} sources.\n")
        lines.append("**Limitations:** This report is a point-in-time snapshot. "
                     "Source credibility scores may have changed since generation. "
                     "LLM-generated summaries require analyst verification.\n")
        lines.append("**Confidence calibration:** Confidence level reflects the fraction "
                     "of narrative clusters corroborated by 2+ independent sources.\n")

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
# ARQ job: generate_source_assessment — Phase 2
# ---------------------------------------------------------------------------

async def generate_source_assessment(ctx: dict, assessment_id: str) -> None:
    """Generate an LLM-powered source assessment brief with per-claim citations.

    Pipeline: fetch assessment → load content → render prompt → LLM → validate → store.
    Idempotent via generated_at IS NULL guard.
    """
    settings = ctx.get("settings", _default_settings)
    pool = ctx["db"]

    # 1. Load assessment row
    assessment = await db.fetch_assessment(pool, assessment_id)
    if assessment is None:
        log.warning("reporter.assessment.not_found", assessment_id=assessment_id)
        return

    # Skip if already generated
    if assessment.get("generated_at") is not None:
        log.info("reporter.assessment.already_generated", assessment_id=assessment_id)
        return

    topic_id = assessment["topic_id"]
    source_id = assessment["source_id"]

    # 2. Load topic info
    topic = await db.fetch_topic(pool, topic_id)
    if topic is None:
        await db.set_assessment_failed(pool, assessment_id, "Topic not found")
        return

    # 3. Load source content (most recent, up to 30 items)
    chunks = await db.fetch_source_content_for_brief(
        pool, topic_id, source_id, limit=30
    )
    if not chunks:
        await db.set_assessment_failed(pool, assessment_id, "No content items found for this source")
        return

    # 4. Assemble content context with content_item_ids for citation
    context_parts = []
    for chunk in chunks:
        header = f"[ID: {chunk['id']} | URL: {chunk.get('url', 'N/A')} | Date: {chunk.get('captured_at', 'N/A')}]"
        context_parts.append(f"{header}\n{chunk['clean_text'][:500]}")
    context = "\n\n---\n\n".join(context_parts)

    # 5. Parse stats summary for prompt context
    stats_summary = ""
    stats_raw = assessment.get("stats")
    if stats_raw:
        import json as _json
        stats_data = _json.loads(stats_raw) if isinstance(stats_raw, str) else stats_raw
        stats_summary = (
            f"Total posts: {stats_data.get('total_posts', 'N/A')}\n"
            f"Avg posts/day: {stats_data.get('avg_posts_per_day', 'N/A')}\n"
            f"Engagement: {stats_data.get('engagement', {})}\n"
            f"Sentiment: {stats_data.get('sentiment_distribution', {})}\n"
            f"Languages: {[l.get('language') for l in stats_data.get('language_breakdown', [])]}\n"
            f"Clusters: {len(stats_data.get('cluster_participation', []))}\n"
            f"Identifiers overlapping other sources: {len(stats_data.get('identifier_overlap', []))}"
        )

    # 6. Parse platform metadata
    platform_meta_str = ""
    meta_raw = assessment.get("platform_metadata")
    if meta_raw:
        import json as _json
        meta = _json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        if meta:
            platform_meta_str = "\n".join(f"{k}: {v}" for k, v in meta.items() if v is not None)

    # 7. Get source info
    source_row = await db.fetch_source_info(pool, source_id)

    source_name = source_row["name"] if source_row else source_id
    platform = source_row["platform"] if source_row else "unknown"

    # 8. Render prompt
    prompt = render_assessment_prompt(
        source_name=source_name,
        platform=platform,
        topic_name=topic.get("name", ""),
        keywords=topic.get("keywords", []),
        context=context,
        stats_summary=stats_summary,
        platform_metadata=platform_meta_str,
    )

    # 9. Call LLM
    brief = await call_ollama_for_assessment(
        prompt=prompt,
        settings=settings,
        max_retries=settings.ollama_retry_max,
    )

    if brief is None:
        await db.set_assessment_failed(pool, assessment_id, "LLM failed to generate valid assessment brief")
        return

    # 10. Validate citations — strip any content_item_ids not in our chunks
    valid_ids = {c["id"] for c in chunks}
    for claim in brief.cited_claims:
        claim.content_item_ids = [cid for cid in claim.content_item_ids if cid in valid_ids]

    # 11. Build markdown
    md_parts = [
        f"## Source Assessment: {source_name}",
        f"\n**Characterization:** {brief.source_characterization}",
        f"\n**Posting Behavior:** {brief.posting_behavior}",
        f"\n**Key Themes:** {', '.join(brief.key_themes)}",
        f"\n**Narrative Role:** {brief.narrative_role}",
        f"\n**Intelligence Value:** {brief.intelligence_value}",
    ]
    if brief.risk_indicators:
        md_parts.append("\n**Risk Indicators:**")
        for ri in brief.risk_indicators:
            md_parts.append(f"- {ri}")
    if brief.cited_claims:
        md_parts.append("\n**Cited Claims:**")
        for claim in brief.cited_claims:
            ids = ", ".join(claim.content_item_ids[:3])
            md_parts.append(f"- {claim.claim} [Refs: {ids}]")
    md_parts.append(f"\n**Confidence:** {brief.confidence_level:.2f}")
    brief_md = "\n".join(md_parts)

    # 12. Store — idempotent via generated_at IS NULL guard
    stored = await db.set_assessment_brief(
        pool,
        assessment_id=assessment_id,
        brief_md=brief_md,
        confidence_score=brief.confidence_level,
    )

    if stored:
        log.info(
            "reporter.assessment.generated",
            assessment_id=assessment_id,
            source_id=source_id,
            confidence=brief.confidence_level,
        )
    else:
        log.info("reporter.assessment.already_set", assessment_id=assessment_id)


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
        arq.func(generate_source_assessment, max_tries=2),
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
