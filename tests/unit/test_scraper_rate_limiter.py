"""Unit tests for per-domain rate limiter.

pytest.mark.unit — no external dependencies.
"""
import asyncio
import time

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_settings():
    with patch("anveshak.scraper.rate_limiter.settings") as ms:
        ms.scraper_per_domain_delay_s = 1.0
        ms.scraper_per_domain_jitter_s = 0.0  # no jitter in tests
        yield ms


class TestDomainRateLimiter:
    """Tests for DomainRateLimiter."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_first_request_no_delay(self, mock_settings):
        """First request to a domain should not sleep."""
        from anveshak.scraper.rate_limiter import DomainRateLimiter

        limiter = DomainRateLimiter()
        with patch("anveshak.scraper.rate_limiter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await limiter.wait("https://example.com/article1")
            mock_sleep.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_enforces_delay_on_second_request(self, mock_settings):
        """Second request within delay window should sleep."""
        from anveshak.scraper.rate_limiter import DomainRateLimiter

        limiter = DomainRateLimiter()
        with patch("anveshak.scraper.rate_limiter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await limiter.wait("https://example.com/page1")
            await limiter.wait("https://example.com/page2")
            # Second call should have triggered a sleep
            assert mock_sleep.await_count == 1
            delay_arg = mock_sleep.call_args[0][0]
            assert 0 < delay_arg <= 1.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_different_domains_independent(self, mock_settings):
        """Requests to different domains should not delay each other."""
        from anveshak.scraper.rate_limiter import DomainRateLimiter

        limiter = DomainRateLimiter()
        with patch("anveshak.scraper.rate_limiter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await limiter.wait("https://example.com/page1")
            await limiter.wait("https://other.com/page1")
            # No sleep — different domains
            mock_sleep.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_jitter_applied(self, mock_settings):
        """Jitter adds randomness to delay."""
        mock_settings.scraper_per_domain_jitter_s = 0.5

        from anveshak.scraper.rate_limiter import DomainRateLimiter

        limiter = DomainRateLimiter()
        with patch("anveshak.scraper.rate_limiter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await limiter.wait("https://example.com/page1")
            await limiter.wait("https://example.com/page2")
            assert mock_sleep.await_count == 1
            delay_arg = mock_sleep.call_args[0][0]
            # delay should be within [0.5, 1.5] (1.0 ± 0.5)
            assert 0 < delay_arg <= 1.5

    @pytest.mark.unit
    def test_domain_extraction(self, mock_settings):
        """Correctly extracts netloc from various URL formats."""
        from anveshak.scraper.rate_limiter import DomainRateLimiter

        limiter = DomainRateLimiter()
        assert limiter._domain("https://www.ndtv.com/india-news/article") == "www.ndtv.com"
        assert limiter._domain("http://example.com:8080/path") == "example.com:8080"
        assert limiter._domain("https://idrw.org") == "idrw.org"
