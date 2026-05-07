"""Unit tests for dark web (.onion) scraping via Tor.

Tests:
  - .onion URL validation (valid/invalid)
  - DNS leak prevention (ValueError on non-.onion in fetch_url_via_tor)
  - Dark web SQL query returns only platform='darkweb' sources
  - Labels use RESTRICTED classification
  - Correct timeout/concurrency settings
  - Dark web health check
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# URL validation — DNS leak prevention
# ---------------------------------------------------------------------------

class TestOnionURLValidation:

    def test_valid_http_onion_url(self):
        from anveshak.scraper.fetch import validate_onion_url

        # Should not raise
        validate_onion_url("http://example.onion")

    def test_valid_https_onion_url(self):
        from anveshak.scraper.fetch import validate_onion_url

        validate_onion_url("https://example.onion/page")

    def test_valid_onion_with_subdomain(self):
        from anveshak.scraper.fetch import validate_onion_url

        validate_onion_url("http://subdomain.example.onion/path?q=1")

    def test_rejects_clearnet_url(self):
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError, match="DNS leak prevention"):
            validate_onion_url("https://example.com")

    def test_rejects_onion_as_substring(self):
        """Ensure 'onion' as part of domain (not TLD) is rejected."""
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError, match="DNS leak prevention"):
            validate_onion_url("https://onionsite.com")

    def test_rejects_ftp_scheme(self):
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError, match="scheme"):
            validate_onion_url("ftp://example.onion/file")

    def test_rejects_empty_url(self):
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError):
            validate_onion_url("")


# ---------------------------------------------------------------------------
# fetch_url_via_tor — DNS leak prevention at fetch level
# ---------------------------------------------------------------------------

class TestFetchURLViaTor:

    @pytest.mark.asyncio
    async def test_rejects_clearnet_url(self):
        """fetch_url_via_tor must raise ValueError for non-.onion URLs."""
        from anveshak.scraper.fetch import fetch_url_via_tor

        with pytest.raises(ValueError, match="DNS leak prevention"):
            await fetch_url_via_tor("https://example.com", None, None)


# ---------------------------------------------------------------------------
# SQL query — darkweb sources only
# ---------------------------------------------------------------------------

class TestDarkwebSQLFilter:

    def test_darkweb_query_filters_platform(self):
        from anveshak.scraper.jobs import SQL_GET_DARKWEB_SOURCES

        assert "platform = 'darkweb'" in SQL_GET_DARKWEB_SOURCES

    def test_darkweb_query_joins_topic_sources(self):
        from anveshak.scraper.jobs import SQL_GET_DARKWEB_SOURCES

        assert "topic_sources" in SQL_GET_DARKWEB_SOURCES
        assert "topic_id = $1" in SQL_GET_DARKWEB_SOURCES

    def test_darkweb_query_excludes_down(self):
        from anveshak.scraper.jobs import SQL_GET_DARKWEB_SOURCES

        assert "health_status != 'down'" in SQL_GET_DARKWEB_SOURCES

    def test_darkweb_query_only_active(self):
        from anveshak.scraper.jobs import SQL_GET_DARKWEB_SOURCES

        assert "is_active = TRUE" in SQL_GET_DARKWEB_SOURCES


# ---------------------------------------------------------------------------
# Labels — RESTRICTED classification for dark web content
# ---------------------------------------------------------------------------

class TestDarkwebLabels:

    def test_darkweb_labels_classification_restricted(self):
        import json
        from anveshak.scraper.jobs import _DARKWEB_LABELS_JSON

        labels = json.loads(_DARKWEB_LABELS_JSON)
        assert labels["classification"] == "RESTRICTED"

    def test_darkweb_labels_domain_darkweb(self):
        import json
        from anveshak.scraper.jobs import _DARKWEB_LABELS_JSON

        labels = json.loads(_DARKWEB_LABELS_JSON)
        assert labels["domain"] == "darkweb"

    def test_darkweb_labels_has_owner_org(self):
        import json
        from anveshak.scraper.jobs import _DARKWEB_LABELS_JSON

        labels = json.loads(_DARKWEB_LABELS_JSON)
        assert labels["owner_org"] == "anveshak"

    def test_web_labels_classification_open(self):
        """Web labels must remain OPEN — dark web change must not affect them."""
        import json
        from anveshak.scraper.jobs import _LABELS_JSON

        labels = json.loads(_LABELS_JSON)
        assert labels["classification"] == "OPEN"


# ---------------------------------------------------------------------------
# Settings — dark web specific config
# ---------------------------------------------------------------------------

class TestDarkwebSettings:

    def test_darkweb_timeout_higher_than_web(self):
        from anveshak.scraper.settings import settings

        assert settings.darkweb_request_timeout_s > settings.scraper_request_timeout_s

    def test_darkweb_concurrency_lower_than_web(self):
        from anveshak.scraper.settings import settings

        assert settings.darkweb_concurrency < settings.scraper_concurrency

    def test_darkweb_follow_links_disabled(self):
        from anveshak.scraper.settings import settings

        assert settings.darkweb_follow_links is False

    def test_darkweb_media_download_disabled(self):
        from anveshak.scraper.settings import settings

        assert settings.darkweb_media_download is False

    def test_darkweb_tor_proxy_url_set(self):
        from anveshak.scraper.settings import settings

        assert "9050" in settings.darkweb_tor_proxy_url
        assert "socks5" in settings.darkweb_tor_proxy_url


# ---------------------------------------------------------------------------
# Metrics — dark web histogram exists
# ---------------------------------------------------------------------------

class TestDarkwebMetrics:

    def test_darkweb_fetch_duration_metric_exists(self):
        from anveshak.scraper.metrics import scraper_darkweb_fetch_duration_seconds

        assert scraper_darkweb_fetch_duration_seconds is not None

    def test_darkweb_fetch_duration_has_higher_buckets(self):
        """Tor latency requires higher histogram buckets than clearnet."""
        from anveshak.scraper.metrics import (
            scraper_darkweb_fetch_duration_seconds,
            scraper_fetch_duration_seconds,
        )

        darkweb_max = max(scraper_darkweb_fetch_duration_seconds._kwargs["buckets"])
        web_max = max(scraper_fetch_duration_seconds._kwargs["buckets"])
        assert darkweb_max > web_max


# ---------------------------------------------------------------------------
# Health check — dark web included in daily checks
# ---------------------------------------------------------------------------

class TestDarkwebHealthCheck:

    def test_health_sql_includes_darkweb(self):
        from anveshak.scraper.health import SQL_GET_ALL_ACTIVE_SOURCES

        assert "'darkweb'" in SQL_GET_ALL_ACTIVE_SOURCES

    @pytest.mark.asyncio
    async def test_check_darkweb_health_rejects_clearnet(self):
        from anveshak.scraper.health import check_darkweb_health

        result = await check_darkweb_health("https://example.com")
        assert result.status == "down"
        assert "DNS leak" in (result.error or "")


# ---------------------------------------------------------------------------
# Worker registration
# ---------------------------------------------------------------------------

class TestDarkwebWorkerRegistration:

    def test_scrape_darkweb_topic_registered(self):
        from anveshak.scraper.jobs import WorkerSettings

        func_names = [f.coroutine.__name__ for f in WorkerSettings.functions]
        assert "scrape_darkweb_topic" in func_names
