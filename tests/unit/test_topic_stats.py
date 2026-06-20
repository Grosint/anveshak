"""Tests for topic stats, top authors, and network graph SQL and endpoints."""
import pytest


# ---------------------------------------------------------------------------
# Phase 1: Topic Stats SQL
# ---------------------------------------------------------------------------

class TestTopicStatsSql:
    def test_platform_stats_sql_groups_by_platform(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_PLATFORM_STATS
        assert "GROUP BY s.platform" in SQL_TOPIC_PLATFORM_STATS
        assert "$1" in SQL_TOPIC_PLATFORM_STATS
        assert "$2" in SQL_TOPIC_PLATFORM_STATS

    def test_volume_timeline_sql_groups_by_date(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_VOLUME_TIMELINE
        assert "GROUP BY DATE(captured_at)" in SQL_TOPIC_VOLUME_TIMELINE
        assert "ORDER BY date ASC" in SQL_TOPIC_VOLUME_TIMELINE

    def test_engagement_summary_uses_coalesce(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_ENGAGEMENT_SUMMARY
        assert "COALESCE" in SQL_TOPIC_ENGAGEMENT_SUMMARY
        assert "labels->'engagement'" in SQL_TOPIC_ENGAGEMENT_SUMMARY

    def test_engagement_handles_platform_variants(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_ENGAGEMENT_SUMMARY
        assert "retweets" in SQL_TOPIC_ENGAGEMENT_SUMMARY
        assert "reposts" in SQL_TOPIC_ENGAGEMENT_SUMMARY
        assert "forwards" in SQL_TOPIC_ENGAGEMENT_SUMMARY


# ---------------------------------------------------------------------------
# Phase 2: Top Authors SQL
# ---------------------------------------------------------------------------

class TestTopAuthorsSql:
    def test_top_authors_sql_filters_null_handles(self):
        from anveshak.api.routes.intelligence import SQL_TOP_AUTHORS
        assert "author_handle' IS NOT NULL" in SQL_TOP_AUTHORS
        # Must use ci.labels prefix to avoid ambiguity with sources.labels
        assert "ci.labels" in SQL_TOP_AUTHORS

    def test_top_authors_sql_has_limit(self):
        from anveshak.api.routes.intelligence import SQL_TOP_AUTHORS
        assert "LIMIT $3" in SQL_TOP_AUTHORS

    def test_top_authors_weights_shares_5x(self):
        from anveshak.api.routes.intelligence import SQL_TOP_AUTHORS
        assert "* 5" in SQL_TOP_AUTHORS


# ---------------------------------------------------------------------------
# Phase 4: Network Graph SQL
# ---------------------------------------------------------------------------

class TestNetworkGraphSql:
    def test_forward_network_sql_groups_correctly(self):
        from anveshak.api.routes.intelligence import SQL_FORWARD_NETWORK
        assert "forwarded_from_channel_name" in SQL_FORWARD_NETWORK
        assert "GROUP BY source_author, target_author" in SQL_FORWARD_NETWORK

    def test_author_post_counts_sql_has_limit(self):
        from anveshak.api.routes.intelligence import SQL_AUTHOR_POST_COUNTS
        assert "LIMIT $2" in SQL_AUTHOR_POST_COUNTS
