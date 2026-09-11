"""SSRF protection — validate URLs before fetching attacker-supplied addresses.

Blocks requests to private/internal/loopback/link-local addresses and
non-HTTP schemes. Used wherever scraped content chooses the address: media
URLs found in a page, and article links found in a feed.

Two checks, because one is not enough. validate_external_url reads the URL as
written, which settles a literal address or a known-dangerous name. It cannot
settle a name, and inside a compose deployment the dangerous addresses all have
names: a link to http://ollama:11434/ is a plain hostname that passes every
literal check and reaches an internal port. validate_external_url_resolved adds
the DNS answer to the judgement, which is what a name actually means.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import structlog

log = structlog.get_logger(__name__)

# Hostnames that must always be blocked regardless of DNS resolution
_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.aws.internal",
        "169.254.169.254",
    }
)


def validate_external_url(url: str) -> bool:
    """Return True if url points to an external, non-private host via HTTP(S).

    Blocks:
    - Non-HTTP schemes (ftp://, file://, data:, etc.)
    - Loopback addresses (127.x.x.x, ::1)
    - Private ranges (10.x, 172.16-31.x, 192.168.x)
    - Link-local (169.254.x.x, fe80::)
    - Cloud metadata endpoints
    - Empty / malformed URLs
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Check blocked hostnames
    if hostname in _BLOCKED_HOSTNAMES:
        log.warning("scraper.ssrf_blocked", url=url, reason="blocked_hostname")
        return False

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            log.warning("scraper.ssrf_blocked", url=url, reason="private_ip")
            return False
        # Also block 0.0.0.0
        # SSRF blocklist; this blocks the address, it does not bind it
        if ip == ipaddress.ip_address("0.0.0.0"):  # nosec B104
            log.warning("scraper.ssrf_blocked", url=url, reason="zero_address")
            return False
    except ValueError:
        # Not an IP — it's a hostname, which is fine (DNS resolution
        # happens later in httpx, and Docker network names resolve to
        # private IPs, but we can't check that without DNS lookup here.
        # The hostname blocklist above catches known dangerous names.)
        pass

    return True


def _is_internal_address(raw: str) -> bool:
    """Return True if raw is an address inside the deployment or the host."""
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return False
    # unspecified covers 0.0.0.0 and ::, which route to the local host.
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified
    )


async def _resolve_host(hostname: str) -> list[str]:
    """Return every address a hostname resolves to, or [] when it resolves to none."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        log.warning("scraper.ssrf_resolve_failed", hostname=hostname, error=str(exc))
        return []
    return [str(info[4][0]) for info in infos]


async def validate_external_url_resolved(url: str) -> bool:
    """Return True if url is external once its hostname has been resolved.

    Deny by default in both directions: a name that resolves to nothing is
    refused, and a name answering with any internal address is refused even if
    it also answers with a public one, because we do not choose which answer the
    client will use.

    This narrows the window rather than closing it. The address is resolved here
    and again by the HTTP client, so a name whose answer changes between the two
    can still be fetched, and a redirect chooses its own host entirely. Egress
    policy is what closes those; this refuses the direct attempt.
    """
    if not validate_external_url(url):
        return False

    # Resolution is run for a literal address too, where it returns the address
    # itself. That keeps one judgement path, and catches the literals the
    # written-form check does not enumerate, such as the unspecified address.
    addresses = await _resolve_host(urlparse(url).hostname or "")
    if not addresses:
        log.warning("scraper.ssrf_blocked", url=url, reason="unresolvable_host")
        return False

    internal = [addr for addr in addresses if _is_internal_address(addr)]
    if internal:
        log.warning(
            "scraper.ssrf_blocked",
            url=url,
            reason="resolves_to_internal_address",
            addresses=internal,
        )
        return False

    return True
