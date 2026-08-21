"""Content repository — full item detail and pgvector similarity search."""

from __future__ import annotations

from typing import Any

from anveshak.db import DBConnection

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_GET_CONTENT_ITEM = """
    SELECT ci.id, ci.url, ci.clean_text, ci.language,
           ci.translated_text, ci.translation_model,
           ci.credibility_score_at_capture, ci.captured_at, ci.content_hash,
           ci.topic_id, ci.source_id,
           s.name AS source_name, s.platform
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.id = $1
"""

SQL_GET_ENTITIES = """
    SELECT id, entity_type, entity_text, confidence, language, created_at
    FROM extracted_entities
    WHERE content_item_id = $1
    ORDER BY entity_type, entity_text
"""

SQL_VECTOR_SEARCH = """
    SELECT ci.id, ci.url,
           LEFT(ci.clean_text, 500) AS clean_text,
           LEFT(ci.translated_text, 500) AS translated_text,
           ci.language, ci.captured_at,
           ci.credibility_score_at_capture,
           1 - (ci.embedding <=> $1::vector) AS similarity_score
    FROM content_items ci
    WHERE ci.topic_id = $2
      AND ci.embedding IS NOT NULL
    ORDER BY ci.embedding <=> $1::vector
    LIMIT 20
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def get_content_item(conn: DBConnection, content_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_CONTENT_ITEM, content_id)
    return dict(row) if row else None


async def get_entities(conn: DBConnection, content_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_ENTITIES, content_id)
    return [dict(r) for r in rows]


async def vector_search(
    conn: DBConnection,
    query_vec_str: str,
    topic_id: str,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_VECTOR_SEARCH, query_vec_str, topic_id)
    return [dict(r) for r in rows]
