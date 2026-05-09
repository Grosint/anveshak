"""Unit tests for robots.txt enforcement in scraper fetch.

Tests:
  - Allowed URL passes through
  - Disallowed URL returns None (skipped)
  - Cache hit: second call for same domain doesn't re-fetch robots.txt
  - .onion URLs bypass robots.txt check
  - Setting respect_robots_txt=False bypasses check
  - Unreachable robots.txt defaults to allow (permissive)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

pytestmark = pytest.mark.unit


class TestRobotsCheck:

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from anveshak.scraper.fetch import _robots_cache
        _robots_cache.clear()
        yield
        _robots_cache.clear()

    @pytest.mark.asyncio
    async def test_allowed_url_passes(self):
        """URL allowed by robots.txt is fetched normally."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch._fetch_robots_txt", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "User-agent: *\nAllow: /\n"
            with patch("anveshak.scraper.fetch.settings") as mock_settings:
                mock_settings.respect_robots_txt = True
                result = await check_robots_allowed("https://example.com/allowed/page")
                assert result is True

    @pytest.mark.asyncio
    async def test_disallowed_url_blocked(self):
        """URL disallowed by robots.txt returns False."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch._fetch_robots_txt", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "User-agent: *\nDisallow: /private\n"
            with patch("anveshak.scraper.fetch.settings") as mock_settings:
                mock_settings.respect_robots_txt = True
                result = await check_robots_allowed("https://example.com/private/secret")
                assert result is False

    @pytest.mark.asyncio
    async def test_cache_hit_no_refetch(self):
        """Second call for same domain uses cache — doesn't fetch robots.txt again."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch._fetch_robots_txt", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "User-agent: *\nAllow: /\n"
            with patch("anveshak.scraper.fetch.settings") as mock_settings:
                mock_settings.respect_robots_txt = True
                await check_robots_allowed("https://example.com/page1")
                await check_robots_allowed("https://example.com/page2")
                assert mock_fetch.await_count == 1

    @pytest.mark.asyncio
    async def test_onion_url_bypasses_check(self):
        """Dark web (.onion) URLs always return True — no robots.txt on Tor."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch.settings") as mock_settings:
            mock_settings.respect_robots_txt = True
            result = await check_robots_allowed("http://darksite.onion/secret")
            assert result is True

    @pytest.mark.asyncio
    async def test_setting_disabled_bypasses_check(self):
        """When respect_robots_txt=False, always returns True."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch.settings") as mock_settings:
            mock_settings.respect_robots_txt = False
            result = await check_robots_allowed("https://example.com/private")
            assert result is True

    @pytest.mark.asyncio
    async def test_unreachable_robots_defaults_allow(self):
        """If robots.txt can't be fetched, default to allowing."""
        from anveshak.scraper.fetch import check_robots_allowed

        with patch("anveshak.scraper.fetch._fetch_robots_txt", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None  # fetch failed
            with patch("anveshak.scraper.fetch.settings") as mock_settings:
                mock_settings.respect_robots_txt = True
                result = await check_robots_allowed("https://unreachable.com/page")
                assert result is True
