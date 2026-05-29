"""Organization repository — CRUD for the organizations table."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_CREATE_ORG = """
    INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at, labels)
    VALUES ($1, $2, $3, true, $4, $5,
            '{"classification":"OPEN","domain":"platform"}'::jsonb)
    RETURNING id
"""

SQL_LIST_ORGS = """
    SELECT id, name, slug, is_active, created_at, updated_at
    FROM organizations
    ORDER BY created_at
"""

SQL_GET_ORG = "SELECT * FROM organizations WHERE id = $1"

SQL_UPDATE_ORG = """
    UPDATE organizations
    SET name = COALESCE($2, name),
        is_active = COALESCE($3, is_active),
        updated_at = $4
    WHERE id = $1
"""


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def create_organization(
    conn: asyncpg.Connection,
    name: str,
    slug: str,
) -> str:
    """Create a new organization. Returns org ID."""
    org_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    return await conn.fetchval(SQL_CREATE_ORG, org_id, name, slug, now, now)


async def list_organizations(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Return all organizations."""
    rows = await conn.fetch(SQL_LIST_ORGS)
    return [dict(r) for r in rows]


async def get_organization(
    conn: asyncpg.Connection,
    org_id: str,
) -> dict[str, Any] | None:
    """Return a single organization or None."""
    row = await conn.fetchrow(SQL_GET_ORG, org_id)
    return dict(row) if row else None


async def update_organization(
    conn: asyncpg.Connection,
    org_id: str,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> None:
    """Update organization fields."""
    now = datetime.now(UTC)
    await conn.execute(SQL_UPDATE_ORG, org_id, name, is_active, now)
