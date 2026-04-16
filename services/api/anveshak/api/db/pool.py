"""PostgreSQL connection pool and FastAPI dependency."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import asyncpg
import structlog

from ..settings import settings

log = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSON/JSONB codecs so json_agg() results and jsonb columns are
    automatically decoded into Python objects instead of raw strings.

    Without this, asyncpg returns every json/jsonb column as a plain string,
    which means json_agg() results (source_warnings, geojson, source_snapshot,
    labels, etc.) arrive as string "[{...}]" and calling .map() on them in the
    frontend throws TypeError.
    """
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


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.postgres_url.replace("+asyncpg", ""),
        min_size=2,
        max_size=settings.postgres_pool_size,
        init=_init_connection,
    )
    log.info("database.pool_created", max_size=settings.postgres_pool_size)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        log.info("database.pool_closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency — yields a connection from the pool."""
    async with _pool.acquire() as conn:
        yield conn


def get_pool() -> asyncpg.Pool | None:
    """Return the raw pool (used by WebSocket handlers that can't use Depends)."""
    return _pool
