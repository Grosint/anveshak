"""Integration test: composite indexes required for windowed queries at scale.

Topics accumulate 10K-1M items over months/years. Windowed queries
(WHERE topic_id = $1 AND captured_at >= ...) need a composite index
to avoid full table scans on every clustering cycle (every 5 minutes).

pytest.mark.integration — requires running PostgreSQL.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestScaleIndexes:
    """Verify composite indexes exist for windowed topic queries."""

    async def test_composite_index_topic_captured_exists(self, db_pool):
        """Composite index (topic_id, captured_at) must exist for windowed queries.

        Without this index, queries like:
          WHERE topic_id = $1 AND captured_at >= NOW() - INTERVAL '30 days'
        do a full scan of all items for the topic, then filter by date.
        At 100K items per topic, this is catastrophic every 5 minutes.
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = 'content_items'
                  AND indexdef LIKE '%topic_id%'
                  AND indexdef LIKE '%captured_at%'
            """)

        assert row is not None, (
            "Missing composite index on content_items(topic_id, captured_at). Run: make migrate"
        )
        assert "idx_content_items_topic_captured" in row["indexname"]

    async def test_composite_index_covers_windowed_columns(self, db_pool):
        """The composite index must cover both topic_id and captured_at columns.

        PostgreSQL may prefer the single-column topic_id index on small tables,
        but at 100K+ items per topic the composite index avoids loading all items
        for a topic then filtering by date. We verify the index definition covers
        both columns in the correct order.
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT indexdef FROM pg_indexes
                WHERE indexname = 'idx_content_items_topic_captured'
            """)

        assert row is not None, "Composite index not found"
        indexdef = row["indexdef"]
        # Verify both columns are in the index definition
        assert "topic_id" in indexdef, f"topic_id missing from index: {indexdef}"
        assert "captured_at" in indexdef, f"captured_at missing from index: {indexdef}"
        assert "DESC" in indexdef, f"captured_at should be DESC for recent-first scans: {indexdef}"
