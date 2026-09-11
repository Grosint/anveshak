"""Unit tests for scraper health check / circuit breaker logic.

pytest.mark.unit — no external dependencies, no DB, no network.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from anveshak.scraper.health import HealthResult, _next_status, check_web_health

# ---------------------------------------------------------------------------
# _next_status — pure function tests
# ---------------------------------------------------------------------------


class TestNextStatus:
    """Tests for the _next_status state machine."""

    @pytest.mark.unit
    def test_healthy_resets_failures(self):
        """Healthy result → (healthy, 0) regardless of prev_failures."""
        result = HealthResult(status="healthy", error=None)
        assert _next_status(result, 0) == ("healthy", 0)
        assert _next_status(result, 5) == ("healthy", 0)
        assert _next_status(result, 99) == ("healthy", 0)

    @pytest.mark.unit
    def test_hard_failure_increments(self):
        """Hard failure with prev=1 → (degraded, 2)."""
        result = HealthResult(status="degraded", error="Connection refused", hard_failure=True)
        status, failures = _next_status(result, 1)
        assert status == "degraded"
        assert failures == 2

    @pytest.mark.unit
    def test_hard_failure_trips_at_3(self):
        """Hard failure with prev=2 → (down, 3)."""
        result = HealthResult(status="degraded", error="Timeout", hard_failure=True)
        status, failures = _next_status(result, 2)
        assert status == "down"
        assert failures == 3

    @pytest.mark.unit
    def test_soft_warning_no_increment(self):
        """Soft warning (hard_failure=False) with prev=2 → (degraded, 2) — NOT down."""
        result = HealthResult(status="degraded", error="Possible paywall", hard_failure=False)
        status, failures = _next_status(result, 2)
        assert status == "degraded"
        assert failures == 2  # NOT incremented, so never reaches 3 → down

    @pytest.mark.unit
    def test_recovery_from_down(self):
        """Healthy after being down → (healthy, 0)."""
        result = HealthResult(status="healthy", error=None)
        status, failures = _next_status(result, 10)
        assert status == "healthy"
        assert failures == 0


# ---------------------------------------------------------------------------
# check_web_health — async function tests (mock fetch_url)
# ---------------------------------------------------------------------------


class TestCheckWebHealth:
    """Tests for check_web_health — mocks fetch_url."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_paywall_detection(self, mock_fetch_url):
        """Text containing paywall pattern → degraded, soft warning."""
        mock_fetch_url.return_value = (
            "This premium content is available to subscribers only. "
            "Please subscribe to continue reading this article. " * 5
        )
        result = await check_web_health("https://example.com/paywalled")
        assert result.status == "degraded"
        assert result.hard_failure is False
        assert "paywall" in result.error.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_short_content(self, mock_fetch_url):
        """Response < 200 chars → degraded, soft warning."""
        mock_fetch_url.return_value = "Short page."
        result = await check_web_health("https://example.com/short")
        assert result.status == "degraded"
        assert result.hard_failure is False
        assert "too short" in result.error.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_empty_response(self, mock_fetch_url):
        """fetch_url returns None → degraded, hard failure."""
        mock_fetch_url.return_value = None
        result = await check_web_health("https://example.com/blocked")
        assert result.status == "degraded"
        assert result.hard_failure is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_healthy_page(self, mock_fetch_url):
        """Normal page with enough content → healthy."""
        mock_fetch_url.return_value = (
            "This is a real news article about military developments in the region. "
            "The government announced new defence procurement plans. " * 5
        )
        result = await check_web_health("https://example.com/article")
        assert result.status == "healthy"
        assert result.error is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_fetch_exception_is_hard_failure(self, mock_fetch_url):
        """fetch_url raises exception → degraded, hard failure."""
        mock_fetch_url.side_effect = ConnectionError("DNS resolution failed")
        result = await check_web_health("https://unreachable.example.com")
        assert result.status == "degraded"
        assert result.hard_failure is True


# ---------------------------------------------------------------------------
# check_rss_health — async function tests (mock httpx)
# ---------------------------------------------------------------------------


class TestCheckRssHealth:
    """Tests for check_rss_health — mocks httpx.AsyncClient."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_rss_health_empty_entries(self, serve_bytes):
        """Feed reachable but feedparser returns entries=[] → degraded, 'no entries'."""
        import types

        from anveshak.scraper.health import check_rss_health

        empty_feed = types.SimpleNamespace(entries=[])

        with serve_bytes(b"<rss></rss>"):
            # feedparser is lazy-imported inside the function, patch via the module
            with patch.dict(
                "sys.modules", {"feedparser": MagicMock(parse=MagicMock(return_value=empty_feed))}
            ):
                result = await check_rss_health("https://example.com/feed.xml")

        assert result.status == "degraded"
        assert "no entries" in result.error.lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_rss_health_http_403_error(self, serve_bytes):
        """A 403 is an answer about the source, so it is reported rather than raised."""
        from anveshak.scraper.health import check_rss_health

        with serve_bytes(b"forbidden", status=403):
            result = await check_rss_health("https://example.com/feed.xml")

        assert result.status == "degraded"
        assert "403" in result.error

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_rss_health_refuses_a_feed_inside_the_deployment(self, serve_bytes):
        """A source URL naming an internal host is never fetched (#55)."""
        from anveshak.scraper.health import check_rss_health

        with serve_bytes(b"<rss></rss>", addresses=["172.28.0.9"]):
            result = await check_rss_health("http://ollama:11434/feed.xml")

        assert result.status == "degraded"


# ---------------------------------------------------------------------------
# check_darkweb_health — async function tests
# ---------------------------------------------------------------------------


class TestCheckDarkwebHealth:
    """Tests for check_darkweb_health — mocks the fetch path and validate_onion_url."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.validate_onion_url")
    async def test_tor_connection_error(self, mock_validate, serve_error):
        """The proxy is unreachable → degraded, hard_failure=True."""
        from anveshak.scraper.health import check_darkweb_health

        mock_validate.return_value = None  # passes validation

        with serve_error(httpx.ConnectError("Tor SOCKS5 proxy unreachable")):
            result = await check_darkweb_health("http://example.onion/page")

        assert result.status == "degraded"
        assert result.hard_failure is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.validate_onion_url")
    async def test_short_response_49_chars(self, mock_validate, serve_bytes):
        """Response text is 49 chars → degraded, 'too short', hard_failure=True. Boundary at < 50."""
        from anveshak.scraper.health import check_darkweb_health

        mock_validate.return_value = None

        with serve_bytes(b"x" * 49):
            result = await check_darkweb_health("http://example.onion/page")

        assert result.status == "degraded"
        assert "too short" in result.error.lower()
        assert result.hard_failure is True


# ---------------------------------------------------------------------------
# check_web_health — additional edge cases
# ---------------------------------------------------------------------------


class TestCheckWebHealthExtended:
    """Extended tests for check_web_health edge cases."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("anveshak.scraper.health.fetch_url", new_callable=AsyncMock)
    async def test_paywall_uppercase(self, mock_fetch_url):
        """'SUBSCRIBERS ONLY' in uppercase → degraded because .lower() on line 136 catches it."""
        mock_fetch_url.return_value = "THIS ARTICLE IS FOR SUBSCRIBERS ONLY. " * 10
        result = await check_web_health("https://example.com/premium")
        assert result.status == "degraded"
        assert result.hard_failure is False
        assert "paywall" in result.error.lower()
