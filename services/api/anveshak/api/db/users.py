"""User management repository — CRUD for the users table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from anveshak.db import DBConnection

from ..auth.jwt import pwd_context

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LIST_USERS = """
    SELECT id, username, role, org_id, created_at, updated_at
    FROM users
    ORDER BY created_at
"""

SQL_LIST_USERS_BY_ORG = """
    SELECT id, username, role, org_id, created_at, updated_at
    FROM users
    WHERE org_id = $1
    ORDER BY created_at
"""

SQL_CREATE_USER = """
    INSERT INTO users (id, username, password_hash, role, org_id, created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6, $7,
            '{"classification":"OPEN","domain":"admin"}'::jsonb)
    RETURNING id
"""

SQL_DELETE_USER = "DELETE FROM users WHERE id = $1"

SQL_UPDATE_ROLE = "UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2"


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def list_users(conn: DBConnection) -> list[dict[str, Any]]:
    """Return all users without password_hash."""
    rows = await conn.fetch(SQL_LIST_USERS)
    return [dict(r) for r in rows]


async def create_user(
    conn: DBConnection,
    username: str,
    password: str,
    role: str = "analyst",
    org_id: str | None = None,
) -> str:
    """Create a new user with hashed password. Returns user ID."""
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    hashed = pwd_context.hash(password)
    created = await conn.fetchval(
        SQL_CREATE_USER,
        user_id,
        username,
        hashed,
        role,
        org_id,
        now,
        now,
    )
    if created is None:
        # INSERT ... RETURNING id with no ON CONFLICT: unreachable, asyncpg raises
        # on failure rather than returning None.
        raise RuntimeError(f"user insert returned no id: {username}")
    return str(created)


async def list_users_by_org(
    conn: DBConnection,
    org_id: str,
) -> list[dict[str, Any]]:
    """Return users filtered by org_id."""
    rows = await conn.fetch(SQL_LIST_USERS_BY_ORG, org_id)
    return [dict(r) for r in rows]


async def delete_user(conn: DBConnection, user_id: str) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    result = await conn.execute(SQL_DELETE_USER, user_id)
    return result.endswith("1")


async def update_user_role(
    conn: DBConnection,
    user_id: str,
    role: str,
) -> None:
    """Update a user's role."""
    await conn.execute(SQL_UPDATE_ROLE, role, user_id)
