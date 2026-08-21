"""Shared asyncpg pool creation with JSONB codec.

All services MUST use create_db_pool() instead of raw asyncpg.create_pool().
This ensures JSONB columns are automatically decoded to Python dicts,
preventing double-encoding bugs and silent data loss.
"""

from __future__ import annotations

import json
from typing import TypeAlias, Union

import asyncpg
import asyncpg.pool

# Annotate every function that takes a connection with this, not with
# asyncpg.Connection.
#
# `async with pool.acquire() as conn` yields a PoolConnectionProxy, not a
# Connection. The proxy forwards every Connection method at runtime, so the code
# works either way, but a bare `conn: asyncpg.Connection` annotation is a lie
# that pyright reports at each of the call sites.
DBConnection: TypeAlias = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


async def _init_connection(conn: DBConnection) -> None:
    """Register JSON/JSONB codecs for automatic decode on every connection."""
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_db_pool(
    postgres_url: str,
    min_size: int = 2,
    max_size: int = 5,
) -> asyncpg.Pool:
    """Create asyncpg pool with JSONB codec registered on every connection."""
    url = postgres_url.replace("+asyncpg", "")
    return await asyncpg.create_pool(
        url,
        min_size=min_size,
        max_size=max_size,
        init=_init_connection,
    )
