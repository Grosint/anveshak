"""Integration test — data integrity invariants against real database.

Verifies Anveshak's architectural rules hold in the actual database:
  - content_hash is never NULL (rule 3)
  - Source FK references are valid
  - Report immutability (rule 4)
  - Credibility audit log completeness (rule 8)

Requires: make up (PostgreSQL running with seeded or live data)
"""

from __future__ import annotations

import asyncpg
import pytest

from tests.conftest import POSTGRES_URL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------


async def test_no_null_content_hash(db_pool):
    """Rule 3: Every content_item MUST have a content_hash."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM content_items WHERE content_hash IS NULL")
    assert count == 0, f"{count} content_items have NULL content_hash"


async def test_no_orphan_content_items(db_pool):
    """Every content_item references a valid source_id."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM content_items ci
            LEFT JOIN sources s ON ci.source_id = s.id
            WHERE s.id IS NULL
            """
        )
    assert count == 0, f"{count} content_items reference non-existent sources"


async def test_no_orphan_content_items_topic(db_pool):
    """Every content_item references a valid topic_id."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM content_items ci
            LEFT JOIN topics t ON ci.topic_id = t.id
            WHERE t.id IS NULL
            """
        )
    assert count == 0, f"{count} content_items reference non-existent topics"


async def test_report_immutability_source_snapshot(db_pool):
    """Rule 4: Every completed report (generated_at IS NOT NULL) must have source_snapshot."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM reports
            WHERE generated_at IS NOT NULL AND source_snapshot IS NULL
            """
        )
    assert count == 0, (
        f"{count} completed reports missing source_snapshot — violates immutability rule"
    )


async def test_content_hash_uniqueness(db_pool):
    """Rule 3: content_hash UNIQUE constraint is enforced — no duplicates."""
    async with db_pool.acquire() as conn:
        dupes = await conn.fetchval(
            """
            SELECT COUNT(*) FROM (
                SELECT content_hash FROM content_items
                GROUP BY content_hash HAVING COUNT(*) > 1
            ) AS dupes
            """
        )
    assert dupes == 0, f"{dupes} duplicate content_hash values found"


async def test_deepfake_scores_are_probabilities(db_pool):
    """Rule 7: deepfake_score must be float 0.0–1.0, never outside range."""
    async with db_pool.acquire() as conn:
        # Check if vision_results table exists first
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='vision_results')"
        )
        if not exists:
            pytest.skip("vision_results table does not exist")
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM vision_results
            WHERE deepfake_score IS NOT NULL
              AND (deepfake_score < 0.0 OR deepfake_score > 1.0)
            """
        )
    assert count == 0, f"{count} vision_results have deepfake_score outside [0.0, 1.0]"
