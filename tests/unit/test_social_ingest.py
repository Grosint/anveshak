"""Unit tests for social content ingestion pipeline.

pytest.mark.unit — mocks all DB and ARQ calls, no external dependencies.
Tests real business logic: normalisation, hashing, dedup, source lookup, media dispatch.
"""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_item(
    raw_text="UAV spotted near border checkpoint",
    url="https://reddit.com/r/test/1",
    platform="reddit",
    source_handle="r/test",
    media_urls=None,
    language=None,
):
    from anveshak.social.adapters.base import RawItem

    return RawItem(
        raw_text=raw_text,
        url=url,
        platform=platform,
        captured_at=datetime.now(UTC),
        source_handle=source_handle,
        media_urls=media_urls or [],
        language=language,
    )


def _make_source_row(source_id="src-1", credibility_score=75.0):
    return {"id": source_id, "credibility_score": credibility_score}


def _mock_pool():
    """Create a mock asyncpg pool with acquire() async context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm
    return pool, conn


# ---------------------------------------------------------------------------
# _normalise tests
# ---------------------------------------------------------------------------

class TestNormalise:

    def test_lowercases_and_collapses_whitespace(self):
        from anveshak.social.ingest import _normalise

        result = _normalise("  Hello   World  ")
        assert result == "hello world"

    def test_strips_leading_trailing(self):
        from anveshak.social.ingest import _normalise

        result = _normalise("\n\t  Test  \n")
        assert result == "test"

    def test_empty_string(self):
        from anveshak.social.ingest import _normalise

        result = _normalise("   ")
        assert result == ""


# ---------------------------------------------------------------------------
# _compute_hash tests
# ---------------------------------------------------------------------------

class TestComputeHash:

    def test_deterministic(self):
        from anveshak.social.ingest import _compute_hash

        h1 = _compute_hash("UAV spotted near border")
        h2 = _compute_hash("UAV spotted near border")
        assert h1 == h2

    def test_different_for_different_text(self):
        from anveshak.social.ingest import _compute_hash

        h1 = _compute_hash("UAV spotted near border")
        h2 = _compute_hash("Tank convoy moving south")
        assert h1 != h2

    def test_normalises_before_hashing(self):
        """Same text with different whitespace/case -> same hash."""
        from anveshak.social.ingest import _compute_hash

        h1 = _compute_hash("UAV Spotted  Near Border")
        h2 = _compute_hash("uav spotted near border")
        assert h1 == h2


# ---------------------------------------------------------------------------
# ingest_raw_item tests
# ---------------------------------------------------------------------------

class TestIngestRawItem:

    @pytest.mark.asyncio
    async def test_empty_text_returns_false(self):
        """raw_text of only whitespace -> False."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item(raw_text="   \n\t   ")
        pool, conn = _mock_pool()
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_source_returns_false(self):
        """Source lookup returns None -> False."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=None)  # source not found
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is False

    @pytest.mark.asyncio
    async def test_dedup_returns_false(self):
        """ON CONFLICT -> fetchrow returns None for insert -> False."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        # First fetchrow: source lookup succeeds
        # Second fetchrow: INSERT returns None (dedup hit)
        conn.fetchrow = AsyncMock(side_effect=[
            _make_source_row(),
            None,  # ON CONFLICT DO NOTHING -> no row returned
        ])
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is False
        # analyse_content should NOT be enqueued on dedup
        arq_pool.enqueue_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_item_returns_true(self):
        """New item inserted -> True, analyse_content enqueued."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        content_item_id = "ci-new-1"
        # First fetchrow: source lookup
        # Second fetchrow: INSERT returns the new row
        conn.fetchrow = AsyncMock(side_effect=[
            _make_source_row(),
            {"id": content_item_id},  # INSERT succeeded
        ])
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is True
        arq_pool.enqueue_job.assert_awaited_once_with(
            "analyse_content", content_item_id, _queue_name="arq:analyst",
        )

    @pytest.mark.asyncio
    async def test_insert_sql_passes_org_id(self):
        """SQL_INSERT_CONTENT has 16 params — org_id must be passed as $16."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        content_item_id = "ci-org-1"
        conn.fetchrow = AsyncMock(side_effect=[
            _make_source_row(),
            {"id": content_item_id},
        ])
        arq_pool = AsyncMock()

        result = await ingest_raw_item(
            raw, "topic-1", pool, arq_pool, "reddit-v1", org_id="org_cyber",
        )
        assert result is True
        # Verify INSERT call received 16 args (SQL has $1-$16)
        insert_call = conn.fetchrow.call_args_list[1]
        insert_args = insert_call.args
        # First arg is SQL string, rest are positional params
        assert len(insert_args) == 17  # SQL + 16 params
        assert insert_args[16] == "org_cyber"  # $16 = org_id

    @pytest.mark.asyncio
    async def test_insert_sql_passes_none_org_id_by_default(self):
        """When org_id not provided, $16 should be None."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        content_item_id = "ci-org-2"
        conn.fetchrow = AsyncMock(side_effect=[
            _make_source_row(),
            {"id": content_item_id},
        ])
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is True
        insert_call = conn.fetchrow.call_args_list[1]
        insert_args = insert_call.args
        assert len(insert_args) == 17  # SQL + 16 params
        assert insert_args[16] is None  # $16 = org_id defaults to None

    @pytest.mark.asyncio
    async def test_enqueues_vision_for_media(self):
        """raw.media_urls not empty -> _download_media_attachments called."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item(media_urls=["https://example.com/image.jpg"])
        pool, conn = _mock_pool()
        content_item_id = "ci-media-1"
        conn.fetchrow = AsyncMock(side_effect=[
            _make_source_row(),
            {"id": content_item_id},
        ])
        arq_pool = AsyncMock()

        with patch("anveshak.social.ingest._download_media_attachments", new_callable=AsyncMock) as mock_dl:
            result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")

        assert result is True
        mock_dl.assert_awaited_once()
        call_kwargs = mock_dl.call_args[1]
        assert call_kwargs["media_urls"] == ["https://example.com/image.jpg"]
        assert call_kwargs["content_item_id"] == content_item_id
