"""Identifier search DB layer — queries for Engine C Step 7.

All SQL is module-level constants. Functions take asyncpg.Connection
and return plain dicts (no Pydantic — route layer handles serialization).
"""
from __future__ import annotations

from typing import Any, Optional

import asyncpg


# ---------------------------------------------------------------------------
# Identifier types covered by the partial index (Engine C migration 009)
# ---------------------------------------------------------------------------

IDENTIFIER_TYPES = (
    "PHONE_IN", "UPI", "EMAIL", "CRYPTO_BTC", "CRYPTO_ETH",
    "CRYPTO_TRC20", "TELEGRAM_HANDLE", "INSTAGRAM_HANDLE",
    "URL_DOMAIN", "GSTIN", "UDYAM", "PAN", "IFSC",
    "BANK_ACCOUNT", "SEBI_REG",
)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_SEARCH_IDENTIFIERS = """
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.url AS content_url, ci.topic_id
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN (
          'PHONE_IN', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
          'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
          'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
          'BANK_ACCOUNT', 'SEBI_REG'
      )
      AND ee.entity_text ILIKE $2
    ORDER BY ee.confidence DESC
    LIMIT $3
"""

SQL_SEARCH_IDENTIFIERS_WITH_TYPE = """
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.url AS content_url, ci.topic_id
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type = $2
      AND ee.entity_text ILIKE $3
    ORDER BY ee.confidence DESC
    LIMIT $4
"""

SQL_TOP_IDENTIFIERS = """
    SELECT identifier_type, identifier_value,
           source_count, content_item_count,
           first_seen_at, last_seen_at
    FROM identifier_clusters
    WHERE topic_id = $1
    ORDER BY source_count DESC
    LIMIT $2
"""

SQL_TOP_IDENTIFIERS_WITH_TYPE = """
    SELECT identifier_type, identifier_value,
           source_count, content_item_count,
           first_seen_at, last_seen_at
    FROM identifier_clusters
    WHERE topic_id = $1
      AND identifier_type = $2
    ORDER BY source_count DESC
    LIMIT $3
"""

SQL_LIST_CLUSTERS = """
    SELECT id, topic_id, identifier_type, identifier_value,
           source_count, content_item_count,
           first_seen_at, last_seen_at, created_at
    FROM identifier_clusters
    WHERE topic_id = $1
    ORDER BY source_count DESC
    LIMIT $2 OFFSET $3
"""

SQL_LIST_CLUSTERS_WITH_TYPE = """
    SELECT id, topic_id, identifier_type, identifier_value,
           source_count, content_item_count,
           first_seen_at, last_seen_at, created_at
    FROM identifier_clusters
    WHERE topic_id = $1
      AND identifier_type = $2
    ORDER BY source_count DESC
    LIMIT $3 OFFSET $4
"""

SQL_GET_CLUSTER = """
    SELECT id, topic_id, identifier_type, identifier_value,
           source_count, content_item_count,
           first_seen_at, last_seen_at, created_at
    FROM identifier_clusters
    WHERE id = $1
"""

SQL_CLUSTER_ITEMS = """
    SELECT ici.content_item_id, ici.source_id,
           s.name AS source_name, s.platform AS source_platform,
           ci.url AS content_url, ci.captured_at
    FROM identifier_cluster_items ici
    JOIN content_items ci ON ici.content_item_id = ci.id
    JOIN sources s ON ici.source_id = s.id
    WHERE ici.identifier_cluster_id = $1
    ORDER BY ci.captured_at DESC
"""

SQL_EXPORT_IDENTIFIERS = """
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.url AS content_url,
           s.name AS source_name, s.platform AS source_platform,
           ci.captured_at
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN (
          'PHONE_IN', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
          'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
          'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
          'BANK_ACCOUNT', 'SEBI_REG'
      )
    ORDER BY ee.entity_type, ee.entity_text
    LIMIT $2
"""

SQL_CO_OCCURRENCE = """
    SELECT DISTINCT ci.id AS content_item_id,
           ci.url AS content_url, ci.captured_at,
           s.name AS source_name
    FROM extracted_entities e1
    JOIN extracted_entities e2
        ON e1.content_item_id = e2.content_item_id
        AND e1.id != e2.id
    JOIN content_items ci ON e1.content_item_id = ci.id
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND e1.entity_text = $2
      AND e2.entity_text = $3
    ORDER BY ci.captured_at DESC
    LIMIT $4
"""


# ---------------------------------------------------------------------------
# DB functions
# ---------------------------------------------------------------------------

async def search_identifiers(
    conn: asyncpg.Connection,
    *,
    q: str,
    topic_id: str,
    identifier_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search extracted identifiers with ILIKE partial match."""
    pattern = f"%{q}%"
    if identifier_type:
        rows = await conn.fetch(
            SQL_SEARCH_IDENTIFIERS_WITH_TYPE,
            topic_id, identifier_type, pattern, limit,
        )
    else:
        rows = await conn.fetch(
            SQL_SEARCH_IDENTIFIERS,
            topic_id, pattern, limit,
        )
    return [dict(r) for r in rows]


async def get_top_identifiers(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    identifier_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Top identifiers by source_count from identifier_clusters."""
    if identifier_type:
        rows = await conn.fetch(
            SQL_TOP_IDENTIFIERS_WITH_TYPE,
            topic_id, identifier_type, limit,
        )
    else:
        rows = await conn.fetch(SQL_TOP_IDENTIFIERS, topic_id, limit)
    return [dict(r) for r in rows]


async def list_identifier_clusters(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    identifier_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List identifier clusters for a topic, sorted by source_count DESC."""
    if identifier_type:
        rows = await conn.fetch(
            SQL_LIST_CLUSTERS_WITH_TYPE,
            topic_id, identifier_type, limit, offset,
        )
    else:
        rows = await conn.fetch(SQL_LIST_CLUSTERS, topic_id, limit, offset)
    return [dict(r) for r in rows]


async def get_cluster_detail(
    conn: asyncpg.Connection,
    *,
    cluster_id: str,
) -> Optional[dict[str, Any]]:
    """Full cluster detail with linked content items and sources."""
    cluster = await conn.fetchrow(SQL_GET_CLUSTER, cluster_id)
    if not cluster:
        return None

    items = await conn.fetch(SQL_CLUSTER_ITEMS, cluster_id)

    result = dict(cluster)
    result["items"] = [dict(r) for r in items]
    return result


async def export_identifiers(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Flat identifier rows for CSV/JSON export."""
    rows = await conn.fetch(SQL_EXPORT_IDENTIFIERS, topic_id, limit)
    return [dict(r) for r in rows]


async def get_co_occurrence(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    identifier_a: str,
    identifier_b: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Content items where both identifiers co-occur."""
    rows = await conn.fetch(
        SQL_CO_OCCURRENCE,
        topic_id, identifier_a, identifier_b, limit,
    )
    return [dict(r) for r in rows]
