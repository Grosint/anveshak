"""Audit trail repository — log and retrieve user actions.

Every mutating API operation (create, update, delete) should call log_action()
to record who did what, when, and from where. Defence/LEA requirement:
"who saw what when" is not optional.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_AUDIT = """
    INSERT INTO audit_trail (
        id, user_id, action, resource_type, resource_id,
        details, ip_address, created_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""

SQL_GET_AUDIT_TRAIL = """
    SELECT id, user_id, action, resource_type, resource_id,
           details, ip_address, created_at
    FROM audit_trail
    WHERE resource_type = $1
    ORDER BY created_at DESC
    LIMIT $2 OFFSET $3
"""

SQL_GET_AUDIT_TRAIL_ALL = """
    SELECT id, user_id, action, resource_type, resource_id,
           details, ip_address, created_at
    FROM audit_trail
    ORDER BY created_at DESC
    LIMIT $1 OFFSET $2
"""

SQL_GET_AUDIT_TRAIL_BY_RESOURCE = """
    SELECT id, user_id, action, resource_type, resource_id,
           details, ip_address, created_at
    FROM audit_trail
    WHERE resource_type = $1 AND resource_id = $2
    ORDER BY created_at DESC
    LIMIT $3 OFFSET $4
"""

_LABELS_JSON = '{"classification":"OPEN","domain":"audit","owner_org":"anveshak"}'

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def log_action(
    conn: asyncpg.Connection,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    ip_address: str = "",
) -> None:
    """Insert an audit trail entry."""
    await conn.execute(
        SQL_INSERT_AUDIT,
        str(uuid.uuid4()),
        user_id,
        action,
        resource_type,
        resource_id,
        json.dumps(details or {}),
        ip_address,
        datetime.now(UTC),
        _LABELS_JSON,
    )


async def get_audit_trail(
    conn: asyncpg.Connection,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Retrieve audit trail entries, optionally filtered by resource_type and resource_id."""
    if resource_type and resource_id:
        rows = await conn.fetch(
            SQL_GET_AUDIT_TRAIL_BY_RESOURCE, resource_type, resource_id, limit, offset
        )
    elif resource_type:
        rows = await conn.fetch(SQL_GET_AUDIT_TRAIL, resource_type, limit, offset)
    else:
        rows = await conn.fetch(SQL_GET_AUDIT_TRAIL_ALL, limit, offset)
    return [dict(r) for r in rows]
