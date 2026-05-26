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


class TestLanguageDetection:
    """Tests for scraper language detection (not hardcoded 'en')."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    @patch("anveshak.scraper.jobs.detect_language")
    async def test_language_detected_not_hardcoded(
        self, mock_detect, mock_crawler, mock_fetch_url, mock_robots,
    ):
        """Language should be detected from text, not hardcoded to 'en'."""
        mock_crawler.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("force fallback")
        )
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch_url.return_value = "Ceci est un article en français avec suffisamment de texte."
        mock_detect.return_value = "fr"

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.fr/article",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}

        with patch("anveshak.scraper.jobs.asyncio.sleep", new_callable=AsyncMock), \
             patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_default_delay_s = 0
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = False
            mock_settings.respect_robots_txt = True

            result = await scrape_topic(ctx, "topic-1")

            mock_detect.assert_called_once()
            # Verify the INSERT got "fr" not "en"
            insert_call = mock_conn.fetchrow.call_args_list[1]
            # SQL_INSERT_CONTENT language param is at index 6 (0-based in args)
            insert_args = insert_call[0]
            lang_arg = insert_args[6]  # $7 = language
            assert lang_arg == "fr", f"Expected 'fr', got '{lang_arg}'"


class TestSourcePageNotStored:
    """Change 1: source page should NOT be stored as content when follow_links=True."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_html", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.extract_article_links")
    @patch("anveshak.scraper.jobs.fetch_url_with_crawler", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_source_page_not_inserted_when_follow_links(
        self, mock_crawler, mock_fetch_crawler, mock_extract, mock_fetch_html, mock_robots,
    ):
        """When follow_links=True, _insert_content is only called for article links."""
        # Setup crawler to work normally
        crawler_obj = AsyncMock()
        run_cfg_obj = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=(crawler_obj, run_cfg_obj))
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_crawler.return_value = cm

        # Source page HTML returns one article link
        mock_fetch_html.return_value = "<html><a href='/article1'>Art</a></html>"
        mock_extract.return_value = ["https://example.com/article1"]

        # Article link fetch returns content
        mock_fetch_crawler.return_value = "Real article content about defence operations in the region."

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}  # topic lookup
            return {"id": "content-item-1"}  # article insert

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # URL not seen
        mock_redis.set = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        with patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.scraper_default_delay_s = 0
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = True
            mock_settings.respect_robots_txt = True
            mock_settings.scraper_url_seen_enabled = True
            mock_settings.scraper_url_seen_ttl_s = 86400
            mock_settings.scraper_per_domain_delay_s = 0
            mock_settings.scraper_per_domain_jitter_s = 0

            result = await scrape_topic(ctx, "topic-1")

        # _insert_content called once (for the article link), not for the homepage
        assert result == 1
        # fetch_url_with_crawler called only for the article link, NOT for homepage
        mock_fetch_crawler.assert_called_once()
        call_url = mock_fetch_crawler.call_args[0][0]
        assert call_url == "https://example.com/article1"
        # fetch_html called for the source page (link discovery)
        mock_fetch_html.assert_called_once_with("https://example.com")

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_source_page_stored_when_follow_links_false(
        self, mock_crawler, mock_fetch_url, mock_robots,
    ):
        """When follow_links=False, source URL IS the content (existing behavior)."""
        mock_crawler.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("force fallback")
        )
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_fetch_url.return_value = "Direct article content for testing."

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com/specific-article",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}

        with patch("anveshak.scraper.jobs.asyncio.sleep", new_callable=AsyncMock), \
             patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_default_delay_s = 0
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = False
            mock_settings.respect_robots_txt = True

            result = await scrape_topic(ctx, "topic-1")
            assert result == 1


class TestUrlSeenTracking:
    """Change 4: Redis URL dedup should skip seen URLs."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_html", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.extract_article_links")
    @patch("anveshak.scraper.jobs.fetch_url_with_crawler", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_seen_url_skipped(
        self, mock_crawler, mock_fetch_crawler, mock_extract, mock_fetch_html, mock_robots,
    ):
        """URL already in Redis → not fetched again."""
        crawler_obj = AsyncMock()
        run_cfg_obj = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=(crawler_obj, run_cfg_obj))
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_crawler.return_value = cm

        mock_fetch_html.return_value = "<html><a href='/art1'>A</a></html>"
        mock_extract.return_value = ["https://example.com/art1"]

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[{"id": "topic-1"}])
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"1")  # URL already seen!
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        with patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.scraper_default_delay_s = 0
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = True
            mock_settings.respect_robots_txt = True
            mock_settings.scraper_url_seen_enabled = True
            mock_settings.scraper_url_seen_ttl_s = 86400
            mock_settings.scraper_per_domain_delay_s = 0
            mock_settings.scraper_per_domain_jitter_s = 0

            result = await scrape_topic(ctx, "topic-1")

        # URL was seen → fetch_url_with_crawler never called
        mock_fetch_crawler.assert_not_called()
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_html", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.extract_article_links")
    @patch("anveshak.scraper.jobs.fetch_url_with_crawler", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_new_url_marked_seen_after_fetch(
        self, mock_crawler, mock_fetch_crawler, mock_extract, mock_fetch_html, mock_robots,
    ):
        """New URL → fetched, then marked in Redis with TTL."""
        crawler_obj = AsyncMock()
        run_cfg_obj = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=(crawler_obj, run_cfg_obj))
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_crawler.return_value = cm

        mock_fetch_html.return_value = "<html><a href='/new'>A</a></html>"
        mock_extract.return_value = ["https://example.com/new"]
        mock_fetch_crawler.return_value = "Fresh article about military exercises in the region."

        source = _make_fake_record({
            "id": "src-1",
            "url_or_handle": "https://example.com",
            "credibility_score": 0.8,
        })

        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1"}
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # URL not seen
        mock_redis.set = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        with patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.scraper_default_delay_s = 0
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = True
            mock_settings.respect_robots_txt = True
            mock_settings.scraper_url_seen_enabled = True
            mock_settings.scraper_url_seen_ttl_s = 86400
            mock_settings.scraper_per_domain_delay_s = 0
            mock_settings.scraper_per_domain_jitter_s = 0

            result = await scrape_topic(ctx, "topic-1")

        assert result == 1
        # redis.set was called to mark URL as seen
        mock_redis.set.assert_called_once()
        set_call = mock_redis.set.call_args
        assert set_call[1].get("ex") == 86400 or set_call[0][2] if len(set_call[0]) > 2 else set_call[1].get("ex") == 86400


class TestRateDelay:
    """Tests for per-source rate delay enforcement."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.jobs.check_robots_allowed", new_callable=AsyncMock, return_value=True)
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_delay_called_after_fetch(self, mock_crawler, mock_fetch_url, mock_robots):
        """asyncio.sleep called with scraper_default_delay_s after successful fetch."""
        mock_crawler.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("force fallback")
        )
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_fetch_url.return_value = "Article content sufficient for testing delay."

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
                return {"id": "topic-1"}
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        ctx = {"db_pool": mock_pool, "redis": AsyncMock()}

        with patch("anveshak.scraper.jobs.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("anveshak.scraper.jobs.settings") as mock_settings:
            mock_settings.scraper_default_delay_s = 2.0
            mock_settings.scraper_concurrency = 5
            mock_settings.scraper_request_timeout_s = 30
            mock_settings.media_download_enabled = False
            mock_settings.scraper_follow_links = False
            mock_settings.respect_robots_txt = True

            result = await scrape_topic(ctx, "topic-1")

            mock_sleep.assert_awaited_once_with(2.0)
            assert result == 1
