"""Template repository — SQL for scam_templates and topic_templates."""
from __future__ import annotations

from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LIST_TEMPLATES = """
    SELECT id, name, display, category, keywords, expected_identifiers,
           severity, legal_sections, is_builtin, is_active, created_at
    FROM scam_templates
    WHERE is_active = true
      AND (org_id IS NULL OR org_id = $1)
    ORDER BY name
"""

SQL_GET_TEMPLATE = """
    SELECT id, name, display, category, keywords, expected_identifiers,
           severity, legal_sections, is_builtin, is_active, created_at
    FROM scam_templates
    WHERE id = $1
"""

SQL_LIST_TOPIC_TEMPLATES = """
    SELECT st.id, st.name, st.display, st.category, st.keywords,
           st.expected_identifiers, st.severity, st.legal_sections,
           st.is_builtin, st.created_at
    FROM topic_templates tt
    JOIN scam_templates st ON st.id = tt.template_id
    WHERE tt.topic_id = $1
    ORDER BY st.name
"""

SQL_LINK_TEMPLATE = """
    INSERT INTO topic_templates (topic_id, template_id)
    VALUES ($1, $2)
    ON CONFLICT (topic_id, template_id) DO NOTHING
"""

SQL_UNLINK_TEMPLATE = """
    DELETE FROM topic_templates
    WHERE topic_id = $1 AND template_id = $2
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def list_templates(
    conn: asyncpg.Connection, org_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TEMPLATES, org_id)
    return [dict(r) for r in rows]


async def get_template(
    conn: asyncpg.Connection, template_id: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_TEMPLATE, template_id)
    return dict(row) if row else None


async def list_topic_templates(
    conn: asyncpg.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TOPIC_TEMPLATES, topic_id)
    return [dict(r) for r in rows]


async def link_template(
    conn: asyncpg.Connection, topic_id: str, template_id: str
) -> None:
    await conn.execute(SQL_LINK_TEMPLATE, topic_id, template_id)


async def unlink_template(
    conn: asyncpg.Connection, topic_id: str, template_id: str
) -> None:
    await conn.execute(SQL_UNLINK_TEMPLATE, topic_id, template_id)
