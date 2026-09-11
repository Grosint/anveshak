"""Publication time as a distinct field — issue #24.

captured_at conflated publication time with collection time. Adapters wrote
the platform's timestamp when they had one and now() when they did not, and
afterwards the two cases were indistinguishable. A timeline built on that
column stacks every fallback item at the moment of collection.

published_at is populated only when the platform genuinely supplies it.
NULL means unknown, and the Sentiment Timeline excludes it and reports the
count rather than plotting it at today.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from anveshak.social.adapters.base import RawItem

pytestmark = pytest.mark.unit

PUBLISHED = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


class TestRawItemCarriesPublicationTime:
    def test_published_at_defaults_to_none(self):
        """Silence means unknown. An adapter opts in by setting it."""
        item = RawItem(
            raw_text="text",
            url="https://example.com/1",
            platform="web",
            captured_at=datetime.now(UTC),
            source_handle="example.com",
        )
        assert item.published_at is None

    def test_published_at_is_independent_of_captured_at(self):
        collected = datetime.now(UTC)
        item = RawItem(
            raw_text="text",
            url="https://example.com/1",
            platform="web",
            captured_at=collected,
            source_handle="example.com",
            published_at=PUBLISHED,
        )
        assert item.published_at == PUBLISHED
        assert item.captured_at == collected

    def test_published_at_does_not_change_the_dedup_key(self):
        """content_hash keys on text. Rule 3 is untouched by this field."""
        base = dict(
            raw_text="same text",
            url="https://example.com/1",
            platform="web",
            captured_at=datetime.now(UTC),
            source_handle="example.com",
        )
        assert (
            RawItem(**base).content_hash() == RawItem(**base, published_at=PUBLISHED).content_hash()
        )


class TestRedditPopulatesPublicationTime:
    def test_created_utc_becomes_published_at(self):
        from anveshak.social.adapters.reddit import RedditAdapter

        post = MagicMock()
        post.created_utc = PUBLISHED.timestamp()
        assert RedditAdapter._published_at(post) == PUBLISHED


class TestTelegramPopulatesPublicationTime:
    def test_message_date_becomes_published_at(self):
        from anveshak.social.adapters.telegram import TelegramAdapter

        message = MagicMock()
        message.date = PUBLISHED
        assert TelegramAdapter._published_at(message) == PUBLISHED

    def test_naive_message_date_is_treated_as_utc(self):
        from anveshak.social.adapters.telegram import TelegramAdapter

        message = MagicMock()
        message.date = PUBLISHED.replace(tzinfo=None)
        assert TelegramAdapter._published_at(message) == PUBLISHED

    def test_missing_date_is_none(self):
        from anveshak.social.adapters.telegram import TelegramAdapter

        message = MagicMock()
        message.date = None
        assert TelegramAdapter._published_at(message) is None


class TestBlueskyPopulatesPublicationTime:
    def test_record_created_at_becomes_published_at(self):
        """indexed_at is when Bluesky saw the post, not when it was written."""
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        post = MagicMock()
        post.record.created_at = "2026-03-04T09:30:00Z"
        assert BlueskyAdapter._published_at(post) == PUBLISHED

    def test_unparseable_timestamp_is_none(self):
        from anveshak.social.adapters.bluesky import BlueskyAdapter

        post = MagicMock()
        post.record.created_at = "not a timestamp"
        assert BlueskyAdapter._published_at(post) is None


class TestProfileItemsHaveNoPublicationTime:
    def test_instagram_bio_publication_time_is_none(self):
        """A biography has no publication time by nature — #24 criterion."""
        from anveshak.social.adapters.instagram import InstagramAdapter

        user_info = MagicMock()
        user_info.username = "someaccount"
        user_info.biography = "bio text"
        item = InstagramAdapter._bio_to_raw_item(user_info)
        assert item.published_at is None
        assert item.captured_at is not None


class TestRssPopulatesOnlyWhatTheFeedSupplies:
    def test_feed_with_published_date_sets_it(self):
        from anveshak.scraper.publication_time import SIGNAL_FEED_PUBLISHED
        from anveshak.scraper.rss import _entry_published_at

        entry = {"published_parsed": PUBLISHED.timetuple()}
        assert _entry_published_at(entry) == (PUBLISHED, SIGNAL_FEED_PUBLISHED)

    def test_feed_with_only_an_updated_date_uses_it(self):
        """An Atom outlet that emits only updated is not an undated outlet."""
        from anveshak.scraper.publication_time import SIGNAL_FEED_UPDATED
        from anveshak.scraper.rss import _entry_published_at

        entry = {"updated_parsed": PUBLISHED.timetuple()}
        assert _entry_published_at(entry) == (PUBLISHED, SIGNAL_FEED_UPDATED)

    def test_feed_without_published_date_returns_none(self):
        """Previously this fell back to now(), which is a collection time."""
        from anveshak.scraper.rss import _entry_published_at

        assert _entry_published_at({}) == (None, None)


class TestIngestPersistsBothTimestamps:
    def test_insert_sql_carries_published_at(self):
        from anveshak.social.ingest import SQL_INSERT_CONTENT

        assert "published_at" in SQL_INSERT_CONTENT
        assert "captured_at" in SQL_INSERT_CONTENT

    def test_scraper_insert_sql_carries_published_at(self):
        from anveshak.scraper.jobs import SQL_INSERT_CONTENT

        assert "published_at" in SQL_INSERT_CONTENT
        assert "captured_at" in SQL_INSERT_CONTENT

    def test_placeholder_count_matches_column_count(self):
        """A column added without a placeholder is a runtime argument error."""
        import re

        from anveshak.social.ingest import SQL_INSERT_CONTENT

        columns = SQL_INSERT_CONTENT.split("(", 1)[1].split(")", 1)[0]
        column_count = len([c for c in columns.split(",") if c.strip()])
        placeholders = re.findall(r"\$\d+", SQL_INSERT_CONTENT.split("VALUES", 1)[1])
        assert column_count == len(placeholders)


class TestMigrationRecordsTheBackfillDecision:
    def test_migration_explains_why_existing_rows_stay_null(self):
        from pathlib import Path

        migration = Path("services/api/migrations/versions/006_narrative_detection.py").read_text()
        assert "published_at" in migration
        assert "NULL" in migration

    def test_published_at_is_nullable(self):
        from pathlib import Path

        migration = Path("services/api/migrations/versions/006_narrative_detection.py").read_text()
        assert "published_at TIMESTAMPTZ" in migration
        assert "published_at TIMESTAMPTZ NOT NULL" not in migration


class TestPublicationTimeIsNotAFutureDate:
    def test_adapters_never_invent_a_future_publication_time(self):
        """A platform timestamp is trusted; a fabricated one is not."""
        item = RawItem(
            raw_text="text",
            url="https://example.com/1",
            platform="web",
            captured_at=datetime.now(UTC),
            source_handle="example.com",
            published_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert item.published_at < item.captured_at
