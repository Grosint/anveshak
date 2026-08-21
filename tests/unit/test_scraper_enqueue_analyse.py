"""Unit tests for scraper → analyse_content enqueue.

The scraper MUST enqueue analyse_content for every new content item it inserts.
Previously it relied entirely on the analyst orphan sweep (1h window, 100 batch)
which couldn't keep up with volume, leaving items permanently without embeddings.

Three insert paths must all enqueue:
  1. scrape_topic  → web crawl   → _insert_content()
  2. poll_rss_sources → RSS feed → inline insert
  3. scrape_darkweb_topic → Tor  → _insert_darkweb_content()

pytest.mark.unit — no external dependencies, no DB, no network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# asyncio_mode = "auto" in pyproject.toml already marks the async tests here.
# An explicit asyncio mark also lands on the sync ones and emits a PytestWarning.
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_record(mapping: dict):
    """Create a dict-like object that supports record['key'] access."""
    rec = MagicMock()
    rec.__getitem__ = lambda self, key: mapping[key]
    rec.keys = lambda: mapping.keys()
    return rec


def _make_pool_mock(conn: AsyncMock):
    """asyncpg.Pool mock where acquire() returns async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


def _make_source(source_id="src-1", url="https://example.com/article", cred=80.0):
    return _make_fake_record(
        {
            "id": source_id,
            "url_or_handle": url,
            "credibility_score": cred,
        }
    )


# ---------------------------------------------------------------------------
# scrape_topic → _insert_content must enqueue analyse_content
# ---------------------------------------------------------------------------


class TestScrapeTopicEnqueuesAnalyse:
    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_enqueues_analyse_content_on_new_insert(
        self,
        mock_crawler,
        mock_fetch_url,
    ):
        """scrape_topic must call redis.enqueue_job('analyse_content', id)
        for every newly inserted content item."""
        from anveshak.scraper.jobs import scrape_topic

        mock_crawler.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("no browser"))
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_fetch_url.return_value = "Article content long enough to process in the pipeline."

        source = _make_source()
        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1", "org_id": "org-1"}  # topic lookup
            return {"id": "content-item-1"}  # insert result

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        await scrape_topic(ctx, "topic-1")

        # Assert analyse_content was enqueued with the content_item_id
        mock_redis.enqueue_job.assert_any_call(
            "analyse_content",
            "content-item-1",
            _queue_name="arq:analyst",
        )

    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_does_not_enqueue_on_dedup_hit(
        self,
        mock_crawler,
        mock_fetch_url,
    ):
        """When ON CONFLICT DO NOTHING fires (dedup), no enqueue should happen."""
        from anveshak.scraper.jobs import scrape_topic

        mock_crawler.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("no browser"))
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_fetch_url.return_value = "Duplicate content already in DB."

        source = _make_source()
        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1", "org_id": "org-1"}
            return None  # dedup — ON CONFLICT DO NOTHING returns None

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        await scrape_topic(ctx, "topic-1")

        # analyse_content should NOT have been enqueued
        for call in mock_redis.enqueue_job.call_args_list:
            assert call[0][0] != "analyse_content", (
                "analyse_content enqueued on dedup hit — should be skipped"
            )

    @patch("anveshak.scraper.jobs.fetch_url", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_enqueue_failure_does_not_crash_scraper(
        self,
        mock_crawler,
        mock_fetch_url,
    ):
        """If enqueue_job raises, the scraper should not crash — log and continue."""
        from anveshak.scraper.jobs import scrape_topic

        mock_crawler.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("no browser"))
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_fetch_url.return_value = "Content that triggers an enqueue failure scenario."

        source = _make_source()
        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1", "org_id": "org-1"}
            return {"id": "content-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(side_effect=ConnectionError("Redis down"))
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        # Should not raise — scraper must be resilient to Redis failures
        result = await scrape_topic(ctx, "topic-1")
        assert result == 1  # insert still counted


# ---------------------------------------------------------------------------
# poll_rss_sources must enqueue analyse_content
# ---------------------------------------------------------------------------


class TestRSSEnqueuesAnalyse:
    @patch("anveshak.scraper.jobs.fetch_rss_items", new_callable=AsyncMock)
    async def test_enqueues_analyse_content_for_rss_item(self, mock_fetch_rss):
        """poll_rss_sources must enqueue analyse_content for each new RSS item."""
        from anveshak.scraper.jobs import poll_rss_sources

        rss_item = MagicMock()
        rss_item.raw_text = "RSS article content that is long enough to be real."
        rss_item.url = "https://feeds.example.com/article-1"
        rss_item.title = "Test Article"
        rss_item.published_at = None
        mock_fetch_rss.return_value = [rss_item]

        source = _make_source(url="https://feeds.example.com/rss")
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": "topic-1", "org_id": "org-1"},  # topic lookup
                {"id": "rss-item-1"},  # insert result
            ]
        )
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        await poll_rss_sources(ctx, "topic-1")

        mock_redis.enqueue_job.assert_any_call(
            "analyse_content",
            "rss-item-1",
            _queue_name="arq:analyst",
        )


# ---------------------------------------------------------------------------
# scrape_darkweb_topic must enqueue analyse_content
# ---------------------------------------------------------------------------


class TestDarkwebEnqueuesAnalyse:
    @patch("anveshak.scraper.jobs.fetch_url_via_tor", new_callable=AsyncMock)
    @patch("anveshak.scraper.jobs.create_shared_crawler")
    async def test_enqueues_analyse_content_for_darkweb_item(
        self,
        mock_crawler,
        mock_fetch_tor,
    ):
        """scrape_darkweb_topic must enqueue analyse_content for each new item."""
        from anveshak.scraper.jobs import scrape_darkweb_topic

        mock_crawler.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_crawler.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_fetch_tor.return_value = "Dark web content extracted from onion site."

        source = _make_source(url="http://example.onion/page")
        mock_conn = AsyncMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"id": "topic-1", "org_id": "org-1"}
            return {"id": "dw-item-1"}

        mock_conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        mock_conn.fetch = AsyncMock(return_value=[source])

        mock_pool = _make_pool_mock(mock_conn)
        mock_redis = AsyncMock()
        ctx = {"db_pool": mock_pool, "redis": mock_redis}

        await scrape_darkweb_topic(ctx, "topic-1")

        mock_redis.enqueue_job.assert_any_call(
            "analyse_content",
            "dw-item-1",
            _queue_name="arq:analyst",
        )
