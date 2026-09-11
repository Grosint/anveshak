"""The browser's own requests are judged too (issue #55).

Crawl4AI drives Playwright, which resolves names and follows redirects inside
its own process, so the httpx-side guard never sees those requests. A page-level
route guard is the in-process control; egress policy is the one outside it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


class _Request:
    def __init__(self, url: str) -> None:
        self.url = url


class _Route:
    """A Playwright route double, recording which way it was resolved."""

    def __init__(self, url: str) -> None:
        self.request = _Request(url)
        self.aborted = False
        self.continued = False

    async def abort(self) -> None:
        self.aborted = True

    async def continue_(self) -> None:
        self.continued = True


async def _approve(url: str):
    from anveshak.net.url_safety import ResolvedTarget

    return ResolvedTarget(url=url, hostname="example.com", address="93.184.216.34")


async def _refuse(url: str):
    return None


class TestRouteGuard:
    async def test_an_internal_address_is_aborted(self):
        from anveshak.scraper.fetch import browser_route_guard

        route = _Route("http://ollama:11434/api/tags")
        await browser_route_guard(_refuse)(route)

        assert route.aborted is True
        assert route.continued is False

    async def test_an_external_address_continues(self):
        from anveshak.scraper.fetch import browser_route_guard

        route = _Route("https://example.com/article")
        await browser_route_guard(_approve)(route)

        assert route.continued is True
        assert route.aborted is False

    async def test_a_scheme_that_issues_no_request_continues(self):
        """data: and blob: are the page's own bytes, not an outbound request."""
        from anveshak.scraper.fetch import browser_route_guard

        guard = AsyncMock(side_effect=_refuse)
        route = _Route("data:image/png;base64,iVBORw0KGgo=")
        await browser_route_guard(guard)(route)

        assert route.continued is True
        guard.assert_not_awaited()

    async def test_one_verdict_per_host_rather_than_per_asset(self):
        from anveshak.scraper.fetch import browser_route_guard

        guard = AsyncMock(side_effect=_approve)
        handler = browser_route_guard(guard)
        for path in ("/a.js", "/b.css", "/c.png"):
            await handler(_Route(f"https://example.com{path}"))

        assert guard.await_count == 1, "a page of assets must not be a page of lookups"


class TestGuardInstallation:
    async def test_the_hook_is_set_on_the_crawler_strategy(self):
        from anveshak.scraper.fetch import install_browser_address_guard

        hooks: dict = {}

        class _Strategy:
            def set_hook(self, name, fn):
                hooks[name] = fn

        class _Crawler:
            crawler_strategy = _Strategy()

        installed = await install_browser_address_guard(_Crawler(), _approve)

        assert installed is True
        assert "on_page_context_created" in hooks

        context = AsyncMock()
        await hooks["on_page_context_created"](page=AsyncMock(), context=context)
        context.route.assert_awaited_once()

    async def test_a_crawler_with_no_hook_api_says_so(self):
        from anveshak.scraper.fetch import install_browser_address_guard

        class _Crawler:
            pass

        assert await install_browser_address_guard(_Crawler(), _approve) is False

    async def test_the_guard_can_be_turned_off_and_reports_it(self):
        from anveshak.scraper import fetch as fetch_module

        class _Crawler:
            crawler_strategy = object()

        with patch.object(fetch_module.settings, "scraper_browser_address_guard", False):
            with patch.object(fetch_module.log, "info") as logged:
                installed = await fetch_module.install_browser_address_guard(_Crawler(), _approve)

        assert installed is False
        assert logged.called, "a disabled guard must say why, not go quiet"


class TestRouteGuardSurvivesAClosingPage:
    """A page can close between the decision and the call that acts on it."""

    async def test_a_failed_abort_is_logged_not_raised(self):
        from anveshak.scraper.fetch import browser_route_guard

        class _Closed(_Route):
            async def abort(self) -> None:
                raise RuntimeError("Target page, context or browser has been closed")

        await browser_route_guard(_refuse)(_Closed("http://ollama:11434/"))

    async def test_a_failed_continue_is_logged_not_raised(self):
        from anveshak.scraper.fetch import browser_route_guard

        class _Closed(_Route):
            async def continue_(self) -> None:
                raise RuntimeError("Target page, context or browser has been closed")

        await browser_route_guard(_approve)(_Closed("https://example.com/a"))

    async def test_an_unparseable_url_is_aborted(self):
        from anveshak.scraper.fetch import browser_route_guard

        route = _Route("http://[::1/")
        await browser_route_guard(_approve)(route)

        assert route.aborted is True


class TestScraperGuards:
    """The guards the production paths actually pass to the fetch path."""

    async def test_the_proxied_guard_keeps_an_onion_url_on_onion(self):
        from anveshak.scraper.fetch import proxied_guard

        target = await proxied_guard("http://abcdefgh.onion/page")

        assert target is not None
        assert target.address is None, "the proxy resolves it, so nothing is pinned here"

    async def test_the_proxied_guard_refuses_an_internal_name(self):
        from anveshak.scraper.fetch import proxied_guard

        assert await proxied_guard("http://localhost:5432/") is None

    async def test_the_proxied_guard_refuses_an_unparseable_url(self):
        from anveshak.scraper.fetch import proxied_guard

        assert await proxied_guard("http://[::1/") is None

    async def test_the_proxied_guard_resolves_nothing(self, monkeypatch):
        """Resolving a name we will not connect to is a question for the proxy."""
        from anveshak.net import url_safety
        from anveshak.scraper.fetch import proxied_guard

        async def _fail(hostname: str) -> list[str]:
            raise AssertionError("the proxied guard must not resolve a name")

        monkeypatch.setattr(url_safety, "_resolve_host", _fail)

        assert await proxied_guard("https://outlet.example.in/a") is not None

    async def test_guard_for_picks_the_resolving_guard_without_a_proxy(self):
        from anveshak.net.url_safety import resolve_external_target
        from anveshak.scraper.fetch import guard_for, proxied_guard

        assert guard_for(None) is resolve_external_target
        assert guard_for("socks5://tor-proxy:9050") is proxied_guard

    async def test_a_degradation_is_reported_once_not_once_per_request(self):
        from anveshak.scraper import fetch as fetch_module

        fetch_module._degradations_logged.clear()
        try:
            with patch.object(fetch_module.log, "info") as logged:
                for _ in range(3):
                    await fetch_module.proxied_guard("https://outlet.example.in/a")

            assert logged.call_count == 1
        finally:
            fetch_module._degradations_logged.clear()


class TestOnionNamesAreNeverResolved:
    """A clearnet resolver must never be asked about a hidden service."""

    async def test_the_resolving_guard_refuses_an_onion_name(self, monkeypatch):
        from anveshak.net import url_safety

        async def _fail(hostname: str) -> list[str]:
            raise AssertionError("an onion name reached the resolver")

        monkeypatch.setattr(url_safety, "_resolve_host", _fail)

        assert await url_safety.resolve_external_target("http://abcdefgh.onion/x") is None
