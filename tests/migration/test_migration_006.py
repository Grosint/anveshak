"""Migration 006 tests — source discovery tables.

Verifies source_catalog, catalog_approvals, discovered_sources tables
and content_items forwarding columns exist after migration 006.

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


# ---------------------------------------------------------------------------
# Table existence
# ---------------------------------------------------------------------------

DISCOVERY_TABLES = [
    "source_catalog",
    "catalog_approvals",
    "discovered_sources",
]


@pytest.mark.parametrize("table_name", DISCOVERY_TABLES)
async def test_discovery_table_exists(db, table_name):
    """All source discovery tables must exist after migration 006."""
    async with db.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)",
            table_name,
        )
    assert exists, f"Table '{table_name}' does not exist — migration 006 may be missing"


# ---------------------------------------------------------------------------
# source_catalog
# ---------------------------------------------------------------------------


async def test_source_catalog_has_expected_columns(db):
    """source_catalog must have all required columns."""
    expected = {
        "id",
        "name",
        "url_or_handle",
        "platform",
        "domain_tags",
        "reliability_tier",
        "bias_indicator",
        "risk_level",
        "language",
        "category",
        "description",
        "subscriber_count",
        "activity_frequency",
        "signal_contribution_count",
        "relevance_hit_rate",
        "cluster_participation_rate",
        "topics_approved_count",
        "recommendation_rank",
        "created_at",
        "updated_at",
        "labels",
    }
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'source_catalog'"
        )
    actual = {r["column_name"] for r in rows}
    missing = expected - actual
    assert not missing, f"source_catalog missing columns: {missing}"


async def test_source_catalog_unique_handle_index(db):
    """source_catalog must have UNIQUE index on (platform, url_or_handle)."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'source_catalog' "
            "AND indexdef LIKE '%url_or_handle%'"
        )
    assert len(rows) >= 1, "source_catalog must have index on url_or_handle"
    # At least one must be UNIQUE
    unique_found = any("UNIQUE" in r["indexdef"] for r in rows)
    assert unique_found, "source_catalog (platform, url_or_handle) must be UNIQUE"


async def test_source_catalog_domain_tags_gin_index(db):
    """source_catalog must have GIN index on domain_tags for array overlap queries."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'source_catalog' "
            "AND indexdef LIKE '%domain_tags%'"
        )
    assert len(rows) >= 1, "source_catalog must have GIN index on domain_tags"
    gin_found = any("gin" in r["indexdef"].lower() for r in rows)
    assert gin_found, "source_catalog.domain_tags index must be GIN"


# ---------------------------------------------------------------------------
# catalog_approvals
# ---------------------------------------------------------------------------


async def test_catalog_approvals_has_expected_columns(db):
    """catalog_approvals must have all required columns."""
    expected = {
        "catalog_entry_id",
        "topic_id",
        "source_id",
        "approved_by",
        "approved_at",
        "labels",
    }
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'catalog_approvals'"
        )
    actual = {r["column_name"] for r in rows}
    missing = expected - actual
    assert not missing, f"catalog_approvals missing columns: {missing}"


async def test_catalog_approvals_pk(db):
    """catalog_approvals PK must be (catalog_entry_id, topic_id)."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "JOIN pg_class c ON c.oid = i.indrelid "
            "WHERE c.relname = 'catalog_approvals' AND i.indisprimary"
        )
    pk_cols = {r["attname"] for r in rows}
    assert pk_cols == {"catalog_entry_id", "topic_id"}, (
        f"catalog_approvals PK must be (catalog_entry_id, topic_id), got {pk_cols}"
    )


# ---------------------------------------------------------------------------
# discovered_sources
# ---------------------------------------------------------------------------


async def test_discovered_sources_has_expected_columns(db):
    """discovered_sources must have all required columns."""
    expected = {
        "id",
        "topic_id",
        "domain_or_handle",
        "platform",
        "discovery_method",
        "citation_count",
        "confidence_score",
        "evidence",
        "status",
        "source_id",
        "created_at",
        "updated_at",
        "labels",
    }
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'discovered_sources'"
        )
    actual = {r["column_name"] for r in rows}
    missing = expected - actual
    assert not missing, f"discovered_sources missing columns: {missing}"


async def test_discovered_sources_unique_constraint(db):
    """discovered_sources must have UNIQUE index on (topic_id, domain_or_handle, discovery_method)."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'discovered_sources' "
            "AND indexdef LIKE '%domain_or_handle%'"
        )
    assert len(rows) >= 1, "discovered_sources must have index on domain_or_handle"
    unique_found = any("UNIQUE" in r["indexdef"] for r in rows)
    assert unique_found, (
        "discovered_sources must have UNIQUE on (topic_id, domain_or_handle, discovery_method)"
    )


# ---------------------------------------------------------------------------
# content_items forwarding columns
# ---------------------------------------------------------------------------


async def test_content_items_has_forwarding_columns(db):
    """content_items must have forwarded_from_channel_id and forwarded_from_channel_name."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'content_items' "
            "AND column_name LIKE 'forwarded_from_%'"
        )
    actual = {r["column_name"] for r in rows}
    expected = {"forwarded_from_channel_id", "forwarded_from_channel_name"}
    assert expected == actual, (
        f"content_items forwarding columns: expected {expected}, got {actual}"
    )
