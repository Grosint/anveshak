"""Shared asyncpg pool creation with JSONB codec.

All services MUST use create_db_pool() instead of raw asyncpg.create_pool().
This ensures JSONB columns are automatically decoded to Python dicts,
preventing double-encoding bugs and silent data loss.
"""
from __future__ import annotations

import json

import asyncpg


async def _init_connection(conn: asyncpg.Connection) -> None:
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
