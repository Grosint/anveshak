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
REDIS_CONTAINER = f"{COMPOSE_PROJECT}-redis-1"
DB_NAME = os.environ.get("POSTGRES_DB", "anveshak")
DB_USER = os.environ.get("POSTGRES_USER", "anveshak")

# Compose file path (relative to repo root)
COMPOSE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "infra", "compose.yml")

# Expected worker containers — if missing, pipeline stage is broken
WORKER_CONTAINERS = {
    "scrape-social-worker":    {"stage": 1, "role": "Social adapter polling (Telegram, X, Reddit, Instagram)"},
    "scrape-web-worker":       {"stage": 1, "role": "Web/RSS/darkweb scraping"},
    "analyse-worker":          {"stage": 2, "role": "NLP, embedding, identifiers, quality scoring"},
    "analyse-scheduler":       {"stage": 3, "role": "Clustering, signals, convergence, orphan sweep"},
    "report-worker":           {"stage": 5, "role": "LLM report generation"},
}

# ARQ queues and their thresholds
# ARQ default queue is "arq:queue" (social), named queues for scraper/analyst
ARQ_QUEUES = {
    "arq:queue":    {"warn": 50, "critical": 200, "stage": 1, "label": "social (default)"},
    "arq:scraper":  {"warn": 30, "critical": 100, "stage": 1, "label": "scraper"},
    "arq:analyst":  {"warn": 50, "critical": 200, "stage": 2, "label": "analyst"},
}

# Source staleness thresholds (seconds)
SOURCE_STALENESS = {
    "telegram": 3600,     # 1h (poll_interval=900s, 4× buffer)
    "twitter":  7200,     # 2h
    "reddit":   7200,     # 2h
    "instagram": 7200,    # 2h
    "bluesky":  7200,     # 2h
    "rss":      21600,    # 6h
    "web":      86400,    # 24h
    "darkweb":  86400,    # 24h
}

# Exit codes
EXIT_HEALTHY = 0
EXIT_WARNING = 1
EXIT_CRITICAL = 2

# Engine C identifier types (from migration 009)
ENGINE_C_IDENTIFIER_TYPES = (
    "PHONE_IN", "UPI", "EMAIL", "CRYPTO_BTC", "CRYPTO_ETH",
    "CRYPTO_TRC20", "TELEGRAM_HANDLE", "INSTAGRAM_HANDLE",
    "URL_DOMAIN", "GSTIN", "UDYAM", "PAN", "IFSC",
    "BANK_ACCOUNT", "SEBI_REG",
)
ENGINE_C_TYPES_SQL = ", ".join(f"'{t}'" for t in ENGINE_C_IDENTIFIER_TYPES)

# Agency detection keywords in topic names
AGENCY_KEYWORDS = {
    "mea": ("MEA", "Beijing", "Chinese Media", "Embassy", "Foreign Media"),
    "cyber": ("Cyber", "Fraud", "Mule", "Investment Fraud"),
    "sebi": ("SEBI", "Pump", "Surveillance", "Market", "Stock"),
    "ncb": ("NCB", "Drug", "Narco", "Cannabis", "Stuff"),
}
AGENCY_DISPLAY = {
    "mea": "MEA — Foreign Media Monitoring",
    "cyber": "Police Cyber Cell — Fraud Detection",
    "sebi": "SEBI — Market Surveillance",
    "ncb": "NCB — Narcotics Intelligence",
}


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
# Redis query helper
# ---------------------------------------------------------------------------

def _redis_cmd(args: list[str]) -> str | None:
    """Run a Redis command via docker exec, return stdout."""
    cmd = ["docker", "exec", REDIS_CONTAINER, "redis-cli"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _redis_queue_depth(queue_name: str) -> int | None:
    """Get ARQ queue length. ARQ uses sorted sets (ZCARD), not lists (LLEN)."""
    # Try ZCARD first (ARQ's actual type), fall back to LLEN
    val = _redis_cmd(["ZCARD", queue_name])
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    # Fallback to LLEN for non-ARQ queues
    val = _redis_cmd(["LLEN", queue_name])
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Stage 1: Container Liveness
# ---------------------------------------------------------------------------

def check_container_health() -> dict:
    """Check which worker containers are running and healthy."""
    stats: dict = {"containers": {}, "warnings": [], "criticals": []}

    try:
        cmd = [
            "docker", "compose", "--env-file", ".env",
            "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE,
            "ps", "--format", "json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            stats["criticals"].append("Cannot query container status — docker compose ps failed")
            return stats

        # Parse JSON lines (one per container)
        running = {}
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                c = json.loads(line)
                # Name format: anveshak-scrape-social-worker-1 → scrape-social-worker
                name = c.get("Name", "").replace(f"{COMPOSE_PROJECT}-", "").rstrip("-1234567890")
                # Strip trailing dash
                if name.endswith("-"):
                    name = name[:-1]
                health = c.get("Health", "")
                state = c.get("State", "")
                running[name] = {"health": health, "state": state}
            except (json.JSONDecodeError, KeyError):
                continue

        for worker_name, info in WORKER_CONTAINERS.items():
            if worker_name in running:
                r = running[worker_name]
                status = r["health"] if r["health"] else r["state"]
                stats["containers"][worker_name] = {
                    "status": status,
                    "stage": info["stage"],
                    "role": info["role"],
                }
                if status in ("unhealthy", "restarting"):
                    stats["warnings"].append(
                        f"Stage {info['stage']}: {worker_name} is {status} — {info['role']}"
                    )
            else:
                stats["containers"][worker_name] = {
                    "status": "MISSING",
                    "stage": info["stage"],
                    "role": info["role"],
                }
                stats["criticals"].append(
                    f"Stage {info['stage']}: {worker_name} NOT RUNNING — {info['role']}"
                )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        stats["criticals"].append("Cannot check containers — docker not available")

    return stats


# ---------------------------------------------------------------------------
# Stage 1-2: ARQ Queue Depth
# ---------------------------------------------------------------------------

def check_queue_depth() -> dict:
    """Check ARQ queue depths in Redis."""
    stats: dict = {"queues": {}, "warnings": [], "criticals": []}

    for queue_name, thresholds in ARQ_QUEUES.items():
        depth = _redis_queue_depth(queue_name)
        if depth is None:
            stats["queues"][queue_name] = {"depth": "?", "label": thresholds["label"]}
            stats["warnings"].append(f"Cannot read queue {queue_name} — Redis unreachable?")
            continue

        entry = {
            "depth": depth,
            "label": thresholds["label"],
            "stage": thresholds["stage"],
        }
        stats["queues"][queue_name] = entry

        if depth >= thresholds["critical"]:
            stats["criticals"].append(
                f"Queue {queue_name} ({thresholds['label']}): {depth} pending — "
                f"stage {thresholds['stage']} worker likely down"
            )
        elif depth >= thresholds["warn"]:
            stats["warnings"].append(
                f"Queue {queue_name} ({thresholds['label']}): {depth} pending — "
                f"worker may be overloaded"
            )

    return stats


# ---------------------------------------------------------------------------
# Stage 2: Pipeline Flow Rate
# ---------------------------------------------------------------------------

def check_flow_rate(hours: int = 2) -> dict:
    """Compare items inserted vs items with embeddings in recent window."""
    stats: dict = {"warnings": [], "criticals": []}

    inserted = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE created_at >= NOW() - INTERVAL '{hours} hours'
    """)
    embedded = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE created_at >= NOW() - INTERVAL '{hours} hours'
        AND embedding IS NOT NULL
    """)
    with_identifiers = _query_val(f"""
        SELECT COUNT(DISTINCT ci.id) FROM content_items ci
        JOIN extracted_entities ee ON ee.content_item_id = ci.id
        WHERE ci.created_at >= NOW() - INTERVAL '{hours} hours'
    """)

    stats["hours"] = hours
    stats["inserted"] = int(inserted or 0)
    stats["embedded"] = int(embedded or 0)
    stats["with_identifiers"] = int(with_identifiers or 0)

    if stats["inserted"] > 0:
        stats["embed_pct"] = round(stats["embedded"] / stats["inserted"] * 100, 1)
        stats["identifier_pct"] = round(stats["with_identifiers"] / stats["inserted"] * 100, 1)
    else:
        stats["embed_pct"] = 0.0
        stats["identifier_pct"] = 0.0

    # Detect analyse-worker failure: content inserted but not embedded
    if stats["inserted"] > 10 and stats["embed_pct"] < 50:
        stats["criticals"].append(
            f"Pipeline gap: {stats['inserted']} items inserted but only "
            f"{stats['embedded']} embedded ({stats['embed_pct']}%) in last {hours}h — "
            f"analyse-worker may be down or queue misrouted"
        )
    elif stats["inserted"] > 10 and stats["embed_pct"] < 80:
        stats["warnings"].append(
            f"Analyst falling behind: {stats['embed_pct']}% embed rate in last {hours}h"
        )

    return stats


# ---------------------------------------------------------------------------
# Stage 1: Per-Source Staleness
# ---------------------------------------------------------------------------

def check_source_staleness() -> dict:
    """Check when each active source last produced content."""
    stats: dict = {"sources": [], "warnings": [], "criticals": []}

    rows = _query("""
        SELECT s.id, s.name, s.url_or_handle, s.platform, s.health_status,
               s.is_active,
               MAX(ci.captured_at) AS last_content_at,
               COUNT(ci.id) AS total_items,
               EXTRACT(EPOCH FROM (NOW() - MAX(ci.captured_at))) AS seconds_since_last
        FROM sources s
        JOIN topic_sources ts ON ts.source_id = s.id
        LEFT JOIN content_items ci ON ci.source_id = s.id
        WHERE s.is_active = true
        GROUP BY s.id, s.name, s.url_or_handle, s.platform, s.health_status, s.is_active
        ORDER BY s.platform, seconds_since_last DESC NULLS FIRST
    """)

    for row in rows:
        platform = row["platform"]
        total_items = int(row.get("total_items", 0))
        seconds_since = float(row["seconds_since_last"]) if row.get("seconds_since_last") else None
        threshold = SOURCE_STALENESS.get(platform, 86400)

        entry = {
            "name": row["name"],
            "handle": row["url_or_handle"],
            "platform": platform,
            "health": row["health_status"],
            "total_items": total_items,
            "last_content_at": row.get("last_content_at"),
            "seconds_since_last": seconds_since,
        }

        if total_items == 0:
            entry["status"] = "NEVER_SCRAPED"
            stats["criticals"].append(
                f"{row['url_or_handle']} ({platform}): NEVER produced content — "
                f"check adapter auth/access"
            )
        elif seconds_since and seconds_since > threshold * 3:
            entry["status"] = "CRITICAL_STALE"
            hours_ago = round(seconds_since / 3600, 1)
            stats["criticals"].append(
                f"{row['url_or_handle']} ({platform}): last content {hours_ago}h ago"
            )
        elif seconds_since and seconds_since > threshold:
            entry["status"] = "STALE"
            hours_ago = round(seconds_since / 3600, 1)
            stats["warnings"].append(
                f"{row['url_or_handle']} ({platform}): last content {hours_ago}h ago"
            )
        else:
            entry["status"] = "OK"

        stats["sources"].append(entry)

    return stats


# ---------------------------------------------------------------------------
# Stage 3: Cluster Freshness
# ---------------------------------------------------------------------------

def check_cluster_freshness() -> dict:
    """Check if clustering is running by looking at most recent cluster update."""
    stats: dict = {"warnings": []}

    last_cluster = _query_val("""
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) FROM narrative_clusters
    """)
    stats["seconds_since_last_cluster"] = float(last_cluster) if last_cluster else None

    if stats["seconds_since_last_cluster"] is None:
        stats["status"] = "NO_CLUSTERS"
    elif stats["seconds_since_last_cluster"] > 7200:  # 2h
        hours = round(stats["seconds_since_last_cluster"] / 3600, 1)
        stats["status"] = "STALE"
        stats["warnings"].append(
            f"No cluster updates in {hours}h — analyse-scheduler may be stuck"
        )
    else:
        stats["status"] = "OK"

    # Identifier cluster freshness
    last_id_cluster = _query_val("""
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) FROM identifier_clusters
    """)
    stats["seconds_since_last_id_cluster"] = float(last_id_cluster) if last_id_cluster else None

    return stats


# ---------------------------------------------------------------------------
# Formatters — Pipeline Stage Health
# ---------------------------------------------------------------------------

def format_container_health(stats: dict) -> str:
    lines = ["  CONTAINERS:"]
    for name, info in stats["containers"].items():
        status = info["status"]
        if status == "MISSING":
            marker = "MISSING"
        elif status == "healthy":
            marker = "UP"
        else:
            marker = status.upper()
        lines.append(f"    {name:<22s} {marker:<12s} (stage {info['stage']}: {info['role'][:50]})")
    return "\n".join(lines)


def format_queue_depth(stats: dict) -> str:
    lines = ["  ARQ QUEUES:"]
    for queue_name, info in stats["queues"].items():
        depth = info["depth"]
        label = info["label"]
        if isinstance(depth, int):
            if depth == 0:
                marker = "OK"
            elif depth < 50:
                marker = f"{depth} pending"
            else:
                marker = f"{depth} pending  WARNING"
        else:
            marker = "unreachable"
        lines.append(f"    {queue_name:<20s} {marker:<25s} ({label})")
    return "\n".join(lines)


def format_flow_rate(stats: dict) -> str:
    lines = [f"  PIPELINE FLOW (last {stats['hours']}h):"]
    lines.append(f"    Items inserted:           {stats['inserted']}")
    lines.append(f"    Items embedded:           {stats['embedded']} ({stats['embed_pct']}%)")
    lines.append(f"    Items with identifiers:   {stats['with_identifiers']} ({stats['identifier_pct']}%)")
    if stats["inserted"] > 0 and stats["embed_pct"] >= 80:
        lines.append(f"    Analyst throughput:        OK")
    elif stats["inserted"] == 0:
        lines.append(f"    Analyst throughput:        no recent content to evaluate")
    else:
        lines.append(f"    Analyst throughput:        DEGRADED — check analyse-worker + arq:analyst queue")
    return "\n".join(lines)


def format_source_staleness(stats: dict) -> str:
    lines = ["  SOURCE STALENESS:"]
    if not stats["sources"]:
        lines.append("    No active sources with topic links")
        return "\n".join(lines)

    for src in stats["sources"]:
        handle = src["handle"]
        if len(handle) > 30:
            handle = handle[:27] + "..."
        platform = src["platform"]

        if src["status"] == "NEVER_SCRAPED":
            age_str = "NEVER scraped"
        elif src["seconds_since_last"] is not None:
            secs = src["seconds_since_last"]
            if secs < 3600:
                age_str = f"{int(secs / 60)} min ago"
            elif secs < 86400:
                age_str = f"{round(secs / 3600, 1)}h ago"
            else:
                age_str = f"{round(secs / 86400, 1)}d ago"
        else:
            age_str = "unknown"

        status_marker = {
            "OK": "OK",
            "STALE": "WARNING",
            "CRITICAL_STALE": "CRITICAL",
            "NEVER_SCRAPED": "CRITICAL",
        }.get(src["status"], "?")

        lines.append(
            f"    {handle:<32s} ({platform:<10s}) "
            f"last: {age_str:<16s} {src['total_items']:>4d} items  {status_marker}"
        )
    return "\n".join(lines)


def format_cluster_freshness(stats: dict) -> str:
    lines = ["  CLUSTER FRESHNESS:"]
    secs = stats["seconds_since_last_cluster"]
    if secs is None:
        lines.append("    Narrative clusters:        no clusters exist yet")
    elif secs < 3600:
        lines.append(f"    Narrative clusters:        updated {int(secs / 60)} min ago  OK")
    else:
        lines.append(f"    Narrative clusters:        updated {round(secs / 3600, 1)}h ago  {'WARNING' if secs > 7200 else 'OK'}")

    id_secs = stats["seconds_since_last_id_cluster"]
    if id_secs is None:
        lines.append("    Identifier clusters:       no clusters exist yet")
    elif id_secs < 3600:
        lines.append(f"    Identifier clusters:       updated {int(id_secs / 60)} min ago  OK")
    else:
        lines.append(f"    Identifier clusters:       updated {round(id_secs / 3600, 1)}h ago  {'WARNING' if id_secs > 7200 else 'OK'}")

    return "\n".join(lines)


def format_stage_report(container_stats: dict, queue_stats: dict, flow_stats: dict,
                        staleness_stats: dict, cluster_stats: dict) -> str:
    """Combine all stage checks into one block."""
    sep = "=" * 60
    lines = [
        f"{sep}",
        "  PIPELINE FLOW — STAGE HEALTH",
        f"{sep}",
        "",
        format_container_health(container_stats),
        "",
        format_queue_depth(queue_stats),
        "",
        format_flow_rate(flow_stats),
        "",
        format_source_staleness(staleness_stats),
        "",
        format_cluster_freshness(cluster_stats),
        "",
    ]

    # Collect all warnings/criticals
    all_w = (container_stats.get("warnings", []) + queue_stats.get("warnings", []) +
             flow_stats.get("warnings", []) + staleness_stats.get("warnings", []) +
             cluster_stats.get("warnings", []))
    all_c = (container_stats.get("criticals", []) + queue_stats.get("criticals", []) +
             flow_stats.get("criticals", []) + staleness_stats.get("criticals", []) +
             cluster_stats.get("criticals", []))

    if all_c:
        lines.append("  STAGE CRITICALS:")
        for c in all_c:
            lines.append(f"    CRITICAL: {c}")
    if all_w:
        lines.append("  STAGE WARNINGS:")
        for w in all_w:
            lines.append(f"    WARNING: {w}")

    if not all_c and not all_w:
        lines.append("  All pipeline stages: HEALTHY")

    lines.append("")
    return "\n".join(lines), all_w, all_c


# ---------------------------------------------------------------------------
# Diagnostics (existing)
# ---------------------------------------------------------------------------

def get_topics(name_filter: str | None = None) -> list[dict]:
    sql = "SELECT id, name, signal_threshold, credibility_min, topic_relevance_threshold FROM topics WHERE status = 'active' ORDER BY name"
    topics = _query(sql)
    if name_filter:
        topics = [t for t in topics if name_filter.lower() in t["name"].lower()]
    return topics


def report_topic(topic_id: str, topic_name: str, signal_threshold: int, hours: int | None, relevance_threshold: float = 0.35) -> dict:
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
    stats["relevance_threshold"] = relevance_threshold
    low_rel = _query_val(f"""
        SELECT COUNT(*) FROM content_items
        WHERE topic_id = '{topic_id}' {time_clause}
        AND topic_relevance_score IS NOT NULL
        AND topic_relevance_score < {relevance_threshold}
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
        stats["criticals"].append("ZERO content scraped — check scrape-web-scheduler logs")
    if stats["cluster_count"] == 0 and stats["content_total"] > 10:
        stats["warnings"].append("Content exists but no clusters — check analyse-scheduler")

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


# ---------------------------------------------------------------------------
# Engine C Diagnostics
# ---------------------------------------------------------------------------

def _engine_c_available() -> bool:
    """Check if Engine C migration (009) has been applied."""
    val = _query_val("SELECT to_regclass('scam_templates')")
    return val is not None and val != ""


def report_topic_engine_c(topic_id: str, content_total: int, hours: int | None) -> dict:
    """Engine C diagnostics for one topic."""
    time_clause = f"AND ci.captured_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""
    time_clause_signals = f"AND created_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""
    stats: dict = {"warnings": []}

    # 1. Identifiers extracted by type
    id_by_type = _query(f"""
        SELECT ee.entity_type, COUNT(*) as cnt
        FROM extracted_entities ee
        JOIN content_items ci ON ee.content_item_id = ci.id
        WHERE ci.topic_id = '{topic_id}'
        AND ee.entity_type IN ({ENGINE_C_TYPES_SQL})
        {time_clause}
        GROUP BY ee.entity_type ORDER BY cnt DESC
    """)
    stats["identifiers_by_type"] = id_by_type
    stats["identifiers_total"] = sum(int(r["cnt"]) for r in id_by_type)

    # 2. Content items with zero identifiers
    no_ids = _query_val(f"""
        SELECT COUNT(*) FROM content_items ci
        WHERE ci.topic_id = '{topic_id}'
        {time_clause.replace('ci.captured_at', 'captured_at') if not time_clause else time_clause}
        AND NOT EXISTS (
            SELECT 1 FROM extracted_entities ee
            WHERE ee.content_item_id = ci.id
            AND ee.entity_type IN ({ENGINE_C_TYPES_SQL})
        )
    """)
    stats["content_no_identifiers"] = int(no_ids or 0)

    # 3. Template matches
    tpl_matches = _query(f"""
        SELECT labels->>'scam_template' as tpl, COUNT(*) as cnt
        FROM content_items
        WHERE topic_id = '{topic_id}'
        AND labels->>'scam_template' IS NOT NULL
        {time_clause.replace('ci.captured_at', 'captured_at') if not time_clause else time_clause.replace('ci.', '')}
        GROUP BY labels->>'scam_template' ORDER BY cnt DESC
    """)
    stats["template_matches"] = tpl_matches
    stats["template_match_total"] = sum(int(r["cnt"]) for r in tpl_matches)

    # 4. Template coverage
    if content_total > 0:
        stats["template_coverage_pct"] = round(stats["template_match_total"] / content_total * 100, 1)
    else:
        stats["template_coverage_pct"] = 0.0

    # 5. Identifier clusters (top 5)
    clusters = _query(f"""
        SELECT identifier_type, identifier_value, source_count, content_item_count
        FROM identifier_clusters
        WHERE topic_id = '{topic_id}'
        ORDER BY source_count DESC
        LIMIT 5
    """)
    stats["id_clusters_top"] = clusters

    cluster_count = _query_val(f"""
        SELECT COUNT(*) FROM identifier_clusters WHERE topic_id = '{topic_id}'
    """)
    stats["id_cluster_count"] = int(cluster_count or 0)

    # 6. Engine C signals
    ec_signals = _query(f"""
        SELECT signal_type, COUNT(*) as cnt FROM signals
        WHERE topic_id = '{topic_id}'
        AND signal_type IN ('identifier_convergence', 'scam_template_match')
        {time_clause_signals}
        GROUP BY signal_type
    """)
    stats["ec_signals"] = ec_signals
    ec_signal_map = {r["signal_type"]: int(r["cnt"]) for r in ec_signals}
    stats["id_convergence_count"] = ec_signal_map.get("identifier_convergence", 0)
    stats["tpl_match_signal_count"] = ec_signal_map.get("scam_template_match", 0)

    # 7. Warnings
    if content_total > 0 and stats["identifiers_total"] == 0:
        stats["warnings"].append("Content exists but 0 identifiers extracted — Engine C extraction may not be running")
    if stats["id_cluster_count"] > 0 and stats["id_convergence_count"] == 0:
        stats["warnings"].append("Identifier clusters exist but 0 identifier_convergence signals — check signal engine")
    if stats["template_match_total"] > 0 and stats["tpl_match_signal_count"] == 0:
        stats["warnings"].append("Template matches exist but 0 scam_template_match signals — check signal engine")

    return stats


def report_global_engine_c(hours: int | None) -> dict:
    """Global Engine C diagnostics."""
    stats: dict = {"warnings": []}
    time_clause = f"AND ee.created_at >= NOW() - INTERVAL '{hours} hours'" if hours else ""

    # Total identifiers by type
    id_global = _query(f"""
        SELECT entity_type, COUNT(*) as cnt FROM extracted_entities
        WHERE entity_type IN ({ENGINE_C_TYPES_SQL})
        {time_clause.replace('ee.', '')}
        GROUP BY entity_type ORDER BY cnt DESC
    """)
    stats["identifiers_global"] = id_global
    stats["identifiers_global_total"] = sum(int(r["cnt"]) for r in id_global)

    # Template matches global
    tpl_global = _query("""
        SELECT labels->>'scam_template' as tpl, COUNT(*) as cnt
        FROM content_items
        WHERE labels->>'scam_template' IS NOT NULL
        GROUP BY labels->>'scam_template' ORDER BY cnt DESC
    """)
    stats["templates_global"] = tpl_global
    stats["most_active_template"] = tpl_global[0]["tpl"] if tpl_global else "none"

    # Cluster global stats
    cluster_global = _query("""
        SELECT COUNT(*) as total, COALESCE(ROUND(AVG(source_count)::numeric, 1), 0) as avg_sc
        FROM identifier_clusters
    """)
    if cluster_global:
        stats["clusters_total"] = int(cluster_global[0].get("total", 0))
        stats["clusters_avg_sc"] = cluster_global[0].get("avg_sc", "0")
    else:
        stats["clusters_total"] = 0
        stats["clusters_avg_sc"] = "0"

    # Tipline ingestion
    tipline = _query_val("""
        SELECT COUNT(*) FROM content_items ci
        JOIN sources s ON ci.source_id = s.id
        WHERE s.platform = 'tipline'
    """)
    stats["tipline_count"] = int(tipline or 0)

    # Instagram adapter
    ig = _query("""
        SELECT s.platform, COUNT(*) as cnt FROM content_items ci
        JOIN sources s ON ci.source_id = s.id
        WHERE s.platform IN ('instagram', 'instagram_bio')
        GROUP BY s.platform
    """)
    stats["instagram"] = ig
    stats["instagram_total"] = sum(int(r["cnt"]) for r in ig)

    # Template health: built-in vs custom
    tpl_health = _query("""
        SELECT
            COUNT(*) FILTER (WHERE is_builtin = true) as builtin,
            COUNT(*) FILTER (WHERE is_builtin = false OR is_builtin IS NULL) as custom
        FROM scam_templates WHERE is_active = true
    """)
    if tpl_health:
        stats["templates_builtin"] = int(tpl_health[0].get("builtin", 0))
        stats["templates_custom"] = int(tpl_health[0].get("custom", 0))
    else:
        stats["templates_builtin"] = 0
        stats["templates_custom"] = 0

    if stats["templates_builtin"] != 11:
        stats["warnings"].append(f"Expected 11 built-in templates, found {stats['templates_builtin']} — check migration 009 seed data")

    return stats


def _detect_agency(topic_name: str) -> str | None:
    """Detect agency type from topic name. Returns agency code or None."""
    name_lower = topic_name.lower()
    for agency, keywords in AGENCY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return agency
    return None


def report_agency_summary(topic_id: str, topic_name: str) -> dict | None:
    """Agency-specific diagnostics. Returns None if not an agency demo topic."""
    agency = _detect_agency(topic_name)
    if not agency:
        return None

    stats: dict = {"agency": agency, "display": AGENCY_DISPLAY.get(agency, agency)}

    if agency == "mea":
        # Multilingual content
        langs = _query(f"""
            SELECT language, COUNT(*) as cnt FROM content_items
            WHERE topic_id = '{topic_id}' GROUP BY language ORDER BY cnt DESC
        """)
        stats["languages"] = langs
        # Translation count
        translated = _query_val(f"""
            SELECT COUNT(*) FROM content_items
            WHERE topic_id = '{topic_id}' AND translated_text IS NOT NULL AND language != 'en'
        """)
        stats["translated_count"] = int(translated or 0)
        non_en = _query_val(f"""
            SELECT COUNT(*) FROM content_items
            WHERE topic_id = '{topic_id}' AND language != 'en'
        """)
        stats["non_english_count"] = int(non_en or 0)
        # Narrative clusters
        nc = _query_val(f"""
            SELECT COUNT(*) FROM narrative_clusters
            WHERE topic_id = '{topic_id}' AND archived_at IS NULL
        """)
        stats["narrative_cluster_count"] = int(nc or 0)

    elif agency == "cyber":
        # Top identifiers by source count
        top_ids = _query(f"""
            SELECT identifier_type, identifier_value, source_count
            FROM identifier_clusters
            WHERE topic_id = '{topic_id}'
            AND identifier_type IN ('PHONE_IN', 'UPI', 'TELEGRAM_HANDLE')
            ORDER BY source_count DESC LIMIT 10
        """)
        stats["top_identifiers"] = top_ids
        # Template breakdown (fraud-focused)
        tpl = _query(f"""
            SELECT labels->>'scam_template' as tpl, COUNT(*) as cnt
            FROM content_items
            WHERE topic_id = '{topic_id}'
            AND labels->>'scam_template' IN ('mule_recruitment', 'investment_fraud', 'maas', 'digital_arrest', 'job_fraud')
            GROUP BY labels->>'scam_template' ORDER BY cnt DESC
        """)
        stats["fraud_templates"] = tpl

    elif agency == "sebi":
        # Finfluencer handles
        handles = _query(f"""
            SELECT identifier_type, identifier_value, source_count
            FROM identifier_clusters
            WHERE topic_id = '{topic_id}'
            AND identifier_type IN ('TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE')
            ORDER BY source_count DESC LIMIT 5
        """)
        stats["finfluencer_handles"] = handles
        # pump_and_dump count
        pnd = _query_val(f"""
            SELECT COUNT(*) FROM content_items
            WHERE topic_id = '{topic_id}'
            AND labels->>'scam_template' = 'pump_and_dump'
        """)
        stats["pump_and_dump_count"] = int(pnd or 0)
        # fake_research_report count
        frr = _query_val(f"""
            SELECT COUNT(*) FROM content_items
            WHERE topic_id = '{topic_id}'
            AND labels->>'scam_template' = 'fake_research_report'
        """)
        stats["fake_report_count"] = int(frr or 0)

    elif agency == "ncb":
        # Drug template matches
        drug = _query_val(f"""
            SELECT COUNT(*) FROM content_items
            WHERE topic_id = '{topic_id}'
            AND labels->>'scam_template' IN ('drug_sale', 'drug_delivery_recruitment')
        """)
        stats["drug_template_count"] = int(drug or 0)
        # Crypto wallets
        wallets = _query(f"""
            SELECT identifier_type, identifier_value, source_count
            FROM identifier_clusters
            WHERE topic_id = '{topic_id}'
            AND identifier_type IN ('CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20')
            ORDER BY source_count DESC LIMIT 5
        """)
        stats["crypto_wallets"] = wallets
        # Dealer phones
        phones = _query(f"""
            SELECT identifier_value, source_count
            FROM identifier_clusters
            WHERE topic_id = '{topic_id}'
            AND identifier_type = 'PHONE_IN'
            ORDER BY source_count DESC LIMIT 5
        """)
        stats["dealer_phones"] = phones
        # Dark web content
        dw = _query_val(f"""
            SELECT COUNT(*) FROM content_items ci
            JOIN sources s ON ci.source_id = s.id
            WHERE ci.topic_id = '{topic_id}'
            AND s.platform = 'darkweb'
        """)
        stats["darkweb_count"] = int(dw or 0)

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
        f"  Relevance-filtered:         {stats['relevance_filtered']} items (score < {stats['relevance_threshold']})",
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


def format_topic_engine_c(ec: dict) -> str:
    """Format Engine C per-topic diagnostics."""
    lines = ["  --- Engine C: Identifier Intelligence ---"]

    # Identifiers by type
    if ec["identifiers_by_type"]:
        parts = ", ".join(f"{r['entity_type']}={r['cnt']}" for r in ec["identifiers_by_type"])
        lines.append(f"  Identifiers extracted:      {ec['identifiers_total']} ({parts})")
    else:
        lines.append(f"  Identifiers extracted:      0")

    lines.append(f"  Content w/o identifiers:    {ec['content_no_identifiers']} items")

    # Template matches
    if ec["template_matches"]:
        parts = ", ".join(f"{r['tpl']}={r['cnt']}" for r in ec["template_matches"])
        lines.append(f"  Template matches:           {ec['template_match_total']} ({parts})")
    else:
        lines.append(f"  Template matches:           0")
    lines.append(f"  Template coverage:          {ec['template_coverage_pct']}%")

    # Identifier clusters
    lines.append(f"  Identifier clusters:        {ec['id_cluster_count']}")
    for c in ec["id_clusters_top"]:
        val = c["identifier_value"]
        if len(val) > 30:
            val = val[:27] + "..."
        lines.append(f"    - {c['identifier_type']} / {val}: {c['source_count']} sources, {c['content_item_count']} items")

    # Engine C signals
    if ec["ec_signals"]:
        parts = ", ".join(f"{r['signal_type']}={r['cnt']}" for r in ec["ec_signals"])
        lines.append(f"  Engine C signals:           {parts}")
    else:
        lines.append(f"  Engine C signals:           0")

    for w in ec["warnings"]:
        lines.append(f"  WARNING: {w}")

    return "\n".join(lines)


def format_global_engine_c(ec: dict) -> str:
    """Format Engine C global diagnostics."""
    lines = ["  --- Engine C: Global ---"]

    # Identifiers
    if ec["identifiers_global"]:
        parts = ", ".join(f"{r['entity_type']}={r['cnt']}" for r in ec["identifiers_global"][:6])
        extra = f", +{len(ec['identifiers_global']) - 6} more" if len(ec["identifiers_global"]) > 6 else ""
        lines.append(f"  Identifiers (all topics):   {ec['identifiers_global_total']} ({parts}{extra})")
    else:
        lines.append(f"  Identifiers (all topics):   0")

    # Templates
    if ec["templates_global"]:
        parts = ", ".join(f"{r['tpl']}={r['cnt']}" for r in ec["templates_global"][:5])
        lines.append(f"  Template matches (global):  {parts}")
        lines.append(f"  Most active template:       {ec['most_active_template']}")
    else:
        lines.append(f"  Template matches (global):  0")

    # Clusters
    lines.append(f"  Identifier clusters:        {ec['clusters_total']} total, avg {ec['clusters_avg_sc']} sources/cluster")

    # Adapters
    lines.append(f"  Tipline items ingested:     {ec['tipline_count']}")
    lines.append(f"  Instagram items:            {ec['instagram_total']}")

    # Template health
    lines.append(f"  Scam templates:             {ec['templates_builtin']} built-in, {ec['templates_custom']} custom")

    for w in ec["warnings"]:
        lines.append(f"  WARNING: {w}")

    return "\n".join(lines)


def format_agency_summary(agency_stats: dict) -> str:
    """Format agency-specific summary."""
    agency = agency_stats["agency"]
    lines = [f"  --- Agency: {agency_stats['display']} ---"]

    if agency == "mea":
        if agency_stats.get("languages"):
            parts = ", ".join(f"{r['language']}={r['cnt']}" for r in agency_stats["languages"])
            lines.append(f"  Languages:                  {parts}")
        lines.append(f"  Non-English content:        {agency_stats.get('non_english_count', 0)} items")
        lines.append(f"  Translated:                 {agency_stats.get('translated_count', 0)} items")
        lines.append(f"  Narrative clusters:         {agency_stats.get('narrative_cluster_count', 0)}")

    elif agency == "cyber":
        if agency_stats.get("top_identifiers"):
            lines.append(f"  Top identifiers (by source count):")
            for r in agency_stats["top_identifiers"][:5]:
                lines.append(f"    {r['identifier_type']} / {r['identifier_value']}: {r['source_count']} sources")
        if agency_stats.get("fraud_templates"):
            parts = ", ".join(f"{r['tpl']}={r['cnt']}" for r in agency_stats["fraud_templates"])
            lines.append(f"  Fraud templates:            {parts}")
        else:
            lines.append(f"  Fraud templates:            0 matches")

    elif agency == "sebi":
        if agency_stats.get("finfluencer_handles"):
            lines.append(f"  Finfluencer handles:")
            for r in agency_stats["finfluencer_handles"]:
                lines.append(f"    {r['identifier_value']}: {r['source_count']} sources")
        lines.append(f"  Pump-and-dump matches:      {agency_stats.get('pump_and_dump_count', 0)}")
        lines.append(f"  Fake research reports:      {agency_stats.get('fake_report_count', 0)}")

    elif agency == "ncb":
        lines.append(f"  Drug template matches:      {agency_stats.get('drug_template_count', 0)}")
        if agency_stats.get("crypto_wallets"):
            lines.append(f"  Crypto wallets:")
            for r in agency_stats["crypto_wallets"]:
                val = r["identifier_value"]
                if len(val) > 20:
                    val = val[:17] + "..."
                lines.append(f"    {r['identifier_type']} / {val}: {r['source_count']} sources")
        if agency_stats.get("dealer_phones"):
            lines.append(f"  Dealer phones:")
            for r in agency_stats["dealer_phones"]:
                lines.append(f"    {r['identifier_value']}: {r['source_count']} sources")
        lines.append(f"  Dark web content:           {agency_stats.get('darkweb_count', 0)} items")

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

    # ── Pipeline Stage Health (containers, queues, flow, staleness) ──
    container_stats = check_container_health()
    queue_stats = check_queue_depth()
    flow_stats = check_flow_rate(hours=min(hours, 4) if hours else 4)
    staleness_stats = check_source_staleness()
    cluster_stats = check_cluster_freshness()

    stage_report, stage_warnings, stage_criticals = format_stage_report(
        container_stats, queue_stats, flow_stats, staleness_stats, cluster_stats,
    )
    print(stage_report)
    all_warnings = list(stage_warnings)
    all_criticals = list(stage_criticals)

    # Engine C availability
    engine_c_ok = _engine_c_available()
    if not engine_c_ok:
        print("INFO: Engine C tables not found — run migration 009 for identifier intelligence")
        print()

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

    for topic in topics:
        raw_threshold = topic.get("topic_relevance_threshold")
        rel_threshold = float(raw_threshold) if raw_threshold else 0.35
        stats = report_topic(
            topic["id"], topic["name"],
            int(topic["signal_threshold"]),
            hours,
            relevance_threshold=rel_threshold,
        )
        print(format_topic_report(
            topic["name"], int(topic["signal_threshold"]),
            stats, hours,
        ))

        # Engine C per-topic diagnostics
        if engine_c_ok:
            ec_stats = report_topic_engine_c(topic["id"], stats["content_total"], hours)
            print(format_topic_engine_c(ec_stats))
            all_warnings.extend(ec_stats.get("warnings", []))
            # Agency-specific summary
            agency_stats = report_agency_summary(topic["id"], topic["name"])
            if agency_stats:
                print(format_agency_summary(agency_stats))

        print()
        all_warnings.extend(stats["warnings"])
        all_criticals.extend(stats["criticals"])

    # Global stats
    global_stats = report_global(hours)
    print(format_global_report(global_stats))

    # Engine C global diagnostics
    if engine_c_ok:
        ec_global = report_global_engine_c(hours)
        print(format_global_engine_c(ec_global))
        all_warnings.extend(ec_global.get("warnings", []))

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
