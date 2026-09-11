"""Unit tests for the shared outbound fetch path (issue #55).

Every hop is validated, not just the first: a redirect chooses its own host,
and a name resolved twice can answer differently the second time. These tests
pin that the request that actually leaves goes to the address the guard
approved, and that a chain ends rather than running forever.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.unit


def _transport(handler):
    return httpx.MockTransport(handler)


def _redirect(location: str, status: int = 302) -> httpx.Response:
    return httpx.Response(status, headers={"location": location})


async def _public(url: str):
    """Guard that approves every URL, pinning it to a fixed public address."""
    from anveshak.net.url_safety import ResolvedTarget

    parsed = httpx.URL(url)
    return ResolvedTarget(url=url, hostname=parsed.host, address="93.184.216.34")


async def _refuse_all(url: str):
    """Guard that refuses everything, as a resolved check on an internal name would."""
    return None


async def _refuse_internal(url: str):
    """Guard that approves example.com only, as a resolved check would."""
    from anveshak.net.url_safety import ResolvedTarget

    parsed = httpx.URL(url)
    if parsed.host != "example.com":
        return None
    return ResolvedTarget(url=url, hostname=parsed.host, address="93.184.216.34")


class TestRedirectValidation:
    """A redirect target is validated before it is fetched."""

    async def test_redirect_to_internal_host_is_refused(self):
        from anveshak.net.safe_fetch import fetch_bytes

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            if request.headers["host"] == "example.com":
                return _redirect("http://ollama:11434/api/tags")
            return httpx.Response(200, content=b"internal secret")

        result = await fetch_bytes(
            "http://example.com/article",
            timeout=5,
            guard=_refuse_internal,
            transport=_transport(handler),
        )

        assert result is None
        assert len(seen) == 1, "the internal hop must never be requested"

    async def test_public_redirect_chain_is_followed(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/article":
                return _redirect("https://example.com/final")
            return httpx.Response(200, content=b"body")

        result = await fetch_bytes(
            "https://example.com/article",
            timeout=5,
            guard=_public,
            transport=_transport(handler),
        )

        assert result is not None
        assert result.body == b"body"
        assert result.url == "https://example.com/final"

    async def test_redirect_chain_is_bounded(self):
        from anveshak.net.safe_fetch import fetch_bytes

        hops: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hops.append(str(request.url))
            return _redirect(f"https://example.com/{len(hops)}")

        result = await fetch_bytes(
            "https://example.com/start",
            timeout=5,
            guard=_public,
            max_redirects=3,
            transport=_transport(handler),
        )

        assert result is None
        assert len(hops) == 4, "the first request plus three redirects, then stop"

    async def test_redirect_without_location_is_refused(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302)

        result = await fetch_bytes(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            transport=_transport(handler),
        )

        assert result is None

    async def test_relative_location_is_joined_against_the_current_url(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/a/b":
                return _redirect("../c")
            return httpx.Response(200, content=b"joined")

        result = await fetch_bytes(
            "https://example.com/a/b",
            timeout=5,
            guard=_public,
            transport=_transport(handler),
        )

        assert result is not None
        assert result.url == "https://example.com/c"


class TestAddressPinning:
    """The connection is made to the address the guard resolved and approved."""

    async def test_request_goes_to_the_validated_address(self):
        from anveshak.net.safe_fetch import fetch_bytes

        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"body")

        await fetch_bytes(
            "https://example.com/article",
            timeout=5,
            guard=_public,
            transport=_transport(handler),
        )

        assert seen[0].url.host == "93.184.216.34"
        assert seen[0].headers["host"] == "example.com"
        assert seen[0].extensions["sni_hostname"] == "example.com"

    async def test_non_default_port_is_kept_in_the_host_header(self):
        from anveshak.net.safe_fetch import fetch_bytes

        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=b"body")

        await fetch_bytes(
            "https://example.com:8443/article",
            timeout=5,
            guard=_public,
            transport=_transport(handler),
        )

        assert seen[0].url.host == "93.184.216.34"
        assert seen[0].url.port == 8443
        assert seen[0].headers["host"] == "example.com:8443"

    async def test_each_hop_is_pinned_to_its_own_resolved_address(self):
        from anveshak.net.safe_fetch import fetch_bytes
        from anveshak.net.url_safety import ResolvedTarget

        addresses = {"example.com": "93.184.216.34", "cdn.example.net": "203.0.113.7"}

        async def guard(url: str):
            host = httpx.URL(url).host
            return ResolvedTarget(url=url, hostname=host, address=addresses[host])

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.host)
            if request.headers["host"] == "example.com":
                return _redirect("https://cdn.example.net/final")
            return httpx.Response(200, content=b"body")

        result = await fetch_bytes(
            "https://example.com/a", timeout=5, guard=guard, transport=_transport(handler)
        )

        assert result is not None
        assert seen == ["93.184.216.34", "203.0.113.7"]

    async def test_a_name_is_not_resolved_a_second_time_by_the_client(self):
        """Rebinding: the guard's answer is used, not a fresh lookup."""
        from anveshak.net.safe_fetch import fetch_bytes
        from anveshak.net.url_safety import ResolvedTarget

        answers = iter(["93.184.216.34", "127.0.0.1"])

        async def guard(url: str):
            return ResolvedTarget(url=url, hostname="example.com", address=next(answers))

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.host)
            return httpx.Response(200, content=b"body")

        await fetch_bytes(
            "https://example.com/a", timeout=5, guard=guard, transport=_transport(handler)
        )

        assert seen == ["93.184.216.34"], "the client must not resolve the name itself"

    async def test_no_pinning_when_the_guard_names_no_address(self):
        """A proxied fetch, .onion included, resolves at the proxy not here."""
        from anveshak.net.safe_fetch import fetch_bytes
        from anveshak.net.url_safety import ResolvedTarget

        async def guard(url: str):
            return ResolvedTarget(url=url, hostname=httpx.URL(url).host, address=None)

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.host)
            return httpx.Response(200, content=b"body")

        await fetch_bytes(
            "http://abc.onion/page", timeout=5, guard=guard, transport=_transport(handler)
        )

        assert seen == ["abc.onion"]


class TestResponseBounds:
    """A document served by an untrusted host is bounded, not buffered whole."""

    async def test_body_past_the_limit_is_refused(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 5000)

        result = await fetch_bytes(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            limit=1000,
            transport=_transport(handler),
        )

        assert result is None

    async def test_error_status_is_refused_by_default(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"nope")

        result = await fetch_bytes(
            "https://example.com/a", timeout=5, guard=_public, transport=_transport(handler)
        )

        assert result is None

    async def test_error_status_is_returned_when_the_caller_asks_for_it(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"nope")

        result = await fetch_bytes(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            expect_ok=False,
            transport=_transport(handler),
        )

        assert result is not None
        assert result.status == 404

    async def test_transport_error_returns_none(self):
        from anveshak.net.safe_fetch import fetch_bytes

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        result = await fetch_bytes(
            "https://example.com/a", timeout=5, guard=_public, transport=_transport(handler)
        )

        assert result is None


class TestResolveExternalTarget:
    """The resolved guard returns the address it approved, for pinning."""

    async def test_returns_the_resolved_address(self, monkeypatch):
        from anveshak.net import url_safety

        async def fake_resolve(hostname: str) -> list[str]:
            return ["93.184.216.34"]

        monkeypatch.setattr(url_safety, "_resolve_host", fake_resolve)
        target = await url_safety.resolve_external_target("https://example.com/a")

        assert target is not None
        assert target.address == "93.184.216.34"
        assert target.hostname == "example.com"

    async def test_refuses_a_name_answering_with_any_internal_address(self, monkeypatch):
        from anveshak.net import url_safety

        async def fake_resolve(hostname: str) -> list[str]:
            return ["93.184.216.34", "172.28.0.5"]

        monkeypatch.setattr(url_safety, "_resolve_host", fake_resolve)

        assert await url_safety.resolve_external_target("https://example.com/a") is None

    async def test_refuses_a_name_that_resolves_to_nothing(self, monkeypatch):
        from anveshak.net import url_safety

        async def fake_resolve(hostname: str) -> list[str]:
            return []

        monkeypatch.setattr(url_safety, "_resolve_host", fake_resolve)

        assert await url_safety.resolve_external_target("https://example.com/a") is None


class TestFailureReasons:
    """A refusal says why, because the reason reaches an operator (#55 review)."""

    async def test_a_refused_address_reports_the_refusal(self):
        from anveshak.net.safe_fetch import FetchFailure, fetch

        outcome = await fetch(
            "https://example.com/a",
            timeout=5,
            guard=_refuse_all,
            transport=_transport(lambda request: httpx.Response(200)),
        )

        assert isinstance(outcome, FetchFailure)
        assert "guard" in outcome.reason

    async def test_a_transport_failure_carries_the_error(self):
        from anveshak.net.safe_fetch import FetchFailure, fetch

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("All connection attempts failed")

        outcome = await fetch(
            "https://example.com/a", timeout=5, guard=_public, transport=_transport(handler)
        )

        assert isinstance(outcome, FetchFailure)
        assert "All connection attempts failed" in outcome.reason

    async def test_a_status_failure_keeps_the_status(self):
        from anveshak.net.safe_fetch import FetchFailure, fetch

        outcome = await fetch(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            transport=_transport(lambda request: httpx.Response(503)),
        )

        assert isinstance(outcome, FetchFailure)
        assert outcome.status == 503
        assert "503" in outcome.reason

    async def test_a_redirect_without_location_keeps_its_status(self):
        from anveshak.net.safe_fetch import FetchFailure, fetch

        outcome = await fetch(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            transport=_transport(lambda request: httpx.Response(302)),
        )

        assert isinstance(outcome, FetchFailure)
        assert outcome.status == 302

    async def test_a_guard_that_raises_is_a_refusal_not_a_crash(self):
        from anveshak.net.safe_fetch import FetchFailure, fetch

        async def guard(url: str):
            raise RuntimeError("robots.txt check exploded")

        outcome = await fetch(
            "https://example.com/a",
            timeout=5,
            guard=guard,
            transport=_transport(lambda request: httpx.Response(200)),
        )

        assert isinstance(outcome, FetchFailure)
        assert "robots.txt check exploded" in outcome.reason

    async def test_a_host_that_cannot_be_built_into_a_request_is_a_refusal(self):
        """An IDNA codepoint httpx rejects must not escape as an exception."""
        from anveshak.net.safe_fetch import FetchFailure, fetch
        from anveshak.net.url_safety import ResolvedTarget

        async def guard(url: str):
            return ResolvedTarget(url=url, hostname="\x80", address=None)

        outcome = await fetch(
            "http://\x80.example.com/a",
            timeout=5,
            guard=guard,
            transport=_transport(lambda request: httpx.Response(200)),
        )

        assert isinstance(outcome, FetchFailure)


class TestAddressFallback:
    """Every address the guard approved is tried, as a resolving client would."""

    async def test_a_second_address_is_tried_when_the_first_refuses(self):
        from anveshak.net.safe_fetch import FetchResult, fetch
        from anveshak.net.url_safety import ResolvedTarget

        async def guard(url: str):
            return ResolvedTarget(
                url=url,
                hostname="example.com",
                address="93.184.216.34",
                alternates=("203.0.113.7",),
            )

        tried: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            tried.append(request.url.host)
            if request.url.host == "93.184.216.34":
                raise httpx.ConnectError("no route to host")
            return httpx.Response(200, content=b"body")

        outcome = await fetch(
            "https://example.com/a", timeout=5, guard=guard, transport=_transport(handler)
        )

        assert isinstance(outcome, FetchResult)
        assert tried == ["93.184.216.34", "203.0.113.7"]


class TestProxiedFetchesArePinnedToNothing:
    async def test_a_proxy_overrides_an_address_the_guard_returned(self):
        """Pinning under a proxy would hand the proxy an address we resolved."""
        from anveshak.net.safe_fetch import fetch_bytes

        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.host)
            return httpx.Response(200, content=b"body")

        await fetch_bytes(
            "https://example.com/a",
            timeout=5,
            guard=_public,
            proxy="socks5://tor-proxy:9050",
            transport=_transport(handler),
        )

        assert seen == ["example.com"]


class TestFetchText:
    async def test_the_body_is_decoded_with_the_declared_encoding(self):
        from anveshak.net.safe_fetch import fetch_text

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content="मुंबई".encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )

        text = await fetch_text(
            "https://example.com/a", timeout=5, guard=_public, transport=_transport(handler)
        )

        assert text == "मुंबई"

    async def test_a_refusal_decodes_to_nothing(self):
        from anveshak.net.safe_fetch import fetch_text

        text = await fetch_text(
            "https://example.com/a",
            timeout=5,
            guard=_refuse_all,
            transport=_transport(lambda request: httpx.Response(200)),
        )

        assert text is None
