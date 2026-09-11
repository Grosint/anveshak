"""Unit tests for social content ingestion pipeline.

pytest.mark.unit — mocks all DB and ARQ calls, no external dependencies.
Tests real business logic: normalisation, hashing, dedup, source lookup, media dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    stable_id=None,
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
        stable_id=stable_id,
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
# Dedup key tests — ingest defers to RawItem.content_hash()
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self):
        h1 = _make_raw_item(raw_text="UAV spotted near border").content_hash()
        h2 = _make_raw_item(raw_text="UAV spotted near border").content_hash()
        assert h1 == h2

    def test_different_for_different_text(self):
        h1 = _make_raw_item(raw_text="UAV spotted near border").content_hash()
        h2 = _make_raw_item(raw_text="Tank convoy moving south").content_hash()
        assert h1 != h2

    def test_normalises_before_hashing(self):
        """Same text with different whitespace/case -> same hash."""
        h1 = _make_raw_item(raw_text="UAV Spotted  Near Border").content_hash()
        h2 = _make_raw_item(raw_text="uav spotted near border").content_hash()
        assert h1 == h2

    def test_matches_scraper_normalisation(self):
        """Must stay byte-identical to _normalise, which produces clean_text."""
        import hashlib

        from anveshak.social.ingest import _normalise

        raw = _make_raw_item(raw_text="UAV Spotted  Near Border")
        expected = hashlib.sha256(_normalise(raw.raw_text).encode("utf-8")).hexdigest()
        assert raw.content_hash() == expected


class TestStableIdDedup:
    """A RawItem carrying stable_id must be deduped on that, not on its text."""

    @pytest.mark.asyncio
    async def test_insert_uses_raw_item_content_hash(self):
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item(
            raw_text="Video title\n\n[TRANSCRIPT]\nfirst asr pass",
            platform="youtube",
            source_handle="@ch",
            stable_id="video:abc123",
        )
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])
        arq_pool = AsyncMock()

        assert await ingest_raw_item(raw, "topic-1", pool, arq_pool, "youtube-v1") is True

        insert_args = conn.fetchrow.await_args_list[1].args
        assert raw.content_hash() in insert_args

    @pytest.mark.asyncio
    async def test_recaptioned_video_hashes_identically(self):
        """An ASR re-run rewrites the transcript; the dedup key must not move."""
        from anveshak.social.ingest import ingest_raw_item

        hashes = []
        for transcript in ("first asr pass", "second asr pass, more accurate"):
            raw = _make_raw_item(
                raw_text=f"Video title\n\n[TRANSCRIPT]\n{transcript}",
                platform="youtube",
                source_handle="@ch",
                stable_id="video:abc123",
            )
            pool, conn = _mock_pool()
            conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])
            await ingest_raw_item(raw, "topic-1", pool, AsyncMock(), "youtube-v1")
            hashes.append(conn.fetchrow.await_args_list[1].args)

        # The hash is whichever positional arg the two inserts share; assert the
        # key itself rather than an index, so a column reorder does not silently pass.
        assert hashes[0].index(raw.content_hash()) == hashes[1].index(raw.content_hash())


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
        conn.fetchrow = AsyncMock(
            side_effect=[
                _make_source_row(),
                None,  # ON CONFLICT DO NOTHING -> no row returned
            ]
        )
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
        conn.fetchrow = AsyncMock(
            side_effect=[
                _make_source_row(),
                {"id": content_item_id},  # INSERT succeeded
            ]
        )
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is True
        arq_pool.enqueue_job.assert_awaited_once_with(
            "analyse_content",
            content_item_id,
            _queue_name="arq:analyst",
        )

    @pytest.mark.asyncio
    async def test_insert_sql_passes_org_id(self):
        """SQL_INSERT_CONTENT has 17 params — org_id is $16, published_at is $17."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        content_item_id = "ci-org-1"
        conn.fetchrow = AsyncMock(
            side_effect=[
                _make_source_row(),
                {"id": content_item_id},
            ]
        )
        arq_pool = AsyncMock()

        result = await ingest_raw_item(
            raw,
            "topic-1",
            pool,
            arq_pool,
            "reddit-v1",
            org_id="org_cyber",
        )
        assert result is True
        # Verify INSERT call received 17 args (SQL has $1-$17)
        insert_call = conn.fetchrow.call_args_list[1]
        insert_args = insert_call.args
        # First arg is SQL string, rest are positional params
        assert len(insert_args) == 18  # SQL + 17 params
        assert insert_args[16] == "org_cyber"  # $16 = org_id

    @pytest.mark.asyncio
    async def test_insert_sql_passes_none_org_id_by_default(self):
        """When org_id is not provided, $16 is None."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        content_item_id = "ci-org-2"
        conn.fetchrow = AsyncMock(
            side_effect=[
                _make_source_row(),
                {"id": content_item_id},
            ]
        )
        arq_pool = AsyncMock()

        result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")
        assert result is True
        insert_call = conn.fetchrow.call_args_list[1]
        insert_args = insert_call.args
        assert len(insert_args) == 18  # SQL + 17 params
        assert insert_args[16] is None  # $16 = org_id defaults to None
        # $17 = published_at. The fixture RawItem sets none, so it stays NULL
        # rather than inheriting the collection time.
        assert insert_args[17] is None

    @pytest.mark.asyncio
    async def test_enqueues_vision_for_media(self):
        """raw.media_urls not empty -> _download_media_attachments called."""
        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item(media_urls=["https://example.com/image.jpg"])
        pool, conn = _mock_pool()
        content_item_id = "ci-media-1"
        conn.fetchrow = AsyncMock(
            side_effect=[
                _make_source_row(),
                {"id": content_item_id},
            ]
        )
        arq_pool = AsyncMock()

        with patch(
            "anveshak.social.ingest._download_media_attachments", new_callable=AsyncMock
        ) as mock_dl:
            result = await ingest_raw_item(raw, "topic-1", pool, arq_pool, "reddit-v1")

        assert result is True
        mock_dl.assert_awaited_once()
        call_kwargs = mock_dl.call_args[1]
        assert call_kwargs["media_urls"] == ["https://example.com/image.jpg"]
        assert call_kwargs["content_item_id"] == content_item_id


# ---------------------------------------------------------------------------
# Publication Time provenance — issue #45
# ---------------------------------------------------------------------------


class TestPublicationTimeSignalLabel:
    """Where a date came from is answerable from the row it was written on."""

    @pytest.mark.asyncio
    async def test_the_signal_name_is_written_into_labels(self):
        import json

        from anveshak.social.ingest import PUBLICATION_TIME_SIGNAL_LABEL, ingest_raw_item

        raw = _make_raw_item()
        raw.published_at = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
        raw.published_at_signal = "jsonld_date_published"
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])

        await ingest_raw_item(raw, "topic-1", pool, AsyncMock(), "corpus-import-v1")

        insert_args = conn.fetchrow.await_args_list[1].args
        labels = json.loads(next(a for a in insert_args if isinstance(a, str) and "domain" in a))
        assert labels[PUBLICATION_TIME_SIGNAL_LABEL] == "jsonld_date_published"

    @pytest.mark.asyncio
    async def test_no_signal_writes_no_key(self):
        """An absent signal is an absent key, never an empty string."""
        import json

        from anveshak.social.ingest import PUBLICATION_TIME_SIGNAL_LABEL, ingest_raw_item

        raw = _make_raw_item()
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])

        await ingest_raw_item(raw, "topic-1", pool, AsyncMock(), "reddit-v1")

        insert_args = conn.fetchrow.await_args_list[1].args
        labels = json.loads(next(a for a in insert_args if isinstance(a, str) and "domain" in a))
        assert PUBLICATION_TIME_SIGNAL_LABEL not in labels

    def test_the_label_key_matches_the_scraper(self):
        """One key across collected and imported content, or an analyst reads two.

        The two services cannot share a module, so the constant is duplicated
        and this test is what keeps the duplicate honest.
        """
        from anveshak.scraper.publication_time import (
            PUBLICATION_TIME_SIGNAL_LABEL as SCRAPER_LABEL,
        )
        from anveshak.social.ingest import PUBLICATION_TIME_SIGNAL_LABEL as SOCIAL_LABEL

        assert SOCIAL_LABEL == SCRAPER_LABEL


class TestExtraLabels:
    """An item may add provenance to its labels, but not reclassify itself."""

    @pytest.mark.asyncio
    async def test_extra_labels_are_merged(self):
        import json

        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        raw.extra_labels = {"discovery": "archive_sitemap", "body_source": "archive"}
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])

        await ingest_raw_item(raw, "topic-1", pool, AsyncMock(), "corpus-import-v1")

        insert_args = conn.fetchrow.await_args_list[1].args
        labels = json.loads(next(a for a in insert_args if isinstance(a, str) and "domain" in a))
        assert labels["discovery"] == "archive_sitemap"
        assert labels["body_source"] == "archive"

    @pytest.mark.asyncio
    async def test_reserved_keys_are_ignored(self):
        """Classification is the pipeline's to assert, never the item's."""
        import json

        from anveshak.social.ingest import ingest_raw_item

        raw = _make_raw_item()
        raw.extra_labels = {"classification": "OPEN_PUBLIC", "owner_org": "somebody-else"}
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(side_effect=[_make_source_row(), {"id": "ci-1"}])

        await ingest_raw_item(raw, "topic-1", pool, AsyncMock(), "corpus-import-v1")

        insert_args = conn.fetchrow.await_args_list[1].args
        labels = json.loads(next(a for a in insert_args if isinstance(a, str) and "domain" in a))
        assert labels["classification"] == "OPEN"
        assert labels["owner_org"] == "anveshak"
