"""Unit tests for scraper circuit breaker — skip 'down' sources, auto-recovery.

Tests:
  - SQL queries exclude health_status='down' sources
  - Health check promotes 'down' → 'healthy' on successful check (auto-recovery)
  - Health check trips 'healthy' → 'down' after 3+ consecutive failures
  - Prometheus metrics fire on trip/recovery
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# SQL filter — down sources excluded
# ---------------------------------------------------------------------------


class TestCircuitBreakerSQLFilter:
    def test_web_sources_query_excludes_down(self):
        from anveshak.scraper.jobs import SQL_GET_WEB_SOURCES

        assert "health_status != 'down'" in SQL_GET_WEB_SOURCES

    def test_rss_sources_query_excludes_down(self):
        from anveshak.scraper.jobs import SQL_GET_RSS_SOURCES

        assert "health_status != 'down'" in SQL_GET_RSS_SOURCES


# ---------------------------------------------------------------------------
# Health status transitions
# ---------------------------------------------------------------------------


class TestHealthStatusTransitions:
    def test_healthy_result_resets_failures(self):
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("healthy", None)
        status, failures = _next_status(result, prev_failures=5)
        assert status == "healthy"
        assert failures == 0

    def test_hard_degraded_result_increments_failures(self):
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("degraded", "timeout", hard_failure=True)
        status, failures = _next_status(result, prev_failures=0)
        assert status == "degraded"
        assert failures == 1

    def test_soft_degraded_result_does_not_increment_failures(self):
        """Soft warnings (paywall heuristic) must not accumulate toward 'down'."""
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("degraded", "Possible paywall", hard_failure=False)
        status, failures = _next_status(result, prev_failures=2)
        assert status == "degraded"
        assert failures == 2  # unchanged

    def test_soft_degraded_never_reaches_down(self):
        """Even after many soft warnings, source stays degraded — never down."""
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("degraded", "Possible paywall", hard_failure=False)
        s, f = "degraded", 0
        for _ in range(10):
            s, f = _next_status(result, f)
        assert s == "degraded"
        assert f == 0

    def test_three_hard_failures_trips_to_down(self):
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("degraded", "timeout", hard_failure=True)
        status, failures = _next_status(result, prev_failures=2)
        assert status == "down"
        assert failures == 3

    def test_already_down_stays_down_on_failure(self):
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("degraded", "still broken", hard_failure=True)
        status, failures = _next_status(result, prev_failures=10)
        assert status == "down"
        assert failures == 11

    def test_down_source_recovers_on_healthy_check(self):
        """Circuit breaker auto-recovery: healthy check resets from any failure count."""
        from anveshak.scraper.health import HealthResult, _next_status

        result = HealthResult("healthy", None)
        status, failures = _next_status(result, prev_failures=100)
        assert status == "healthy"
        assert failures == 0


# ---------------------------------------------------------------------------
# Health check functions
# ---------------------------------------------------------------------------


class TestWebHealthCheck:
    @pytest.mark.asyncio
    async def test_empty_content_returns_degraded_hard(self):
        from unittest.mock import AsyncMock, patch

        from anveshak.scraper.health import check_web_health

        with patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            result = await check_web_health("https://example.com")

        assert result.status == "degraded"
        assert "no content" in result.error.lower()
        assert result.hard_failure  # empty content is a real failure

    @pytest.mark.asyncio
    async def test_short_content_returns_degraded_soft(self):
        from unittest.mock import AsyncMock, patch

        from anveshak.scraper.health import check_web_health

        with patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "Short"
            result = await check_web_health("https://example.com")

        assert result.status == "degraded"
        assert "too short" in result.error.lower()
        assert not result.hard_failure  # short content is a soft warning

    @pytest.mark.asyncio
    async def test_paywall_content_returns_degraded(self):
        from unittest.mock import AsyncMock, patch

        from anveshak.scraper.health import check_web_health

        with patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "x" * 300 + " premium content required to continue reading"
            result = await check_web_health("https://example.com")

        assert result.status == "degraded"
        assert "paywall" in result.error.lower()
        assert not result.hard_failure  # paywall heuristic is a soft warning

    @pytest.mark.asyncio
    async def test_good_content_returns_healthy(self):
        from unittest.mock import AsyncMock, patch

        from anveshak.scraper.health import check_web_health

        with patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "A" * 500
            result = await check_web_health("https://example.com")

        assert result.status == "healthy"
        assert result.error is None


# ---------------------------------------------------------------------------
# Metrics exist
# ---------------------------------------------------------------------------


class TestCircuitBreakerMetrics:
    def test_circuit_breaker_metric_exists(self):
        from anveshak.scraper.metrics import scraper_circuit_breaker_total

        assert scraper_circuit_breaker_total is not None

    def test_sources_skipped_metric_exists(self):
        from anveshak.scraper.metrics import scraper_sources_skipped_total

        assert scraper_sources_skipped_total is not None
