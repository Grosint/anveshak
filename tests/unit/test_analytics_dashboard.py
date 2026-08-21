"""Tests for analytics dashboard backend — db/analytics.py + route.

pytest.mark.unit — no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


# ===================================================================
# 1. DB module: SQL constants exist
# ===================================================================


class TestAnalyticsSQLConstants:
    """db/analytics.py must define all required SQL constants."""

    def test_content_volume_trend_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_CONTENT_VOLUME_TREND

        assert "content_items" in SQL_CONTENT_VOLUME_TREND.lower()
        assert "$1" in SQL_CONTENT_VOLUME_TREND

    def test_content_by_platform_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_CONTENT_BY_PLATFORM

        assert "platform" in SQL_CONTENT_BY_PLATFORM.lower()
        assert "$1" in SQL_CONTENT_BY_PLATFORM

    def test_content_by_language_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_CONTENT_BY_LANGUAGE

        assert "language" in SQL_CONTENT_BY_LANGUAGE.lower()
        assert "$1" in SQL_CONTENT_BY_LANGUAGE

    def test_top_entities_global_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_TOP_ENTITIES_GLOBAL

        assert "extracted_entities" in SQL_TOP_ENTITIES_GLOBAL.lower()
        assert "$1" in SQL_TOP_ENTITIES_GLOBAL

    def test_sentiment_distribution_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_SENTIMENT_DISTRIBUTION

        assert "sentiment" in SQL_SENTIMENT_DISTRIBUTION.lower()
        assert "$1" in SQL_SENTIMENT_DISTRIBUTION

    def test_signal_activity_trend_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_SIGNAL_ACTIVITY_TREND

        assert "signals" in SQL_SIGNAL_ACTIVITY_TREND.lower()
        assert "$1" in SQL_SIGNAL_ACTIVITY_TREND

    def test_recent_activity_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_RECENT_ACTIVITY

        assert "signals" in SQL_RECENT_ACTIVITY.lower()
        assert "reports" in SQL_RECENT_ACTIVITY.lower()

    def test_active_topics_sql_exists(self):
        from services.api.anveshak.api.db.analytics import SQL_ACTIVE_TOPICS

        assert "topics" in SQL_ACTIVE_TOPICS.lower()

    def test_entities_filter_noise_types(self):
        """Noise entity types (CARDINAL, ORDINAL, DATE, TIME, MONEY) must be excluded."""
        from services.api.anveshak.api.db.analytics import SQL_TOP_ENTITIES_GLOBAL

        assert "CARDINAL" in SQL_TOP_ENTITIES_GLOBAL
        assert "NOT IN" in SQL_TOP_ENTITIES_GLOBAL.upper()

    def test_all_queries_have_org_id_filter(self):
        """Every SQL constant must filter by org_id for multi-tenancy."""
        from services.api.anveshak.api.db import analytics

        sql_constants = [
            analytics.SQL_CONTENT_VOLUME_TREND,
            analytics.SQL_CONTENT_BY_PLATFORM,
            analytics.SQL_CONTENT_BY_LANGUAGE,
            analytics.SQL_TOP_ENTITIES_GLOBAL,
            analytics.SQL_SENTIMENT_DISTRIBUTION,
            analytics.SQL_SIGNAL_ACTIVITY_TREND,
            analytics.SQL_RECENT_ACTIVITY,
            analytics.SQL_ACTIVE_TOPICS,
        ]
        for sql in sql_constants:
            assert "org_id" in sql.lower(), f"Missing org_id filter in SQL: {sql[:60]}..."


# ===================================================================
# 2. DB function: get_dashboard_data() shape
# ===================================================================


class TestGetDashboardData:
    """get_dashboard_data() must return dict with all required keys."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self, mock_conn):
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
            }
        )

        result = await get_dashboard_data(mock_conn, days=30, org_id="org-test")

        assert isinstance(result, dict)
        required_keys = [
            "content_volume_trend",
            "content_by_platform",
            "content_by_language",
            "top_entities",
            "sentiment_distribution",
            "signal_activity_trend",
            "recent_activity",
            "active_topics",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_content_volume_trend_is_list(self, mock_conn):
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
            }
        )

        result = await get_dashboard_data(mock_conn, days=30, org_id="org-test")
        assert isinstance(result["content_volume_trend"], list)

    @pytest.mark.asyncio
    async def test_sentiment_distribution_is_dict(self, mock_conn):
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 5,
                "neutral": 10,
                "negative": 2,
                "total": 17,
            }
        )

        result = await get_dashboard_data(mock_conn, days=30, org_id="org-test")
        sentiment = result["sentiment_distribution"]
        assert isinstance(sentiment, dict)
        assert "positive" in sentiment
        assert "neutral" in sentiment
        assert "negative" in sentiment
        assert "total" in sentiment

    @pytest.mark.asyncio
    async def test_active_topics_is_int(self, mock_conn):
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=5)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
            }
        )

        result = await get_dashboard_data(mock_conn, days=7, org_id="org-test")
        assert isinstance(result["active_topics"], int)

    @pytest.mark.asyncio
    async def test_days_param_passed_to_queries(self, mock_conn):
        """All time-filtered queries must receive the days parameter."""
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
            }
        )

        await get_dashboard_data(mock_conn, days=7, org_id="org-test")

        all_calls = (
            mock_conn.fetch.call_args_list
            + mock_conn.fetchval.call_args_list
            + mock_conn.fetchrow.call_args_list
        )
        days_passed = any(7 in call.args for call in all_calls if len(call.args) > 1)
        assert days_passed, "days=7 not passed to any query"

    @pytest.mark.asyncio
    async def test_null_sentiment_row_returns_zeros(self, mock_conn):
        """If sentiment query returns None, should return zero dict."""
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await get_dashboard_data(mock_conn, days=30, org_id="org-test")
        assert result["sentiment_distribution"] == {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "total": 0,
        }

    @pytest.mark.asyncio
    async def test_org_id_passed_to_all_queries(self, mock_conn):
        """org_id must be passed to every query for org isolation."""
        from services.api.anveshak.api.db.analytics import get_dashboard_data

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "total": 0,
            }
        )

        await get_dashboard_data(mock_conn, days=30, org_id="org-xyz")

        all_calls = (
            mock_conn.fetch.call_args_list
            + mock_conn.fetchval.call_args_list
            + mock_conn.fetchrow.call_args_list
        )
        for call in all_calls:
            assert "org-xyz" in call.args, f"org_id missing from query call: {call}"


# ===================================================================
# 3. Route exists and is registered
# ===================================================================


class TestAnalyticsDashboardRoute:
    """Route /api/v1/system/analytics-dashboard must exist."""

    def test_route_registered_on_system_router(self):
        from services.api.anveshak.api.routes.system import router

        paths = [r.path for r in router.routes]
        assert "/analytics-dashboard" in paths or "/api/v1/system/analytics-dashboard" in paths, (
            f"analytics-dashboard route not found in: {paths}"
        )

    def test_route_accepts_get_method(self):
        from services.api.anveshak.api.routes.system import router

        for route in router.routes:
            path = getattr(route, "path", "")
            if "analytics-dashboard" in path:
                methods = getattr(route, "methods", set())
                assert "GET" in methods
                return
        pytest.fail("analytics-dashboard route not found")

    def test_route_has_days_query_param(self):
        """Route must accept ?days= query parameter."""
        import inspect

        from services.api.anveshak.api.routes.system import router

        for route in router.routes:
            path = getattr(route, "path", "")
            if "analytics-dashboard" in path:
                endpoint = route.endpoint
                sig = inspect.signature(endpoint)
                assert "days" in sig.parameters, "Route missing 'days' parameter"
                return
        pytest.fail("analytics-dashboard route not found")
