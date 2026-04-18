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

SQL_CONTENT_ZH = "SELECT COUNT(*) FROM content_items WHERE language = 'zh'"

SQL_CONTENT_TRANSLATED = """
    SELECT COUNT(*) FROM content_items
    WHERE translated_text IS NOT NULL
"""

SQL_ENTITIES_FROM_ZH = """
    SELECT COUNT(*) FROM extracted_entities ee
    JOIN content_items ci ON ci.id = ee.content_item_id
    WHERE ci.language = 'zh'
      AND ee.language = 'en'
"""

# ---------------------------------------------------------------------------
# Vector pipeline health — Phase 10 validation
# ---------------------------------------------------------------------------

SQL_NEAR_DUPLICATES_COUNT = "SELECT COUNT(*) FROM near_duplicates"

SQL_HNSW_INDEX_CHECK = """
    SELECT indexdef FROM pg_indexes
    WHERE tablename = 'content_items'
      AND indexname = 'idx_content_items_embedding'
"""

SQL_NEAR_DUP_TABLE_EXISTS = """
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'near_duplicates'
    )
"""

SQL_ARCHIVED_CLUSTERS = """
    SELECT COUNT(*) FROM narrative_clusters
    WHERE archived_at IS NOT NULL
"""

SQL_LABELED_CLUSTERS = """
    SELECT COUNT(*) FROM narrative_clusters
    WHERE label_generated_at IS NOT NULL
      AND label_item_hash IS NOT NULL
"""

SQL_COLUMN_EXISTS = """
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = $1 AND column_name = $2
    )
"""

SQL_CONVERGENCE_SIGNALS = """
    SELECT COUNT(*) FROM signals
    WHERE signal_type = 'cross_topic_convergence'
"""

SQL_CONVERGENCE_INDEX = """
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_signals_cross_topic'
    )
"""

SQL_BACKFILLED_ITEMS = """
    SELECT COUNT(*) FROM topic_content_items
    WHERE similarity_score > 0
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def get_pipeline_metrics(conn: asyncpg.Connection) -> dict[str, Any]:
    content_total      = await conn.fetchval(SQL_CONTENT_TOTAL)
    content_embedded   = await conn.fetchval(SQL_CONTENT_EMBEDDED)
    content_last_24h   = await conn.fetchval(SQL_CONTENT_LAST_24H)
    clusters_total     = await conn.fetchval(SQL_CLUSTERS_TOTAL)
    signals_last_30d   = await conn.fetchval(SQL_SIGNALS_LAST_30D)
    reports_last_30d   = await conn.fetchval(SQL_REPORTS_LAST_30D)
    sources_active     = await conn.fetchval(SQL_SOURCES_ACTIVE)
    sources_down       = await conn.fetchval(SQL_SOURCES_DOWN)
    content_zh         = await conn.fetchval(SQL_CONTENT_ZH)
    content_translated = await conn.fetchval(SQL_CONTENT_TRANSLATED)
    entities_from_zh   = await conn.fetchval(SQL_ENTITIES_FROM_ZH)

    return {
        "content_items_total":      int(content_total),
        "content_items_embedded":   int(content_embedded),
        "content_items_last_24h":   int(content_last_24h),
        "narrative_clusters_total": int(clusters_total),
        "signals_last_30d":         int(signals_last_30d),
        "reports_last_30d":         int(reports_last_30d),
        "sources_active":           int(sources_active),
        "sources_down":             int(sources_down),
        # Multilingual pipeline metrics
        "content_items_zh":         int(content_zh),
        "content_items_translated": int(content_translated),
        "extracted_entities_zh":    int(entities_from_zh),
    }


async def get_vector_health(conn: asyncpg.Connection) -> dict[str, Any]:
    """Read-only vector pipeline health metrics for make validate-vector."""

    # Migration checks — do columns/tables exist?
    near_dup_table = await conn.fetchval(SQL_NEAR_DUP_TABLE_EXISTS)
    archived_at_col = await conn.fetchval(SQL_COLUMN_EXISTS, "narrative_clusters", "archived_at")
    label_hash_col = await conn.fetchval(SQL_COLUMN_EXISTS, "narrative_clusters", "label_item_hash")
    label_gen_col = await conn.fetchval(SQL_COLUMN_EXISTS, "narrative_clusters", "label_generated_at")

    # HNSW index check
    hnsw_indexdef = await conn.fetchval(SQL_HNSW_INDEX_CHECK)
    hnsw_active = bool(hnsw_indexdef and "hnsw" in hnsw_indexdef.lower())

    # Data counts (safe even if tables don't exist yet via migration)
    near_dup_count = 0
    if near_dup_table:
        near_dup_count = int(await conn.fetchval(SQL_NEAR_DUPLICATES_COUNT))

    archived_count = 0
    if archived_at_col:
        archived_count = int(await conn.fetchval(SQL_ARCHIVED_CLUSTERS))

    labeled_count = 0
    if label_hash_col and label_gen_col:
        labeled_count = int(await conn.fetchval(SQL_LABELED_CLUSTERS))

    convergence_index = await conn.fetchval(SQL_CONVERGENCE_INDEX)
    convergence_signals = int(await conn.fetchval(SQL_CONVERGENCE_SIGNALS))

    backfilled_items = int(await conn.fetchval(SQL_BACKFILLED_ITEMS))

    return {
        "migrations": {
            "002_near_duplicates": bool(near_dup_table),
            "003_hnsw_index": hnsw_active,
            "004_cluster_temporal": bool(archived_at_col),
            "005_label_staleness": bool(label_hash_col and label_gen_col),
            "006_cross_topic_signals": bool(convergence_index),
        },
        "hnsw_index_active": hnsw_active,
        "hnsw_indexdef": hnsw_indexdef or "",
        "near_duplicates_count": near_dup_count,
        "archived_clusters_count": archived_count,
        "labeled_clusters_count": labeled_count,
        "convergence_signals_count": convergence_signals,
        "backfilled_items_count": backfilled_items,
    }
