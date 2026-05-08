"""Integration tests — test database isolation.

Verifies that:
  1. Tests connect to anveshak_test, NOT anveshak (production)
  2. The test database has all required extensions (pgvector, uuid-ossp, etc.)
  3. The test database has the schema (tables created by Alembic)
  4. The safety guard refuses to run against the production database

Requires: make up + make create-test-db + make migrate-test
"""
from __future__ import annotations

import pytest

from tests.conftest import POSTGRES_URL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# 1. Conftest defaults to anveshak_test
# ---------------------------------------------------------------------------

def test_postgres_url_points_to_test_database():
    """POSTGRES_URL in conftest must default to anveshak_test, never production."""
    assert "anveshak_test" in POSTGRES_URL, (
        f"Tests are configured to use '{POSTGRES_URL}' which does not contain "
        "'anveshak_test'. Tests must NEVER run against the production database."
    )


# ---------------------------------------------------------------------------
# 2. Test database has required extensions
# ---------------------------------------------------------------------------

REQUIRED_EXTENSIONS = ["vector", "uuid-ossp", "pg_trgm", "btree_gin"]


async def test_test_db_has_required_extensions(db_pool):
    """anveshak_test must have the same extensions as production."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT extname FROM pg_extension WHERE extname = ANY($1)",
            REQUIRED_EXTENSIONS,
        )
    installed = {r["extname"] for r in rows}
    missing = set(REQUIRED_EXTENSIONS) - installed
    assert not missing, (
        f"Test database is missing extensions: {missing}. "
        "Run: make create-test-db"
    )


# ---------------------------------------------------------------------------
# 3. Test database has the schema (tables from Alembic)
# ---------------------------------------------------------------------------

REQUIRED_TABLES = [
    "topics", "sources", "content_items", "narrative_clusters",
    "signals", "reports", "media_assets", "vision_results",
    "credibility_audit_log", "topic_sources",
]


async def test_test_db_has_schema(db_pool):
    """anveshak_test must have all Alembic-managed tables."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY($1)",
            REQUIRED_TABLES,
        )
    found = {r["table_name"] for r in rows}
    missing = set(REQUIRED_TABLES) - found
    assert not missing, (
        f"Test database is missing tables: {missing}. "
        "Run: make migrate-test"
    )


# ---------------------------------------------------------------------------
# 4. Test database is isolated from production data
# ---------------------------------------------------------------------------

async def test_test_db_does_not_contain_demo_data(db_pool):
    """anveshak_test should not contain the seed demo data (that lives in production)."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM topics WHERE name LIKE 'E2E Validation%' "
            "OR name LIKE '%Drone Surveillance%'"
        )
    assert count == 0, (
        f"Test database contains {count} production/demo topics. "
        "Tests should run against a clean anveshak_test database."
    )
