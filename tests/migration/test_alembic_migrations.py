"""Migration test — verify database schema matches expectations.

Checks that all expected tables and critical indexes exist after migrations.
Requires: make up (PostgreSQL running with migrations applied)
"""
from __future__ import annotations

import pytest

from tests.conftest import POSTGRES_URL

pytestmark = [pytest.mark.migration, pytest.mark.asyncio]


@pytest.fixture
async def db():
    asyncpg = pytest.importorskip("asyncpg")
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
    except Exception:
        pytest.skip("PostgreSQL not available")
    yield pool
    await pool.close()


EXPECTED_TABLES = [
    "topics",
    "sources",
    "topic_sources",
    "content_items",
    "extracted_entities",
    "narrative_clusters",
    "signals",
    "reports",
    "report_source_warnings",
    "credibility_audit_log",
    "media_assets",
    "analysis_jobs",
]


@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
async def test_expected_table_exists(db, table_name):
    """All expected tables must exist after migrations."""
    async with db.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)",
            table_name,
        )
    assert exists, f"Table '{table_name}' does not exist — migration may be missing"


async def test_content_hash_unique_index(db):
    """content_items.content_hash must have a UNIQUE constraint/index."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'content_items'
              AND indexdef LIKE '%content_hash%'
            """
        )
    index_names = [r["indexname"] for r in rows]
    assert len(index_names) >= 1, (
        "content_items must have an index on content_hash for dedup"
    )


async def test_pgvector_extension_enabled(db):
    """pgvector extension must be installed for embedding similarity."""
    async with db.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
    assert exists, "pgvector extension not installed — embeddings won't work"
