"""Unit tests for content archive + retention sweep (Priority 4).

Tests verify the archive-then-delete logic without a real database.
All DB calls are mocked; archive writes use a temp directory.

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import gzip
import json
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test 1: Disabled when CONTENT_RETENTION_DAYS=0
# ---------------------------------------------------------------------------

class TestRetentionDisabled:

    @pytest.mark.asyncio
    async def test_retention_disabled_when_zero(self):
        """When content_retention_days=0, no archive or delete should happen."""
        from anveshak.analyst.scheduler import archive_and_delete_expired

        pool = AsyncMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=conn)

        with patch("anveshak.analyst.scheduler.settings") as mock_settings:
            mock_settings.content_retention_days = 0
            result = await archive_and_delete_expired(pool)

        assert result["skipped"] == "retention_disabled"
        conn.fetch.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Only clustered items archived
# ---------------------------------------------------------------------------

class TestOnlyClusteredItems:

    @pytest.mark.asyncio
    async def test_sql_filters_clustered_only(self):
        """SQL_EXPIRED_CONTENT_ITEMS must require narrative_cluster_id IS NOT NULL."""
        from anveshak.analyst.scheduler import SQL_EXPIRED_CONTENT_ITEMS

        sql = SQL_EXPIRED_CONTENT_ITEMS.lower()
        assert "narrative_cluster_id is not null" in sql, (
            "SQL must filter for clustered items only — unclustered items must survive"
        )


# ---------------------------------------------------------------------------
# Test 3: Archive writes valid JSONL.gz
# ---------------------------------------------------------------------------

class TestArchiveFormat:

    def test_archive_writes_jsonl_gz(self):
        """Archive must write valid gzipped JSONL with content + entities."""
        from anveshak.analyst.scheduler import write_archive_batch

        items = [
            {
                "id": "item-1", "topic_id": "topic-a", "month": "2026-04",
                "raw_text": "PLA bridge at Pangong", "clean_text": "PLA bridge at Pangong",
                "url": "https://example.com/1", "captured_at": datetime(2026, 4, 15, tzinfo=UTC),
                "content_hash": "abc123", "labels": '{"sentiment": {"compound": 0.5}}',
                "entities": json.dumps([{"entity_type": "ORG", "entity_text": "PLA", "confidence": 0.95}]),
            },
            {
                "id": "item-2", "topic_id": "topic-a", "month": "2026-04",
                "raw_text": "NDTV reports on LAC", "clean_text": "NDTV reports on LAC",
                "url": "https://example.com/2", "captured_at": datetime(2026, 4, 16, tzinfo=UTC),
                "content_hash": "def456", "labels": '{}',
                "entities": json.dumps([]),
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_archive_batch("topic-a", "2026-04", items, tmpdir)

            # File exists and is gzipped
            assert Path(path).exists()
            assert path.endswith(".jsonl.gz")

            # Read and verify content
            with gzip.open(path, "rt") as f:
                lines = f.readlines()

            assert len(lines) == 2
            obj = json.loads(lines[0])
            assert obj["id"] == "item-1"
            assert obj["raw_text"] == "PLA bridge at Pangong"
            assert obj["entities"][0]["entity_text"] == "PLA"


# ---------------------------------------------------------------------------
# Test 4: Archive then delete — delete only after successful write
# ---------------------------------------------------------------------------

class TestArchiveThenDelete:

    @pytest.mark.asyncio
    async def test_delete_after_successful_archive(self):
        """Items must be deleted from DB only after archive write succeeds."""
        from anveshak.analyst.scheduler import archive_and_delete_expired

        expired_rows = [
            {"id": "item-1", "topic_id": "topic-a", "month": "2026-04"},
            {"id": "item-2", "topic_id": "topic-a", "month": "2026-04"},
        ]
        archive_data = [
            {
                "id": "item-1", "topic_id": "topic-a", "month": "2026-04",
                "raw_text": "text1", "clean_text": "text1", "url": "https://x.com/1",
                "captured_at": datetime(2026, 4, 15, tzinfo=UTC),
                "content_hash": "h1", "labels": "{}",
                "entities": "[]",
            },
            {
                "id": "item-2", "topic_id": "topic-a", "month": "2026-04",
                "raw_text": "text2", "clean_text": "text2", "url": "https://x.com/2",
                "captured_at": datetime(2026, 4, 16, tzinfo=UTC),
                "content_hash": "h2", "labels": "{}",
                "entities": "[]",
            },
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=[expired_rows, archive_data])
        conn.execute = AsyncMock(return_value="DELETE 2")
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("anveshak.analyst.scheduler.settings") as mock_settings:
                mock_settings.content_retention_days = 30
                mock_settings.content_archive_root = tmpdir
                result = await archive_and_delete_expired(pool)

        assert result["archived"] == 2
        assert result["deleted"] == 2

    @pytest.mark.asyncio
    async def test_archive_failure_skips_delete(self):
        """If archive write fails, items must NOT be deleted from DB."""
        from anveshak.analyst.scheduler import archive_and_delete_expired

        expired_rows = [
            {"id": "item-1", "topic_id": "topic-a", "month": "2026-04"},
        ]
        archive_data = [
            {
                "id": "item-1", "topic_id": "topic-a", "month": "2026-04",
                "raw_text": "text", "clean_text": "text", "url": "https://x.com/1",
                "captured_at": datetime(2026, 4, 15, tzinfo=UTC),
                "content_hash": "h1", "labels": "{}",
                "entities": "[]",
            },
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=[expired_rows, archive_data])
        conn.execute = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        with patch("anveshak.analyst.scheduler.settings") as mock_settings:
            mock_settings.content_retention_days = 30
            mock_settings.content_archive_root = "/nonexistent/path/that/will/fail"

            result = await archive_and_delete_expired(pool)

        assert result.get("deleted", 0) == 0
        assert result.get("errors", 0) > 0


# ---------------------------------------------------------------------------
# Test 5: Batch limit
# ---------------------------------------------------------------------------

class TestBatchLimit:

    @pytest.mark.asyncio
    async def test_sql_has_batch_limit(self):
        """SQL_EXPIRED_CONTENT_ITEMS must have LIMIT to avoid unbounded deletes."""
        from anveshak.analyst.scheduler import SQL_EXPIRED_CONTENT_ITEMS

        sql = SQL_EXPIRED_CONTENT_ITEMS.lower()
        assert "limit" in sql, "SQL must have LIMIT to batch deletes"
