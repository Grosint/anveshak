"""One outbound fetch path for addresses chosen by scraped content.

A link in a feed, a link in a page and a media URL in markup are all written by
whoever we are collecting from, and each becomes a request from a worker sitting
on the internal network alongside postgres, redis, ollama and the API. Judging
the address once, before the request, does not hold:

- a redirect names the host that is finally fetched, and it is not the host that
  was judged;
- a name resolved by the guard and again by the client is two answers, and the
  second is the attacker's to choose.

So the judgement is made a property of the path rather than a call each caller
has to remember. Every hop goes through the guard, the chain is bounded, and the
connection is made to the address the guard returned rather than to a fresh
lookup of the name.

What this does not cover: a browser resolves and navigates inside its own
process, so Crawl4AI is guarded at the page level instead (see the scraper's
fetch module) and by egress policy. See docs/adr/0005-outbound-fetch-guard.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping, Optional, Union

import httpx
import structlog

from .url_safety import ResolvedTarget, resolve_external_target

log = structlog.get_logger(__name__)

# A chain longer than this is a loop or a stall, not a moved document.
DEFAULT_MAX_REDIRECTS = 5

# A fetched document is served by whoever scraped content pointed us at, so its
# size is theirs to choose and ours to bound. Measured after decompression.
DEFAULT_MAX_BYTES = 16 * 1024 * 1024

# A guard judges one URL and returns the address to connect to, or None to
# refuse it. It is async because judging a name means resolving it, and callers
# hang their own checks - rate limit, robots.txt, length bound - off the same
# call so every hop pays them, not just the first.
Guard = Callable[[str], Awaitable[Optional[ResolvedTarget]]]


@dataclass(frozen=True)
class FetchFailure:
    """Why one fetch produced no body.

    reason is short and written for an operator, because it ends up in
    sources.health_error where an analyst reads it. A log line alone is not
    enough: the analyst debugging a dead source does not have the worker log.
    """

    url: str
    reason: str
    status: Optional[int] = None


@dataclass(frozen=True)
class FetchResult:
    """One fetched response, after every redirect hop was validated.

    url is the address the body actually came from, which is the last hop rather
    than the one the caller asked for.
    """

    url: str
    status: int
    body: bytes
    encoding: Optional[str]
    headers: Mapping[str, str]


def _build_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    address: Optional[str],
) -> httpx.Request:
    """Build a request aimed at the approved address, still named for its host.

    The address goes in the URL so no second lookup happens, the name goes in
    the Host header so the server still serves the right site, and the name goes
    in sni_hostname so TLS is negotiated and the certificate verified against the
    name rather than against the address.

    The name is taken in its ASCII form. `host` hands back the unicode form of an
    internationalised name, which CPython would then re-encode with a different
    IDNA codec than the one httpx used, so the two can disagree about what was
    requested and about what the certificate has to match.
    """
    parsed = httpx.URL(url)
    if address is None or address == parsed.host:
        return client.build_request(method, parsed)
    return client.build_request(
        method,
        parsed.copy_with(host=address),
        headers={"Host": parsed.netloc.decode("ascii")},
        extensions={"sni_hostname": parsed.raw_host.decode("ascii")},
    )


async def _read_bounded(resp: httpx.Response, url: str, limit: int) -> Optional[bytes]:
    """Read a streamed response up to limit, measured after decompression.

    A small compressed response that expands without limit is refused rather
    than buffered, which ``resp.read()`` would have already done by the time
    anything could object.
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > limit:
            log.warning("net.response_too_large", url=url, limit=limit, read_bytes=total)
            return None
        chunks.append(chunk)
    return b"".join(chunks)


async def fetch(
    url: str,
    *,
    timeout: float,
    method: str = "GET",
    headers: Optional[Mapping[str, str]] = None,
    guard: Optional[Guard] = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    limit: int = DEFAULT_MAX_BYTES,
    expect_ok: bool = True,
    proxy: Optional[str] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Union[FetchResult, FetchFailure]:
    """Fetch url, validating the destination at every hop.

    guard defaults to the resolved SSRF check. A caller with more to say about a
    URL - a rate limit, robots.txt, a length bound - passes its own, and that
    check then runs on every hop rather than only on the first.

    expect_ok=False returns the response for a 4xx or 5xx rather than refusing
    it, for a caller that reads the status as an answer.

    Failure is a FetchFailure carrying a reason, never an exception: a page we
    could not fetch is a degraded item, not a failed job. The reason is returned
    as well as logged, because a caller that shows the operator why a source is
    dead cannot read the worker's log.
    """
    guard = guard or resolve_external_target

    client_kwargs: dict = {
        "timeout": timeout,
        # Never the client's decision. A client following a redirect picks the
        # final host on its own, which is the hole this module exists to close.
        "follow_redirects": False,
        "headers": dict(headers or {}),
        # A pinned request is addressed to an IP, so a pooled connection is
        # keyed on that IP and would be reused across a redirect to a second
        # name sharing it - sending the second Host down a connection whose
        # certificate was checked against the first. One hop, one connection.
        "limits": httpx.Limits(max_keepalive_connections=0),
    }
    if transport is not None:
        client_kwargs["transport"] = transport
        if proxy:
            # A transport is mounted ahead of the proxy, so the fetch would
            # leave directly. Saying so beats a dark web fetch quietly going
            # out over clearnet.
            log.warning("net.proxy_ignored", url=url, reason="an explicit transport was passed")
    elif proxy:
        client_kwargs["proxy"] = proxy

    # The proxy resolves the name and makes the connection, so an address pinned
    # here would be an address handed to the proxy to connect to. That is a
    # footgun rather than a control: it is the pairing of a resolving guard with
    # a proxy, refused structurally rather than left to each caller to get right.
    pin = not proxy

    current = url
    async with httpx.AsyncClient(**client_kwargs) as client:
        for _ in range(max_redirects + 1):
            try:
                target = await guard(current)
            except Exception as exc:
                # A guard runs a caller's own checks, and one of those failing
                # is not a reason to fail the job that asked for the page.
                log.warning("net.guard_failed", url=current, error=str(exc))
                return FetchFailure(url=current, reason=f"address check failed: {exc}"[:200])
            if target is None:
                # The guard logged which of its checks refused.
                return FetchFailure(url=current, reason="address refused by the fetch guard")

            addresses: list[Optional[str]] = [target.address, *target.alternates] if pin else [None]
            resp = None
            last_error = ""
            for address in addresses:
                try:
                    resp = await client.send(
                        _build_request(client, method, current, address), stream=True
                    )
                    break
                except Exception as exc:
                    # Every address here passed the same check, so an unreachable
                    # one is a retry rather than a refusal. A client resolving the
                    # name itself would have tried them all too.
                    last_error = str(exc)
                    log.warning("net.fetch_failed", url=current, address=address, error=last_error)
            if resp is None:
                return FetchFailure(url=current, reason=last_error[:200] or "transport failure")

            try:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        log.warning("net.redirect_without_location", url=current)
                        return FetchFailure(
                            url=current,
                            reason=f"HTTP {resp.status_code} with no Location header",
                            status=resp.status_code,
                        )
                    # Joined against the name, not against the pinned address,
                    # so a relative Location resolves the way the server meant.
                    current = str(httpx.URL(current).join(location))
                    continue
                if expect_ok and resp.status_code >= 400:
                    log.warning("net.fetch_status", url=current, status=resp.status_code)
                    return FetchFailure(
                        url=current,
                        reason=f"HTTP {resp.status_code}",
                        status=resp.status_code,
                    )
                body = await _read_bounded(resp, current, limit)
                if body is None:
                    return FetchFailure(
                        url=current,
                        reason=f"response past the {limit} byte bound",
                        status=resp.status_code,
                    )
                return FetchResult(
                    url=current,
                    status=resp.status_code,
                    body=body,
                    encoding=resp.encoding,
                    headers=resp.headers,
                )
            except Exception as exc:
                log.warning("net.fetch_failed", url=current, error=str(exc))
                return FetchFailure(url=current, reason=str(exc)[:200] or "read failure")
            finally:
                await resp.aclose()

    log.warning("net.redirect_chain_too_long", url=url, limit=max_redirects, last=current)
    return FetchFailure(url=current, reason=f"redirect chain longer than {max_redirects} hops")


async def fetch_bytes(url: str, *, timeout: float, **kwargs) -> Optional[FetchResult]:
    """Fetch url through the guarded path. None on any refusal.

    The form for a caller that acts on a body or skips the item. A caller that
    tells an operator why a source is dead wants fetch, which says what failed.
    """
    outcome = await fetch(url, timeout=timeout, **kwargs)
    return outcome if isinstance(outcome, FetchResult) else None


async def fetch_text(url: str, *, timeout: float, **kwargs) -> Optional[str]:
    """Fetch url and decode it, using the encoding the response declared."""
    result = await fetch_bytes(url, timeout=timeout, **kwargs)
    if result is None:
        return None
    return result.body.decode(result.encoding or "utf-8", errors="replace")
