"""Unit tests for orphan sweep dedup check — MED-15.

Orphan sweep must check that content_item still has embedding IS NULL
before re-enqueuing, to avoid double analysis of items already being processed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestOrphanSweepDedupQuery:
    def test_orphan_query_checks_embedding_is_null(self):
        """SQL_ORPHANED_CONTENT must filter on embedding IS NULL."""
        from anveshak.analyst.scheduler import SQL_ORPHANED_CONTENT

        sql = SQL_ORPHANED_CONTENT.lower()
        assert "embedding is null" in sql, "Orphan sweep query must check embedding IS NULL"

    def test_orphan_query_has_time_bound(self):
        """Query must limit to recent items (prevent full table scan)."""
        from anveshak.analyst.scheduler import SQL_ORPHANED_CONTENT

        sql = SQL_ORPHANED_CONTENT.lower()
        assert "interval" in sql or "now()" in sql, "Orphan sweep must have a time-bound filter"

    def test_orphan_query_has_batch_limit(self):
        """Query must have LIMIT to prevent unbounded processing."""
        from anveshak.analyst.scheduler import SQL_ORPHANED_CONTENT

        sql = SQL_ORPHANED_CONTENT.lower()
        assert "limit" in sql, "Orphan sweep must have a LIMIT clause"

    def test_orphan_query_excludes_items_with_pending_job(self):
        """Query must exclude items that already have a pending ARQ job.

        This prevents re-enqueuing items that are currently being analysed
        by the worker (embedding set after analysis completes).
        Use a NOT EXISTS subquery or similar mechanism.
        """
        from anveshak.analyst.scheduler import SQL_ORPHANED_CONTENT

        sql = SQL_ORPHANED_CONTENT.lower()
        # Must have some mechanism to avoid re-enqueuing already-queued items
        # Either: check a 'processing' flag, or exclude recently-enqueued items
        assert (
            "enqueued_at" in sql
            or "processing" in sql
            or "not exists" in sql
            or "last_enqueued" in sql
            or "orphan_enqueued_at" in sql
        ), "Orphan sweep must exclude items already enqueued to prevent double analysis"
