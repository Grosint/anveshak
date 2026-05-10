#!/usr/bin/env python3
"""Pipeline health diagnostics — daily (or on-demand) report.

Queries PostgreSQL via docker exec psql. No external Python deps required.
Run on the VM host after `make setup`.

Usage:
    python scripts/pipeline_health.py                  # last 24h, all topics
    python scripts/pipeline_health.py --hours 48       # last 48h
    python scripts/pipeline_health.py --topic "LAC"    # filter by topic name substring
    python scripts/pipeline_health.py --summary        # full-period stats (since first content)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COMPOSE_PROJECT = "anveshak"
POSTGRES_CONTAINER = f"{COMPOSE_PROJECT}-postgres-1"
DB_NAME = os.environ.get("POSTGRES_DB", "anveshak")
DB_USER = os.environ.get("POSTGRES_USER", "anveshak")

# Exit codes
EXIT_HEALTHY = 0
EXIT_WARNING = 1
EXIT_CRITICAL = 2


# ---------------------------------------------------------------------------
# DB query helper
# ---------------------------------------------------------------------------

def _query(sql: str) -> list[dict]:
    """Run SQL via docker exec psql, return list of dicts."""
    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", DB_USER, "-d", DB_NAME,
        "-t", "-A", "-F", "\t",
        "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"SQL ERROR: {result.stderr.strip()}", file=sys.stderr)
        return []

    rows = []
    lines = result.stdout.strip().split("\n")
    if not lines or lines == [""]:
        return []

    # First query line is data (no header with -t flag)
    # We need column names — run with headers
    cmd_h = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", DB_USER, "-d", DB_NAME,
        "-A", "-F", "\t",
        "-c", sql,
    ]
    result_h = subprocess.run(cmd_h, capture_output=True, text=True, timeout=30)
    if result_h.returncode != 0:
        return []

    h_lines = result_h.stdout.strip().split("\n")
    if len(h_lines) < 2:
        return []

    headers = h_lines[0].split("\t")
    for line in h_lines[1:]:
        if line.startswith("(") and line.endswith(")"):
            break  # row count footer
        vals = line.split("\t")
        if len(vals) == len(headers):
            rows.append(dict(zip(headers, vals)))
    return rows


def _query_val(sql: str) -> str | None:
    """Run SQL that returns a single value."""
    cmd = [
        "docker", "exec", POSTGRES_CONTAINER,
        "psql", "-U", DB_USER, "-d", DB_NAME,
        "-t", "-A",
        "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return None
    val = result.stdout.strip()
    return val if val else None


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def get_topics(name_filter: str | None = None) -> list[dict]:
    sql = "SELECT id, name, signal_threshold, credibility_min FROM topics WHERE status = 'active' ORDER BY name"
    topics = _query(sql)
    if name_filter:
        topics = [t for t in topics if name_filter.lower() in t["name"].lower()]
    return topics


def report_topic(topic_id: str, topic_name: str, signal_threshold: int, hours: int | None) -> dict:
    """Generate diagnostics for one topic. Returns stats dict."""
    time_clause = f"AND captured_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""
    time_clause_created = f"AND created_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""

    stats: dict = {"warnings": [], "criticals": []}

    # 1. Content scraped
    total = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
    """)
    stats["content_total"] = int(total or 0)

    # Also count via topic_content_items (backfilled)
    backfilled = _query_val(f"""
        SELECT COUNT(*) FROM topic_content_items
        WHERE topic_id = '{topic_id}'
        AND content_item_id NOT IN (
            SELECT id FROM content_items WHERE topic_id = '{topic_id}'
        )
    """)
    stats["content_backfilled"] = int(backfilled or 0)

    # 2. Quality-filtered
    low_quality = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        AND content_quality = 'low_quality'
    """)
    stats["quality_filtered"] = int(low_quality or 0)

    # 3. Embeddings NULL (orphans)
    null_embed = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        AND embedding IS NULL
    """)
    stats["embeddings_null"] = int(null_embed or 0)
    if stats["embeddings_null"] > 0:
        stats["warnings"].append(f"{stats['embeddings_null']} items with NULL embedding")

    # 4. Relevance-filtered
    low_rel = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        AND topic_relevance_score IS NOT NULL
        AND topic_relevance_score < 0.35
    """)
    stats["relevance_filtered"] = int(low_rel or 0)

    # 5. Clusters
    clusters = _query(f"""
        SELECT id, label, item_count, independent_source_count
        FROM narrative_clusters
        WHERE topic_id = '{topic_id}' AND archived_at IS NULL
        ORDER BY item_count DESC
        LIMIT 20
    """)
    stats["clusters"] = clusters
    stats["cluster_count"] = len(clusters)

    # 6. Unassigned items (have embedding but no cluster)
    unassigned = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        AND embedding IS NOT NULL
        AND narrative_cluster_id IS NULL
    """)
    stats["unassigned"] = int(unassigned or 0)

    # 7. Signals
    signals_fired = _query_val(f"""
        SELECT COUNT(*) FROM signals
        WHERE topic_id = '{topic_id}' {time_clause_created}
    """)
    stats["signals_fired"] = int(signals_fired or 0)

    signals_by_status = _query(f"""
        SELECT status, COUNT(*) as cnt FROM signals
        WHERE topic_id = '{topic_id}' {time_clause_created}
        GROUP BY status ORDER BY status
    """)
    stats["signals_by_status"] = signals_by_status

    # 8. Reports
    reports = _query(f"""
        SELECT id, report_type, generated_at, generation_error, content_item_count
        FROM reports
        WHERE topic_id = '{topic_id}' {time_clause_created}
        ORDER BY created_at DESC
        LIMIT 5
    """)
    stats["reports"] = reports
    failed_reports = [r for r in reports if r.get("generation_error") and r.get("generation_error") != ""]
    if failed_reports:
        stats["warnings"].append(f"{len(failed_reports)} report(s) with generation errors")

    # 9. Content by platform
    by_platform = _query(f"""
        SELECT s.platform, COUNT(*) as cnt
        FROM content_items ci
        JOIN sources s ON ci.source_id = s.id
        WHERE ci.topic_id = '{topic_id}' {time_clause.replace('captured_at', 'ci.captured_at')}
        GROUP BY s.platform ORDER BY cnt DESC
    """)
    stats["by_platform"] = by_platform

    # 10. Content by language
    by_lang = _query(f"""
        SELECT language, COUNT(*) as cnt FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        GROUP BY language ORDER BY cnt DESC
    """)
    stats["by_language"] = by_lang

    # Critical checks
    if stats["content_total"] == 0 and hours and hours <= 48:
        stats["criticals"].append("ZERO content scraped — check scraper logs")
    if stats["cluster_count"] == 0 and stats["content_total"] > 10:
        stats["warnings"].append("Content exists but no clusters — check analyst-scheduler")

    return stats


def report_global(hours: int | None) -> dict:
    """Global diagnostics not tied to a specific topic."""
    stats: dict = {"warnings": [], "criticals": []}
    time_clause = f"WHERE failed_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""

    # DLQ
    dlq = _query(f"""
        SELECT queue_name, COUNT(*) as cnt FROM failed_jobs
        {time_clause}
        GROUP BY queue_name ORDER BY cnt DESC
    """)
    stats["dlq"] = dlq
    total_dlq = sum(int(r.get("cnt", 0)) for r in dlq)
    if total_dlq > 10:
        stats["warnings"].append(f"DLQ has {total_dlq} failed jobs")

    # Source health
    source_health = _query("""
        SELECT health_status, COUNT(*) as cnt FROM sources
        WHERE is_active = true
        GROUP BY health_status ORDER BY health_status
    """)
    stats["source_health"] = source_health
    down_count = sum(int(r["cnt"]) for r in source_health if r["health_status"] in ("down", "dead"))
    if down_count > 0:
        stats["warnings"].append(f"{down_count} source(s) are DOWN")

    # Media assets
    time_clause_media = f"AND created_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""
    media_total = _query_val(f"SELECT COUNT(*) FROM media_assets WHERE 1=1 {time_clause_media}")
    stats["media_total"] = int(media_total or 0)

    # Vision results
    vision_processed = _query_val(f"SELECT COUNT(*) FROM vision_results WHERE 1=1 {time_clause_media.replace('created_at', 'processed_at')}")
    stats["vision_processed"] = int(vision_processed or 0)

    # Deepfake distribution
    deepfake_stats = _query("""
        SELECT
            COUNT(*) FILTER (WHERE deepfake_score >= 0.5) as suspicious,
            COUNT(*) FILTER (WHERE deepfake_score >= 0.8) as high_risk,
            COUNT(*) FILTER (WHERE deepfake_score IS NOT NULL) as total_scored
        FROM vision_results
    """)
    stats["deepfake"] = deepfake_stats[0] if deepfake_stats else {}

    # Analysis jobs
    time_clause_jobs = f"AND created_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""
    jobs = _query(f"""
        SELECT job_type, status, COUNT(*) as cnt FROM analysis_jobs
        WHERE 1=1 {time_clause_jobs}
        GROUP BY job_type, status ORDER BY job_type, status
    """)
    stats["analysis_jobs"] = jobs

    return stats


def check_gpu() -> str | None:
    """Check GPU utilization via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_topic_report(name: str, signal_threshold: int, stats: dict, hours: int | None) -> str:
    period = f"last {hours}h" if hours else "all time"
    lines = [
        f"TOPIC: {name}",
        f"  Content scraped ({period}):  {stats['content_total']} items"
        + (f" (+{stats['content_backfilled']} backfilled)" if stats['content_backfilled'] > 0 else ""),
        f"  Quality-filtered out:       {stats['quality_filtered']} items",
        f"  Embeddings NULL:            {stats['embeddings_null']} items (orphans)",
        f"  Relevance-filtered:         {stats['relevance_filtered']} items (score < 0.35)",
    ]

    # Platform breakdown
    if stats["by_platform"]:
        plats = ", ".join(f"{r['platform']}={r['cnt']}" for r in stats["by_platform"])
        lines.append(f"  By platform:                {plats}")

    # Language breakdown
    if stats["by_language"]:
        langs = ", ".join(f"{r['language']}={r['cnt']}" for r in stats["by_language"])
        lines.append(f"  By language:                {langs}")

    # Clusters
    lines.append(f"  Active clusters:            {stats['cluster_count']}")
    for c in stats["clusters"][:10]:
        label = c.get("label") or "(unlabelled)"
        if len(label) > 50:
            label = label[:47] + "..."
        isc = int(c.get("independent_source_count", 0))
        items = int(c.get("item_count", 0))
        threshold_met = isc >= signal_threshold
        marker = "SIGNAL" if threshold_met else f"ISC below {signal_threshold}"
        lines.append(f"    - \"{label}\": {items} items, ISC={isc} {'OK' if threshold_met else 'x'} {marker}")

    lines.append(f"  Unassigned items:           {stats['unassigned']} (not in any cluster)")

    # Signals
    lines.append(f"  Signals fired ({period}):  {stats['signals_fired']}")
    if stats["signals_by_status"]:
        status_str = ", ".join(f"{r['status']}={r['cnt']}" for r in stats["signals_by_status"])
        lines.append(f"    Status breakdown:         {status_str}")

    # Reports
    if stats["reports"]:
        for r in stats["reports"][:3]:
            gen = r.get("generated_at", "")
            err = r.get("generation_error", "")
            items = r.get("content_item_count", "?")
            if gen and gen != "":
                lines.append(f"  Report: {r['report_type']} — generated at {gen} ({items} items)")
            elif err:
                lines.append(f"  Report: {r['report_type']} — FAILED: {err[:80]}")
            else:
                lines.append(f"  Report: {r['report_type']} — pending")
    else:
        lines.append(f"  Reports generated:          None")

    # Warnings / criticals
    for w in stats["warnings"]:
        lines.append(f"  WARNING: {w}")
    for c in stats["criticals"]:
        lines.append(f"  CRITICAL: {c}")

    # Bottleneck analysis
    if stats["unassigned"] > 10 and stats["content_total"] > 20:
        pct = round(stats["unassigned"] / stats["content_total"] * 100)
        lines.append(f"\n  BOTTLENECK: {pct}% items unassigned — consider lowering clustering_similarity_threshold")

    return "\n".join(lines)


def format_global_report(stats: dict) -> str:
    lines = ["GLOBAL"]

    # DLQ
    if stats["dlq"]:
        lines.append("  Dead Letter Queue:")
        for r in stats["dlq"]:
            lines.append(f"    {r['queue_name']}: {r['cnt']} failed jobs")
    else:
        lines.append("  Dead Letter Queue:          empty")

    # Source health
    if stats["source_health"]:
        lines.append("  Source Health:")
        for r in stats["source_health"]:
            lines.append(f"    {r['health_status']}: {r['cnt']}")
    else:
        lines.append("  Source Health:               no active sources")

    # Media & vision
    lines.append(f"  Media assets:               {stats['media_total']}")
    lines.append(f"  Vision results:             {stats['vision_processed']}")

    # Deepfake
    df = stats.get("deepfake", {})
    if df:
        lines.append(f"  Deepfake scores:            {df.get('total_scored', 0)} scored"
                      f", {df.get('suspicious', 0)} suspicious (>0.5)"
                      f", {df.get('high_risk', 0)} high-risk (>0.8)")

    # Analysis jobs
    if stats["analysis_jobs"]:
        lines.append("  Analysis Jobs:")
        for r in stats["analysis_jobs"]:
            lines.append(f"    {r['job_type']}/{r['status']}: {r['cnt']}")

    for w in stats["warnings"]:
        lines.append(f"  WARNING: {w}")
    for c in stats.get("criticals", []):
        lines.append(f"  CRITICAL: {c}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Anveshak pipeline health diagnostics")
    parser.add_argument("--hours", type=int, default=24, help="Look-back window in hours (default: 24)")
    parser.add_argument("--topic", type=str, default=None, help="Filter topics by name substring")
    parser.add_argument("--summary", action="store_true", help="Full-period stats (ignore --hours)")
    args = parser.parse_args()

    hours: int | None = None if args.summary else args.hours
    period_label = "ALL TIME" if args.summary else f"LAST {args.hours}h"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"{'=' * 60}")
    print(f"  PIPELINE HEALTH REPORT — {period_label}")
    print(f"  Generated: {now}")
    print(f"{'=' * 60}")
    print()

    # Check DB connectivity
    test = _query_val("SELECT 1")
    if test is None:
        print(f"CRITICAL: Cannot connect to PostgreSQL container ({POSTGRES_CONTAINER})")
        print("Ensure containers are running: make ps")
        return EXIT_CRITICAL

    # GPU
    gpu_info = check_gpu()
    if gpu_info:
        print(f"GPU: {gpu_info}")
        print()

    # Topics
    topics = get_topics(args.topic)
    if not topics:
        print("No active topics found.")
        return EXIT_WARNING

    exit_code = EXIT_HEALTHY
    all_warnings = []
    all_criticals = []

    for topic in topics:
        stats = report_topic(
            topic["id"], topic["name"],
            int(topic["signal_threshold"]),
            hours,
        )
        print(format_topic_report(
            topic["name"], int(topic["signal_threshold"]),
            stats, hours,
        ))
        print()
        all_warnings.extend(stats["warnings"])
        all_criticals.extend(stats["criticals"])

    # Global stats
    global_stats = report_global(hours)
    print(format_global_report(global_stats))
    print()
    all_warnings.extend(global_stats["warnings"])
    all_criticals.extend(global_stats.get("criticals", []))

    # Final verdict
    print(f"{'=' * 60}")
    if all_criticals:
        print(f"  STATUS: CRITICAL ({len(all_criticals)} issue(s))")
        exit_code = EXIT_CRITICAL
    elif all_warnings:
        print(f"  STATUS: WARNING ({len(all_warnings)} issue(s))")
        exit_code = EXIT_WARNING
    else:
        print("  STATUS: HEALTHY")
    print(f"{'=' * 60}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
