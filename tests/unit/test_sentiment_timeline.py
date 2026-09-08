"""Sentiment Timeline aggregate — issue #29.

Supporting and opposing volume as separate series over publication time,
with mean hostility overlaid. Two diverging volume curves show polarisation;
a rising hostility line shows escalation independent of which side is
growing. A single sentiment score expresses neither.

The chart plots publication time, never collection time. Items with no
publication time are excluded and reported as a count, so a collection
artefact never appears as a spike at today's date.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from anveshak.api.db.timeline import (
    SQL_TIMELINE_BUCKETS,
    SQL_TIMELINE_EXCLUDED_COUNT,
    SQL_TIMELINE_PLATFORM_WINDOWS,
    choose_bucket,
    to_percentages,
)

pytestmark = pytest.mark.unit

TIMELINE_SQL = (
    SQL_TIMELINE_BUCKETS,
    SQL_TIMELINE_EXCLUDED_COUNT,
    SQL_TIMELINE_PLATFORM_WINDOWS,
)


class TestItPlotsPublicationTime:
    def test_the_bucket_query_groups_on_published_at(self):
        assert "published_at" in SQL_TIMELINE_BUCKETS
        assert "captured_at" not in SQL_TIMELINE_BUCKETS

    def test_items_without_a_publication_time_are_excluded(self):
        assert "published_at IS NOT NULL" in SQL_TIMELINE_BUCKETS

    def test_the_excluded_count_is_a_separate_query(self):
        """Reported as a footnote, never silently dropped."""
        assert "published_at IS NULL" in SQL_TIMELINE_EXCLUDED_COUNT


class TestSeries:
    def test_stance_is_split_into_separate_series(self):
        for stance in ("supporting", "opposing", "neutral"):
            assert stance in SQL_TIMELINE_BUCKETS

    def test_mean_hostility_is_aggregated(self):
        assert "AVG" in SQL_TIMELINE_BUCKETS
        assert "hostility" in SQL_TIMELINE_BUCKETS

    def test_unscored_hostility_is_excluded_from_the_mean(self):
        """NULL means not measured; averaging it as 0.0 would invent calm."""
        assert "hostility IS NOT NULL" in SQL_TIMELINE_BUCKETS

    def test_content_marked_unsupported_language_is_counted_separately(self):
        assert "unsupported_language" in SQL_TIMELINE_BUCKETS


class TestBucketing:
    def test_a_short_range_buckets_daily(self):
        assert choose_bucket(days=30) == "day"

    def test_a_long_range_rolls_up_to_weekly(self):
        assert choose_bucket(days=200) == "week"

    def test_the_boundary_is_explicit(self):
        assert choose_bucket(days=90) == "day"
        assert choose_bucket(days=91) == "week"

    def test_the_query_takes_the_bucket_as_a_parameter(self):
        assert "DATE_TRUNC" in SQL_TIMELINE_BUCKETS


class TestPercentageView:
    def test_absolute_counts_convert_to_percentages(self):
        buckets = [
            {"bucket": "2026-03-01", "supporting": 30, "opposing": 10, "neutral": 10},
        ]
        result = to_percentages(buckets)
        assert result[0]["supporting"] == pytest.approx(60.0)
        assert result[0]["opposing"] == pytest.approx(20.0)

    def test_an_empty_bucket_stays_at_zero_rather_than_dividing_by_zero(self):
        buckets = [{"bucket": "2026-03-01", "supporting": 0, "opposing": 0, "neutral": 0}]
        result = to_percentages(buckets)
        assert result[0]["supporting"] == 0.0

    def test_hostility_is_not_converted(self):
        """It is already a 0.0 to 1.0 measure, not a share of volume."""
        buckets = [
            {
                "bucket": "2026-03-01",
                "supporting": 30,
                "opposing": 10,
                "neutral": 10,
                "mean_hostility": 0.4,
            }
        ]
        assert to_percentages(buckets)[0]["mean_hostility"] == pytest.approx(0.4)

    def test_the_absolute_total_survives_the_conversion(self):
        """A bucket that is mostly unscored must not read as fully scored."""
        buckets = [
            {
                "bucket": "2026-03-01",
                "supporting": 30,
                "opposing": 10,
                "neutral": 10,
                "unscored": 200,
                "total": 250,
            }
        ]
        result = to_percentages(buckets)[0]
        assert result["total"] == 250
        assert result["scored_total"] == 50


class TestOrgScoping:
    def test_every_query_is_org_scoped(self):
        for sql in TIMELINE_SQL:
            assert "org_id" in sql

    def test_every_query_is_topic_scoped(self):
        for sql in TIMELINE_SQL:
            assert "topic_id" in sql

    def test_the_repository_function_takes_org_id_keyword_only(self):
        import inspect

        from anveshak.api.db.timeline import get_timeline

        signature = inspect.signature(get_timeline)
        assert signature.parameters["org_id"].kind == inspect.Parameter.KEYWORD_ONLY


class TestDataAvailabilityLabelling:
    def test_the_platform_window_query_reports_earliest_publication_per_platform(self):
        assert "MIN" in SQL_TIMELINE_PLATFORM_WINDOWS
        assert "platform" in SQL_TIMELINE_PLATFORM_WINDOWS

    def test_the_platform_filter_happens_in_sql(self):
        """Filtering in Python meant scanning a Topic's whole history to
        compute a MIN per platform and discarding all but two rows."""
        assert "s.platform = ANY(" in SQL_TIMELINE_PLATFORM_WINDOWS


class TestTheIndexIsUsable:
    def test_no_query_uses_an_or_over_the_link_table(self):
        """idx_content_items_published covers only the topic_id branch. An
        OR with an IN subquery degrades toward a sequential scan, which is
        worst for exactly the accepted Candidate Topics that get their
        content through topic_content_items."""
        for sql in TIMELINE_SQL:
            assert "OR ci.id IN (SELECT" not in sql
            if "topic_content_items" in sql:
                assert "EXISTS (" in sql

    def test_the_constrained_platforms_are_a_setting(self):
        from anveshak.api.settings import settings

        assert isinstance(settings.timeline_constrained_platforms, list)
        assert "twitter" in settings.timeline_constrained_platforms

    def test_no_platform_name_is_hardcoded_in_the_module(self):
        source = Path("services/api/anveshak/api/db/timeline.py").read_text()
        assert '"twitter"' not in source


class TestQualityGate:
    def test_the_gate_is_applied(self):
        assert "content_quality" in SQL_TIMELINE_BUCKETS


class TestRoute:
    def test_the_route_verifies_topic_access(self):
        source = Path("services/api/anveshak/api/routes/timeline.py").read_text()
        assert "verify_topic_access" in source

    def test_the_router_is_wired_into_the_app(self):
        source = Path("services/api/anveshak/api/main.py").read_text()
        assert "timeline_router" in source
