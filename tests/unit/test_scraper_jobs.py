"""Unit tests for scraper ARQ jobs — scrape_topic and media URL extraction.

pytest.mark.unit — no external dependencies, no DB, no network.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from anveshak.scraper.jobs import _extract_media_urls, scrape_topic


# ---------------------------------------------------------------------------
# _extract_media_urls — pure function tests (no mocks needed)
# ---------------------------------------------------------------------------


class TestExtractMediaUrls:
    """Tests for _extract_media_urls HTML parser."""

    @pytest.mark.unit
    def test_absolute_and_relative(self):
        """Mix of absolute and relative src attributes resolved correctly."""
        html = (
            '<img src="https://cdn.example.com/photo.jpg">'
            '<img src="/images/logo.png">'
            '<img src="assets/pic.webp">'
        )
        urls = _extract_media_urls(html, "https://example.com/page/article")
        assert urls[0] == "https://cdn.example.com/photo.jpg"
        assert urls[1] == "https://example.com/images/logo.png"
        assert urls[2] == "https://example.com/page/assets/pic.webp"
        assert len(urls) == 3

    @pytest.mark.unit
    def test_caps_at_20(self):
        """30 images → only first 20 returned."""
        tags = "".join(f'<img src="/img/{i}.jpg">' for i in range(30))
        urls = _extract_media_urls(tags, "https://example.com")
        assert len(urls) == 20

    @pytest.mark.unit
    def test_skips_data_uris(self):
        """data: scheme URLs not included."""
        html = (
            '<img src="data:image/png;base64,iVBOR...">'
            '<img src="https://example.com/real.jpg">'
        )
        urls = _extract_media_urls(html, "https://example.com")
        assert len(urls) == 1
        assert "real.jpg" in urls[0]

    @pytest.mark.unit
    def test_handles_video_source_tags(self):
        """<video><source src="..."></video> extracted."""
        html = (
            '<video><source src="https://cdn.example.com/clip.mp4" type="video/mp4"></video>'
            '<video src="https://cdn.example.com/intro.webm"></video>'
        )
        urls = _extract_media_urls(html, "https://example.com")
        assert len(urls) == 2
        assert "clip.mp4" in urls[0]
        assert "intro.webm" in urls[1]

    @pytest.mark.unit
    def test_data_src_fallback(self):
        """data-src and data-lazy-src attributes are also extracted."""
        html = '<img data-src="https://example.com/lazy.jpg">'
        urls = _extract_media_urls(html, "https://example.com")
        assert len(urls) == 1
        assert "lazy.jpg" in urls[0]

    @pytest.mark.unit
    def test_empty_html(self):
        urls = _extract_media_urls("", "https://example.com")
        assert urls == []


# ---------------------------------------------------------------------------
# scrape_topic — async job tests (mock DB + fetch)
# ---------------------------------------------------------------------------


def _make_fake_record(mapping: dict):
    """Create a dict-like object that supports record['key'] access."""
    rec = MagicMock()
    rec.__getitem__ = lambda self, key: mapping[key]
    rec.keys = lambda: mapping.keys()
    return rec


def _make_pool_mock(conn: AsyncMock):
    """Create an asyncpg.Pool mock where acquire() returns an async context manager.

    asyncpg's pool.acquire() returns a PoolAcquireContext (async ctx manager),
    NOT a coroutine. The mock must replicate: `async with pool.acquire() as conn`.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


class TestScrapeTopic:
    """Tests for the scrape_topic ARQ job function."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_topic_not_found(self):
        """Topic doesn't exist → returns 0."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}
        result = await scrape_topic(ctx, "nonexistent-topic-id")
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_sources(self):
        """Topic exists but no sources → returns 0."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "topic-1"})
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}
        result = await scrape_topic(ctx, "topic-1")
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_fallback_when_browser_fails(self, mock_crawler, mock_fetch_url):
        """create_shared_crawler raises → falls back to fetch_url."""
        mock_crawler.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Chromium not found")
        )
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch_url.return_value = "Fallback article content for testing purposes."

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com/article",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}  # topic lookup
            # insert returns a row (new insert)
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}
        result = await scrape_topic(ctx, "topic-1")

        # fetch_url was called as fallback
        mock_fetch_url.assert_called_once_with("https://example.com/article")
        assert result == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_dedup_via_content_hash(self, mock_crawler, mock_fetch_url):
        """ON CONFLICT DO NOTHING → counter not incremented on duplicate."""
        mock_crawler.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("force fallback")
        )
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch_url.return_value = "Duplicate article content."

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com/dupe",
            "credibility_score": 0.7,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}  # topic lookup
            # Insert returns None (ON CONFLICT DO NOTHING — duplicate)
            return None

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}
        result = await scrape_topic(ctx, "topic-1")

        # Duplicate → counter stays at 0
        assert result == 0
