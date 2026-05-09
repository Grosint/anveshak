"""Unit tests for social polling jobs — per-adapter scheduling and error isolation.

pytest.mark.unit — mocks all DB, ARQ, and adapter calls.
Tests real business logic: X adapter skip logic, error isolation between adapters.
"""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx():
    """Build a fake ARQ context with mocked DB pool and ARQ pool."""
    db_pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    db_pool.acquire.return_value = acm

    arq_pool = AsyncMock()
    return {"db_pool": db_pool, "arq_pool": arq_pool, "redis": arq_pool}, db_pool, conn


def _make_adapter(adapter_id: str, platform: str):
    """Create a mock adapter that yields no items by default."""
    adapter = MagicMock()
    adapter.adapter_id = adapter_id
    adapter.platform = platform

    async def empty_collect(*args, **kwargs):
        return
        yield  # make it an async generator

    adapter.collect = empty_collect
    return adapter


def _make_adapter_yielding(adapter_id: str, platform: str, items: list):
    """Create a mock adapter that yields the given RawItems."""
    adapter = MagicMock()
    adapter.adapter_id = adapter_id
    adapter.platform = platform

    async def yielding_collect(*args, **kwargs):
        for item in items:
            yield item

    adapter.collect = yielding_collect
    return adapter


# ---------------------------------------------------------------------------
# poll_social_topic tests
# ---------------------------------------------------------------------------

class TestPollSocialTopic:

    @pytest.mark.asyncio
    async def test_topic_not_found_returns_early(self):
        """Non-existent topic -> returns {inserted: 0}."""
        ctx, db_pool, conn = _make_ctx()
        conn.fetchrow = AsyncMock(return_value=None)

        from anveshak.social.jobs import poll_social_topic
        result = await poll_social_topic(ctx, "nonexistent-topic")

        assert result == {"inserted": 0}

    @pytest.mark.asyncio
    async def test_x_adapter_skipped_when_include_x_false(self):
        """include_x=False -> X/Twitter adapter is skipped."""
        from anveshak.social.adapters.base import AdapterRateLimitError

        ctx, db_pool, conn = _make_ctx()
        conn.fetchrow = AsyncMock(return_value={"id": "topic-1", "keywords": ["test"]})
        conn.fetch = AsyncMock(return_value=[])  # no sources

        twitter_adapter = _make_adapter("x-v1", "twitter")
        reddit_adapter = _make_adapter("reddit-v1", "reddit")

        with patch.dict("anveshak.social.jobs._ADAPTERS", {
            "x-v1": twitter_adapter,
            "reddit-v1": reddit_adapter,
        }, clear=True):
            from anveshak.social.jobs import poll_social_topic
            result = await poll_social_topic(ctx, "topic-1", include_x=False)

        # Twitter platform should not appear in results (skipped)
        inserted = result.get("inserted_by_platform", {})
        assert "twitter" not in inserted
        # Reddit should still be present
        assert "reddit" in inserted

    @pytest.mark.asyncio
    async def test_adapter_error_does_not_crash_others(self):
        """One adapter raising an exception doesn't prevent others from running."""
        from anveshak.social.adapters.base import RawItem

        ctx, db_pool, conn = _make_ctx()
        conn.fetchrow = AsyncMock(return_value={"id": "topic-1", "keywords": ["test"]})
        conn.fetch = AsyncMock(return_value=[{"id": "s1", "url_or_handle": "handle1", "credibility_score": 80.0}])

        # Reddit adapter raises
        broken_adapter = MagicMock()
        broken_adapter.adapter_id = "reddit-v1"
        broken_adapter.platform = "reddit"

        async def failing_collect(*args, **kwargs):
            raise RuntimeError("Network timeout")
            yield  # noqa: unreachable

        broken_adapter.collect = failing_collect

        # Bluesky adapter works fine
        working_adapter = _make_adapter("bluesky-v1", "bluesky")

        with patch.dict("anveshak.social.jobs._ADAPTERS", {
            "reddit-v1": broken_adapter,
            "bluesky-v1": working_adapter,
        }, clear=True):
            from anveshak.social.jobs import poll_social_topic
            result = await poll_social_topic(ctx, "topic-1")

        # Both platforms should be in results — one with 0, the other also 0 but not crashed
        inserted = result.get("inserted_by_platform", {})
        assert "reddit" in inserted
        assert "bluesky" in inserted
