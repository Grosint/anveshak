"""Catalog & discovery repository — SQL for source catalog and discovered sources."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants — source_catalog
# ---------------------------------------------------------------------------

SQL_LIST_CATALOG_BY_TAGS = """
    SELECT id, name, url_or_handle, platform, domain_tags,
           reliability_tier, bias_indicator, risk_level, language,
           category, description, subscriber_count, activity_frequency,
           signal_contribution_count, relevance_hit_rate,
           cluster_participation_rate, topics_approved_count,
           recommendation_rank, created_at, updated_at
    FROM source_catalog
    WHERE domain_tags && $1
       OR EXISTS (
           SELECT 1 FROM unnest($1) AS kw
           WHERE LOWER(source_catalog.name) LIKE '%' || REPLACE(REPLACE(REPLACE(kw, '\\', '\\\\'), '%', '\\%'), '_', '\\_') || '%'
              OR LOWER(source_catalog.description) LIKE '%' || REPLACE(REPLACE(REPLACE(kw, '\\', '\\\\'), '%', '\\%'), '_', '\\_') || '%'
       )
    ORDER BY
        CASE WHEN domain_tags && $1 THEN 0 ELSE 1 END,
        CASE recommendation_rank
            WHEN 'most_recommended' THEN 1
            WHEN 'proven'           THEN 2
            WHEN 'curated'          THEN 3
            WHEN 'low_performer'    THEN 4
        END,
        CASE reliability_tier
            WHEN 'S' THEN 1
            WHEN 'A' THEN 2
            WHEN 'B' THEN 3
            WHEN 'C' THEN 4
        END
"""

SQL_GET_CATALOG_ENTRY = """
    SELECT id, name, url_or_handle, platform, domain_tags,
           reliability_tier, bias_indicator, risk_level, language,
           category, description, subscriber_count, activity_frequency,
           signal_contribution_count, relevance_hit_rate,
           cluster_participation_rate, topics_approved_count,
           recommendation_rank, created_at, updated_at
    FROM source_catalog
    WHERE id = $1
"""

SQL_LIST_ALL_CATALOG = """
    SELECT id, name, url_or_handle, platform, domain_tags,
           reliability_tier, bias_indicator, risk_level, language,
           category, description, subscriber_count, activity_frequency,
           signal_contribution_count, relevance_hit_rate,
           cluster_participation_rate, topics_approved_count,
           recommendation_rank, created_at, updated_at
    FROM source_catalog
    ORDER BY
        CASE recommendation_rank
            WHEN 'most_recommended' THEN 1
            WHEN 'proven'           THEN 2
            WHEN 'curated'          THEN 3
            WHEN 'low_performer'    THEN 4
        END,
        name
"""

SQL_INSERT_CATALOG_ENTRY = """
    INSERT INTO source_catalog (
        id, name, url_or_handle, platform, domain_tags,
        reliability_tier, bias_indicator, risk_level, language,
        category, description, subscriber_count, activity_frequency,
        created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
    ON CONFLICT (platform, url_or_handle) DO NOTHING
"""

SQL_UPDATE_CATALOG_EFFECTIVENESS = """
    UPDATE source_catalog
    SET signal_contribution_count  = $2,
        relevance_hit_rate         = $3,
        cluster_participation_rate = $4,
        topics_approved_count      = $5,
        recommendation_rank        = $6,
        updated_at                 = $7
    WHERE id = $1
"""

# ---------------------------------------------------------------------------
# SQL constants — catalog_approvals
# ---------------------------------------------------------------------------

SQL_INSERT_CATALOG_APPROVAL = """
    INSERT INTO catalog_approvals
        (catalog_entry_id, topic_id, source_id, approved_by, approved_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (catalog_entry_id, topic_id) DO NOTHING
"""

# ---------------------------------------------------------------------------
# SQL constants — discovered_sources
# ---------------------------------------------------------------------------

SQL_LIST_DISCOVERED = """
    SELECT id, topic_id, domain_or_handle, platform, discovery_method,
           citation_count, confidence_score, evidence, status, source_id,
           created_at, updated_at
    FROM discovered_sources
    WHERE topic_id = $1
    ORDER BY citation_count DESC, created_at DESC
"""

SQL_LIST_DISCOVERED_BY_STATUS = """
    SELECT id, topic_id, domain_or_handle, platform, discovery_method,
           citation_count, confidence_score, evidence, status, source_id,
           created_at, updated_at
    FROM discovered_sources
    WHERE topic_id = $1 AND status = $2
    ORDER BY citation_count DESC, created_at DESC
"""

SQL_UPSERT_DISCOVERED = """
    INSERT INTO discovered_sources
        (id, topic_id, domain_or_handle, platform, discovery_method,
         citation_count, confidence_score, evidence, status,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', $9, $9, $10)
    ON CONFLICT (topic_id, domain_or_handle, discovery_method)
    DO UPDATE SET
        citation_count   = discovered_sources.citation_count + EXCLUDED.citation_count,
        confidence_score = COALESCE(EXCLUDED.confidence_score, discovered_sources.confidence_score),
        evidence         = discovered_sources.evidence || EXCLUDED.evidence,
        updated_at       = EXCLUDED.updated_at
"""

SQL_APPROVE_DISCOVERED = """
    UPDATE discovered_sources
    SET status    = 'approved',
        source_id = $2,
        updated_at = $3
    WHERE id = $1
"""

SQL_DISMISS_DISCOVERED = """
    UPDATE discovered_sources
    SET status     = 'dismissed',
        updated_at = $2
    WHERE id = $1
"""

# ---------------------------------------------------------------------------
# Repository functions — source_catalog
# ---------------------------------------------------------------------------


async def list_catalog_suggestions(
    conn: asyncpg.Connection,
    keywords: list[str],
) -> list[dict[str, Any]]:
    """List catalog entries whose domain_tags overlap with topic keywords."""
    rows = await conn.fetch(SQL_LIST_CATALOG_BY_TAGS, keywords)
    return [dict(r) for r in rows]


async def get_catalog_entry(
    conn: asyncpg.Connection, entry_id: str
) -> dict[str, Any] | None:
    """Fetch a single catalog entry by ID."""
    row = await conn.fetchrow(SQL_GET_CATALOG_ENTRY, entry_id)
    return dict(row) if row else None


async def list_all_catalog(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """List all catalog entries (admin view)."""
    rows = await conn.fetch(SQL_LIST_ALL_CATALOG)
    return [dict(r) for r in rows]


async def insert_catalog_approval(
    conn: asyncpg.Connection,
    catalog_entry_id: str,
    topic_id: str,
    source_id: str,
    approved_by: str,
    labels_json: str,
) -> None:
    """Record that an analyst approved a catalog entry for a topic."""
    await conn.execute(
        SQL_INSERT_CATALOG_APPROVAL,
        catalog_entry_id, topic_id, source_id, approved_by,
        datetime.now(UTC), labels_json,
    )


async def update_catalog_effectiveness(
    conn: asyncpg.Connection,
    catalog_entry_id: str,
    signal_contribution_count: int,
    relevance_hit_rate: float,
    cluster_participation_rate: float,
    topics_approved_count: int,
    recommendation_rank: str,
) -> None:
    """Update effectiveness analytics for a catalog entry."""
    await conn.execute(
        SQL_UPDATE_CATALOG_EFFECTIVENESS,
        catalog_entry_id,
        signal_contribution_count,
        relevance_hit_rate,
        cluster_participation_rate,
        topics_approved_count,
        recommendation_rank,
        datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Repository functions — discovered_sources
# ---------------------------------------------------------------------------


async def list_discovered(
    conn: asyncpg.Connection,
    topic_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List discovered sources for a topic, optionally filtered by status."""
    if status:
        rows = await conn.fetch(SQL_LIST_DISCOVERED_BY_STATUS, topic_id, status)
    else:
        rows = await conn.fetch(SQL_LIST_DISCOVERED, topic_id)
    return [dict(r) for r in rows]


async def upsert_discovered(
    conn: asyncpg.Connection,
    topic_id: str,
    domain_or_handle: str,
    platform: str,
    discovery_method: str,
    citation_count: int = 1,
    confidence_score: float | None = None,
    evidence: dict[str, Any] | None = None,
    labels_json: str = '{}',
) -> None:
    """Insert or update a discovered source.

    ON CONFLICT increments citation_count and merges evidence.
    """
    now = datetime.now(UTC)
    evidence_json = json.dumps(evidence) if evidence else '{}'
    await conn.execute(
        SQL_UPSERT_DISCOVERED,
        str(uuid.uuid4()),  # id
        topic_id,
        domain_or_handle,
        platform,
        discovery_method,
        citation_count,
        confidence_score,
        evidence_json,
        now,
        labels_json,
    )


async def approve_discovered(
    conn: asyncpg.Connection,
    discovered_id: str,
    source_id: str,
) -> None:
    """Mark a discovered source as approved and link to the created source."""
    await conn.execute(
        SQL_APPROVE_DISCOVERED,
        discovered_id,
        source_id,
        datetime.now(UTC),
    )


async def dismiss_discovered(
    conn: asyncpg.Connection,
    discovered_id: str,
) -> None:
    """Dismiss a discovered source suggestion."""
    await conn.execute(
        SQL_DISMISS_DISCOVERED,
        discovered_id,
        datetime.now(UTC),
    )
