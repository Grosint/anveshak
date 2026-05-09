"""User management repository — CRUD for the users table."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any

import asyncpg

from ..auth.jwt import pwd_context

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LIST_USERS = """
    SELECT id, username, role, created_at, updated_at
    FROM users
    ORDER BY created_at
"""

SQL_CREATE_USER = """
    INSERT INTO users (id, username, password_hash, role, created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, $5, $6,
            '{"classification":"OPEN","domain":"admin","owner_org":"anveshak"}'::jsonb)
    RETURNING id
"""

SQL_DELETE_USER = "DELETE FROM users WHERE id = $1"

SQL_UPDATE_ROLE = "UPDATE users SET role = $1, updated_at = NOW() WHERE id = $2"


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def list_users(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Return all users without password_hash."""
    rows = await conn.fetch(SQL_LIST_USERS)
    return [dict(r) for r in rows]


async def create_user(
    conn: asyncpg.Connection,
    username: str,
    password: str,
    role: str = "analyst",
) -> str:
    """Create a new user with hashed password. Returns user ID."""
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    hashed = pwd_context.hash(password)
    return await conn.fetchval(
        SQL_CREATE_USER,
        user_id, username, hashed, role, now, now,
    )


async def delete_user(conn: asyncpg.Connection, user_id: str) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    result = await conn.execute(SQL_DELETE_USER, user_id)
    return result.endswith("1")


async def update_user_role(
    conn: asyncpg.Connection,
    user_id: str,
    role: str,
) -> None:
    """Update a user's role."""
    await conn.execute(SQL_UPDATE_ROLE, role, user_id)
