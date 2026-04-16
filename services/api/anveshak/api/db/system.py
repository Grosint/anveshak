"""System repository — pipeline health metrics queries."""
from __future__ import annotations

from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_CONTENT_TOTAL = "SELECT COUNT(*) FROM content_items"

SQL_CONTENT_EMBEDDED = "SELECT COUNT(*) FROM content_items WHERE embedding IS NOT NULL"

SQL_CONTENT_LAST_24H = """
    SELECT COUNT(*) FROM content_items
    WHERE created_at >= NOW() - INTERVAL '24 hours'
"""

SQL_CLUSTERS_TOTAL = "SELECT COUNT(*) FROM narrative_clusters"

SQL_SIGNALS_LAST_30D = """
    SELECT COUNT(*) FROM signals
    WHERE created_at >= NOW() - INTERVAL '30 days'
"""

SQL_REPORTS_LAST_30D = """
    SELECT COUNT(*) FROM reports
    WHERE generated_at IS NOT NULL
      AND generation_error IS NULL
      AND generated_at >= NOW() - INTERVAL '30 days'
"""

SQL_SOURCES_ACTIVE = "SELECT COUNT(*) FROM sources WHERE is_active = true"

SQL_SOURCES_DOWN = "SELECT COUNT(*) FROM sources WHERE health_status = 'down'"

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def get_pipeline_metrics(conn: asyncpg.Connection) -> dict[str, Any]:
    content_total    = await conn.fetchval(SQL_CONTENT_TOTAL)
    content_embedded = await conn.fetchval(SQL_CONTENT_EMBEDDED)
    content_last_24h = await conn.fetchval(SQL_CONTENT_LAST_24H)
    clusters_total   = await conn.fetchval(SQL_CLUSTERS_TOTAL)
    signals_last_30d = await conn.fetchval(SQL_SIGNALS_LAST_30D)
    reports_last_30d = await conn.fetchval(SQL_REPORTS_LAST_30D)
    sources_active   = await conn.fetchval(SQL_SOURCES_ACTIVE)
    sources_down     = await conn.fetchval(SQL_SOURCES_DOWN)

    return {
        "content_items_total":    int(content_total),
        "content_items_embedded": int(content_embedded),
        "content_items_last_24h": int(content_last_24h),
        "narrative_clusters_total": int(clusters_total),
        "signals_last_30d":       int(signals_last_30d),
        "reports_last_30d":       int(reports_last_30d),
        "sources_active":         int(sources_active),
        "sources_down":           int(sources_down),
    }
