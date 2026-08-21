"""Keyword alert rules repository — all SQL for alert CRUD and triggers."""

from __future__ import annotations

from typing import Any

from anveshak.db import DBConnection

SQL_LIST_RULES = """
    SELECT id, topic_id, keywords, match_mode, is_active,
           notify_websocket, created_by, created_at, updated_at
    FROM keyword_alert_rules
    WHERE topic_id = $1
    ORDER BY created_at DESC
"""

SQL_LIST_RULES_BY_ORG = """
    SELECT id, topic_id, keywords, match_mode, is_active,
           notify_websocket, created_by, created_at, updated_at
    FROM keyword_alert_rules
    WHERE topic_id = $1 AND org_id = $2
    ORDER BY created_at DESC
"""

SQL_GET_RULE = """
    SELECT id, topic_id, keywords, match_mode, is_active,
           notify_websocket, created_by, org_id, created_at, updated_at
    FROM keyword_alert_rules
    WHERE id = $1
"""

SQL_INSERT_RULE = """
    INSERT INTO keyword_alert_rules
        (id, topic_id, keywords, match_mode, is_active, notify_websocket,
         created_by, org_id, created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            '{"classification":"OPEN","domain":"alert","owner_org":"anveshak"}'::jsonb)
    RETURNING id
"""

SQL_UPDATE_RULE = """
    UPDATE keyword_alert_rules
    SET keywords = COALESCE($2, keywords),
        match_mode = COALESCE($3, match_mode),
        is_active = COALESCE($4, is_active),
        updated_at = NOW()
    WHERE id = $1
    RETURNING id, keywords, match_mode, is_active
"""

SQL_DELETE_RULE = "DELETE FROM keyword_alert_rules WHERE id = $1 RETURNING id"

SQL_LIST_TRIGGERS = """
    SELECT t.id, t.rule_id, t.content_item_id, t.matched_keywords,
           t.triggered_at, ci.url, LEFT(ci.clean_text, 200) AS content_snippet,
           r.keywords AS rule_keywords
    FROM keyword_alert_triggers t
    JOIN content_items ci ON t.content_item_id = ci.id
    JOIN keyword_alert_rules r ON t.rule_id = r.id
    WHERE r.topic_id = $1
    ORDER BY t.triggered_at DESC
    LIMIT $2 OFFSET $3
"""


async def list_rules(conn: DBConnection, topic_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_RULES, topic_id)
    return [dict(r) for r in rows]


async def get_rule(conn: DBConnection, rule_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_RULE, rule_id)
    return dict(row) if row else None


async def create_rule(
    conn: DBConnection,
    rule_id: str,
    topic_id: str,
    keywords: list[str],
    match_mode: str,
    created_by: str,
    org_id: str | None,
    now: Any,
) -> str:
    row = await conn.fetchrow(
        SQL_INSERT_RULE,
        rule_id,
        topic_id,
        keywords,
        match_mode,
        True,
        True,
        created_by,
        org_id,
        now,
        now,
    )
    if row is None:
        # SQL_INSERT_RULE is INSERT ... RETURNING with no ON CONFLICT, so this is
        # unreachable: asyncpg raises on failure rather than returning None.
        raise RuntimeError(f"keyword alert rule insert returned no row: {rule_id}")
    return row["id"]


async def update_rule(
    conn: DBConnection,
    rule_id: str,
    keywords: list[str] | None = None,
    match_mode: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_UPDATE_RULE, rule_id, keywords, match_mode, is_active)
    return dict(row) if row else None


async def delete_rule(conn: DBConnection, rule_id: str) -> bool:
    row = await conn.fetchrow(SQL_DELETE_RULE, rule_id)
    return row is not None


async def list_triggers(
    conn: DBConnection, topic_id: str, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_LIST_TRIGGERS, topic_id, limit, offset)
    return [
        {
            **dict(r),
            "content_snippet": (r["content_snippet"] or "")[:200],
        }
        for r in rows
    ]
