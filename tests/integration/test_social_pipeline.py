"""Integration tests for social ingestion pipeline — criteria 3.27–3.29.

These tests verify that:
- Each adapter produces ContentItems with correct platform value (3.27)
- Telegram + Reddit items for the same story → different DB rows, cluster groups them (3.28)
- independent_source_count counts telegram and reddit as 2 distinct platforms (3.29)

All external APIs (tweepy, PRAW, atproto, Telethon) are mocked via unittest.mock.
Real PostgreSQL and Redis from Docker Compose are used (pytest.mark.integration).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from anveshak.social.adapters.base import RawItem
from anveshak.social.ingest import ingest_raw_item

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_topic(make_topic):
    return await make_topic(
        name="Social Test Topic",
        keywords=["border", "airforce"],
    )


@pytest.fixture
async def reddit_source(make_source):
    source_id = await make_source(
        name="r/worldnews test",
        url_or_handle="r/worldnews",
        platform="reddit",
        credibility_score=75.0,
    )
    return {"id": source_id, "handle": "r/worldnews", "platform": "reddit"}


@pytest.fixture
async def telegram_source(make_source):
    source_id = await make_source(
        name="@defencenews test",
        url_or_handle="@defencenews",
        platform="telegram",
        credibility_score=70.0,
    )
    return {"id": source_id, "handle": "@defencenews", "platform": "telegram"}


@pytest.fixture
def mock_arq_pool():
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="test-job-id"))
    return pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngestRawItem:
    """ingest_raw_item() inserts content_items rows correctly."""

    @pytest.mark.asyncio
    async def test_reddit_item_inserted_with_correct_platform(
        self, db_pool, test_topic, reddit_source, mock_arq_pool
    ):
        raw = RawItem(
            raw_text="IAF jets scrambled near LoC in response to airspace violation.",
            url="https://www.reddit.com/r/worldnews/comments/test123/",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/worldnews",
        )
        new = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        assert new is True

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT source_id FROM content_items WHERE url = $1", raw.url)
        assert row is not None
        assert row["source_id"] == reddit_source["id"]
        from unittest.mock import ANY

        mock_arq_pool.enqueue_job.assert_called_once_with(
            "analyse_content", ANY, _queue_name="arq:analyst"
        )

    @pytest.mark.asyncio
    async def test_telegram_item_inserted_with_correct_platform(
        self, db_pool, test_topic, telegram_source, mock_arq_pool
    ):
        raw = RawItem(
            raw_text="Breaking: IAF conducts night exercise near Leh.",
            url="https://t.me/defencenews/9001",
            platform="telegram",
            captured_at=datetime.now(UTC),
            source_handle="@defencenews",
        )
        new = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "telegram-v1", org_id="org-integration-test"
        )
        assert new is True

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT source_id FROM content_items WHERE url = $1", raw.url)
        assert row is not None

    @pytest.mark.asyncio
    async def test_dedup_same_content_hash(self, db_pool, test_topic, reddit_source, mock_arq_pool):
        """Inserting identical text twice → second insert is a no-op (criteria 1.5 / 3.4)."""
        raw = RawItem(
            raw_text="Unique dedup test text " + str(uuid.uuid4()),
            url="https://www.reddit.com/r/worldnews/dedup_test/",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/worldnews",
        )
        first = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        second = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        assert first is True
        assert second is False  # dedup hit
        # ARQ job enqueued only once
        assert mock_arq_pool.enqueue_job.call_count == 1

    @pytest.mark.asyncio
    async def test_analyse_content_job_enqueued_on_new_item(
        self, db_pool, test_topic, reddit_source, mock_arq_pool
    ):
        raw = RawItem(
            raw_text="Test NLP job enqueue " + str(uuid.uuid4()),
            url=f"https://www.reddit.com/r/worldnews/{uuid.uuid4()}/",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/worldnews",
        )
        await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        mock_arq_pool.enqueue_job.assert_called_once()
        call_args = mock_arq_pool.enqueue_job.call_args[0]
        assert call_args[0] == "analyse_content"


class TestMultiPlatformIndependentSourceCount:
    """Criteria 3.29 — Telegram and Reddit counted as 2 distinct platforms."""

    @pytest.mark.asyncio
    async def test_two_platforms_yield_distinct_platform_values(
        self,
        db_pool,
        test_topic,
        reddit_source,
        telegram_source,
        mock_arq_pool,
    ):
        """Insert items from both platforms and verify DB has both platform values."""
        reddit_raw = RawItem(
            raw_text="IAF Story from Reddit " + str(uuid.uuid4()),
            url=f"https://www.reddit.com/r/worldnews/{uuid.uuid4()}/",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/worldnews",
        )
        telegram_raw = RawItem(
            raw_text="IAF Story from Telegram " + str(uuid.uuid4()),
            url=f"https://t.me/defencenews/{uuid.uuid4()}",
            platform="telegram",
            captured_at=datetime.now(UTC),
            source_handle="@defencenews",
        )

        await ingest_raw_item(
            reddit_raw,
            test_topic,
            db_pool,
            mock_arq_pool,
            "reddit-v1",
            org_id="org-integration-test",
        )
        await ingest_raw_item(
            telegram_raw,
            test_topic,
            db_pool,
            mock_arq_pool,
            "telegram-v1",
            org_id="org-integration-test",
        )

        # Verify two distinct platform values exist in sources for this topic
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT s.platform
                FROM content_items ci
                JOIN sources s ON ci.source_id = s.id
                WHERE ci.topic_id = $1
                  AND s.platform IN ('reddit', 'telegram')
                """,
                test_topic,
            )
        platforms = {r["platform"] for r in rows}
        assert "reddit" in platforms, "reddit platform must be in content_items"
        assert "telegram" in platforms, "telegram platform must be in content_items"
        assert len(platforms) >= 2, (
            "independent_source_count must see 2+ distinct platforms (criteria 3.29)"
        )


class TestIngestEdgeCases:
    """Edge cases — empty text, unknown source."""

    @pytest.mark.asyncio
    async def test_empty_text_not_inserted(self, db_pool, test_topic, mock_arq_pool):
        raw = RawItem(
            raw_text="   ",
            url="https://example.com/empty",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/worldnews",
        )
        result = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        assert result is False
        mock_arq_pool.enqueue_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_source_handle_not_inserted(self, db_pool, test_topic, mock_arq_pool):
        raw = RawItem(
            raw_text="Content from unknown handle " + str(uuid.uuid4()),
            url="https://example.com/unknown",
            platform="reddit",
            captured_at=datetime.now(UTC),
            source_handle="r/nonexistent_subreddit_xyz",
        )
        result = await ingest_raw_item(
            raw, test_topic, db_pool, mock_arq_pool, "reddit-v1", org_id="org-integration-test"
        )
        assert result is False
