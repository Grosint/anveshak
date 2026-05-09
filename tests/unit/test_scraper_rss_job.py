"""Unit tests for poll_rss_sources ARQ job.

Bugs caught:
  1. Missing topic → must return 0 immediately (not crash)
  2. No RSS sources for topic → must return 0 (not crash on empty gather)
  3. ON CONFLICT dedup: second identical item returns None from fetchrow → counter stays at 1
  4. Exception on one item must not block remaining items (per-item try/except)

pytest.mark.unit — no DB, no Redis, no network.
"""
import pytest
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


def _make_pool_and_conn():
    """Build the canonical pool + conn mock."""
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm
    return pool, conn


def _rss_item(raw_text: str, url: str, title: str = "Test", published_at=None):
    """Simulate an RSS item returned by fetch_rss_items."""
    return SimpleNamespace(
        raw_text=raw_text,
        url=url,
        title=title,
        published_at=published_at or datetime.now(UTC),
    )


def _source_row(source_id: str, url: str, credibility: float = 50.0):
    return {
        "id": source_id,
        "url_or_handle": url,
        "credibility_score": credibility,
    }


# ---------------------------------------------------------------------------
# poll_rss_sources
# ---------------------------------------------------------------------------


class TestPollRssSources:

    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.fetch_rss_items", new_callable=AsyncMock)
    async def test_topic_not_found(self, mock_fetch_rss):
        """conn.fetchrow(SQL_GET_TOPIC) returns None → returns 0."""
        from anveshak.scraper.jobs import poll_rss_sources

        pool, conn = _make_pool_and_conn()
        conn.fetchrow.return_value = None  # topic not found
        ctx = {"db_pool": pool, "redis": MagicMock()}

        result = await poll_rss_sources(ctx, "nonexistent-topic")

        assert result == 0
        mock_fetch_rss.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.fetch_rss_items", new_callable=AsyncMock)
    async def test_no_sources(self, mock_fetch_rss):
        """Topic exists, but no RSS sources → returns 0."""
        from anveshak.scraper.jobs import poll_rss_sources

        pool, conn = _make_pool_and_conn()
        conn.fetchrow.return_value = {"id": "topic-1"}  # topic exists
        conn.fetch.return_value = []  # no RSS sources
        ctx = {"db_pool": pool, "redis": MagicMock()}

        result = await poll_rss_sources(ctx, "topic-1")

        assert result == 0
        mock_fetch_rss.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.scraper_items_fetched_total")
    @patch("anveshak.scraper.jobs.extract_title", return_value="Title")
    @patch("anveshak.scraper.jobs.score_content_quality", return_value=0.8)
    @patch("anveshak.scraper.jobs.compute_clean_hash", return_value="cleanhash1")
    @patch("anveshak.scraper.jobs.clean_extracted_text", return_value="cleaned text")
    @patch("anveshak.scraper.jobs.compute_content_hash")
    @patch("anveshak.scraper.jobs.fetch_rss_items", new_callable=AsyncMock)
    async def test_dedup_via_on_conflict(
        self, mock_fetch_rss, mock_hash, mock_clean, mock_clean_hash,
        mock_quality, mock_title, mock_metric
    ):
        """Two items with same content_hash — second insert returns None (ON CONFLICT) → counter=1."""
        from anveshak.scraper.jobs import poll_rss_sources

        # Both items produce the same content_hash
        mock_hash.return_value = "same-hash"
        mock_fetch_rss.return_value = [
            _rss_item("duplicate text", "https://a.com/1"),
            _rss_item("duplicate text", "https://a.com/2"),
        ]

        # First call setup: topic lookup + sources lookup on the outer conn
        outer_pool, outer_conn = _make_pool_and_conn()
        outer_conn.fetchrow.return_value = {"id": "topic-1"}
        outer_conn.fetch.return_value = [_source_row("s1", "https://feed.com/rss")]

        # Inner conn for per-item inserts: first returns a row (inserted), second returns None (dedup)
        inner_conn = AsyncMock()
        inner_conn.fetchrow.side_effect = [{"id": "new-id"}, None]

        inner_acm = MagicMock()
        inner_acm.__aenter__ = AsyncMock(return_value=inner_conn)
        inner_acm.__aexit__ = AsyncMock(return_value=False)

        # pool.acquire returns outer_conn first (for topic+sources), then inner_conn for each item
        call_count = 0
        outer_acm = MagicMock()
        outer_acm.__aenter__ = AsyncMock(return_value=outer_conn)
        outer_acm.__aexit__ = AsyncMock(return_value=False)

        def acquire_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return outer_acm
            return inner_acm

        outer_pool.acquire.side_effect = acquire_side_effect

        ctx = {"db_pool": outer_pool, "redis": MagicMock()}
        result = await poll_rss_sources(ctx, "topic-1")

        assert result == 1  # only 1 inserted, second was dedup'd

    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.scraper_items_fetched_total")
    @patch("anveshak.scraper.jobs.scraper_fetch_errors_total")
    @patch("anveshak.scraper.jobs.extract_title", return_value="Title")
    @patch("anveshak.scraper.jobs.score_content_quality", return_value=0.8)
    @patch("anveshak.scraper.jobs.compute_clean_hash", return_value="cleanhash")
    @patch("anveshak.scraper.jobs.clean_extracted_text")
    @patch("anveshak.scraper.jobs.compute_content_hash", return_value="hash1")
    @patch("anveshak.scraper.jobs.fetch_rss_items", new_callable=AsyncMock)
    async def test_item_error_continues(
        self, mock_fetch_rss, mock_hash, mock_clean, mock_clean_hash,
        mock_quality, mock_title, mock_errors_metric, mock_items_metric
    ):
        """Item 2 raises during clean → items 1 and 3 still inserted."""
        from anveshak.scraper.jobs import poll_rss_sources

        mock_fetch_rss.return_value = [
            _rss_item("good text one", "https://a.com/1"),
            _rss_item("bad text", "https://a.com/2"),
            _rss_item("good text three", "https://a.com/3"),
        ]

        # clean_extracted_text raises on the second call
        mock_clean.side_effect = [
            "cleaned one",
            ValueError("Encoding error in content"),
            "cleaned three",
        ]

        # Outer conn for topic + sources
        outer_pool, outer_conn = _make_pool_and_conn()
        outer_conn.fetchrow.return_value = {"id": "topic-1"}
        outer_conn.fetch.return_value = [_source_row("s1", "https://feed.com/rss")]

        # Inner conn for per-item inserts — returns a row each time (successful insert)
        inner_conn = AsyncMock()
        inner_conn.fetchrow.return_value = {"id": "new-id"}

        inner_acm = MagicMock()
        inner_acm.__aenter__ = AsyncMock(return_value=inner_conn)
        inner_acm.__aexit__ = AsyncMock(return_value=False)

        call_count = 0
        outer_acm = MagicMock()
        outer_acm.__aenter__ = AsyncMock(return_value=outer_conn)
        outer_acm.__aexit__ = AsyncMock(return_value=False)

        def acquire_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return outer_acm
            return inner_acm

        outer_pool.acquire.side_effect = acquire_side_effect

        ctx = {"db_pool": outer_pool, "redis": MagicMock()}
        result = await poll_rss_sources(ctx, "topic-1")

        # Items 1 and 3 inserted, item 2 failed → count = 2
        assert result == 2
