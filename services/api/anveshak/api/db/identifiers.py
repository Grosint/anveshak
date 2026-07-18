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
    "PHONE_IN", "PHONE_INTL", "UPI", "EMAIL", "CRYPTO_BTC", "CRYPTO_ETH",
    "CRYPTO_TRC20", "TELEGRAM_HANDLE", "INSTAGRAM_HANDLE",
    "FACEBOOK_HANDLE", "X_HANDLE",
    "URL_DOMAIN", "GSTIN", "UDYAM", "PAN", "IFSC",
    "BANK_ACCOUNT", "SEBI_REG", "AIRCRAFT_ID",
)

# SQL fragment generated from IDENTIFIER_TYPES — single source of truth
_ID_TYPES_SQL = ", ".join(f"'{t}'" for t in IDENTIFIER_TYPES)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_SEARCH_IDENTIFIERS = f"""
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.url AS content_url, ci.topic_id
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN ({_ID_TYPES_SQL})
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

SQL_TOP_IDENTIFIERS = f"""
    SELECT ee.entity_type AS identifier_type,
           ee.entity_text AS identifier_value,
           COUNT(DISTINCT ci.source_id) AS source_count,
           COUNT(DISTINCT ee.content_item_id) AS content_item_count,
           MIN(ci.captured_at) AS first_seen_at,
           MAX(ci.captured_at) AS last_seen_at
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN ({_ID_TYPES_SQL})
    GROUP BY ee.entity_type, ee.entity_text
    HAVING COUNT(DISTINCT ee.content_item_id) >= $2
    ORDER BY COUNT(DISTINCT ee.content_item_id) DESC
    LIMIT $3
"""

SQL_TOP_IDENTIFIERS_WITH_TYPE = """
    SELECT ee.entity_type AS identifier_type,
           ee.entity_text AS identifier_value,
           COUNT(DISTINCT ci.source_id) AS source_count,
           COUNT(DISTINCT ee.content_item_id) AS content_item_count,
           MIN(ci.captured_at) AS first_seen_at,
           MAX(ci.captured_at) AS last_seen_at
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type = $2
    GROUP BY ee.entity_type, ee.entity_text
    HAVING COUNT(DISTINCT ee.content_item_id) >= $3
    ORDER BY COUNT(DISTINCT ee.content_item_id) DESC
    LIMIT $4
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

SQL_EXPORT_IDENTIFIERS = f"""
    SELECT ee.entity_type, ee.entity_text, ee.confidence,
           ee.content_item_id, ci.url AS content_url,
           s.name AS source_name, s.platform AS source_platform,
           ci.captured_at
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN ({_ID_TYPES_SQL})
    ORDER BY ee.entity_type, ee.entity_text
    LIMIT $2
"""

SQL_SEARCH_IDENTIFIERS_GLOBAL = """
    SELECT ic.identifier_type, ic.identifier_value,
           ic.topic_id, t.name AS topic_name,
           ic.source_count, ic.content_item_count,
           ic.last_seen_at
    FROM identifier_clusters ic
    JOIN topics t ON ic.topic_id = t.id
    WHERE t.org_id = $1
      AND ic.identifier_value ILIKE $2
    ORDER BY ic.source_count DESC
    LIMIT $3
"""

SQL_SEARCH_IDENTIFIERS_GLOBAL_WITH_TYPE = """
    SELECT ic.identifier_type, ic.identifier_value,
           ic.topic_id, t.name AS topic_name,
           ic.source_count, ic.content_item_count,
           ic.last_seen_at
    FROM identifier_clusters ic
    JOIN topics t ON ic.topic_id = t.id
    WHERE t.org_id = $1
      AND ic.identifier_type = $2
      AND ic.identifier_value ILIKE $3
    ORDER BY ic.source_count DESC
    LIMIT $4
"""

SQL_IDENTIFIER_CONVERGENCE = """
    SELECT ic.identifier_type, ic.identifier_value,
           COUNT(DISTINCT ic.topic_id) AS topic_count,
           SUM(ic.source_count) AS total_source_count,
           array_agg(DISTINCT t.name ORDER BY t.name) AS topic_names
    FROM identifier_clusters ic
    JOIN topics t ON ic.topic_id = t.id
    WHERE t.org_id = $1
    GROUP BY ic.identifier_type, ic.identifier_value
    HAVING COUNT(DISTINCT ic.topic_id) >= 2
    ORDER BY COUNT(DISTINCT ic.topic_id) DESC, SUM(ic.source_count) DESC
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
# Template linking SQL
# ---------------------------------------------------------------------------

SQL_LINK_TEMPLATE = """
    INSERT INTO topic_templates (topic_id, template_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

SQL_UNLINK_TEMPLATE = """
    DELETE FROM topic_templates
    WHERE topic_id = $1 AND template_id = $2
"""

SQL_LIST_TOPIC_TEMPLATES = """
    SELECT st.id, st.name, st.display, st.category,
           st.keywords, st.expected_identifiers, st.severity,
           st.legal_sections, st.is_builtin
    FROM scam_templates st
    JOIN topic_templates tt ON tt.template_id = st.id
    WHERE tt.topic_id = $1
    ORDER BY st.severity DESC, st.display ASC
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
    min_items: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Top identifiers by item count, grouped from extracted_entities."""
    if identifier_type:
        rows = await conn.fetch(
            SQL_TOP_IDENTIFIERS_WITH_TYPE,
            topic_id, identifier_type, min_items, limit,
        )
    else:
        rows = await conn.fetch(
            SQL_TOP_IDENTIFIERS, topic_id, min_items, limit,
        )
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


async def search_identifiers_global(
    conn: asyncpg.Connection,
    *,
    q: str,
    org_id: str,
    identifier_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Cross-topic identifier search, scoped to user's org."""
    pattern = f"%{q}%"
    if identifier_type:
        rows = await conn.fetch(
            SQL_SEARCH_IDENTIFIERS_GLOBAL_WITH_TYPE,
            org_id, identifier_type, pattern, limit,
        )
    else:
        rows = await conn.fetch(
            SQL_SEARCH_IDENTIFIERS_GLOBAL,
            org_id, pattern, limit,
        )
    return [dict(r) for r in rows]


async def get_identifier_convergence(
    conn: asyncpg.Connection,
    *,
    org_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Identifiers appearing in 2+ topics within the same org — convergence detection."""
    rows = await conn.fetch(SQL_IDENTIFIER_CONVERGENCE, org_id, limit)
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


# ---------------------------------------------------------------------------
# Template linking functions
# ---------------------------------------------------------------------------

async def link_template(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    template_id: str,
) -> None:
    """Link a scam template to a topic. Idempotent (ON CONFLICT DO NOTHING)."""
    await conn.execute(SQL_LINK_TEMPLATE, topic_id, template_id)


async def unlink_template(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
    template_id: str,
) -> None:
    """Unlink a scam template from a topic."""
    await conn.execute(SQL_UNLINK_TEMPLATE, topic_id, template_id)


async def list_topic_templates(
    conn: asyncpg.Connection,
    *,
    topic_id: str,
) -> list[dict[str, Any]]:
    """List all scam templates linked to a topic."""
    rows = await conn.fetch(SQL_LIST_TOPIC_TEMPLATES, topic_id)
    return [dict(r) for r in rows]
