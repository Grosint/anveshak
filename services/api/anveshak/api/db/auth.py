"""Auth repository — user lookup for authentication."""
from __future__ import annotations

from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_GET_USER_BY_USERNAME = (
    "SELECT id, password_hash, role, org_id FROM users WHERE username = $1"
)

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def get_user_by_username(
    conn: asyncpg.Connection, username: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_USER_BY_USERNAME, username)
    return dict(row) if row else None
