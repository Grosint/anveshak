"""SSRF protection — validate URLs before fetching attacker-supplied addresses.

Blocks requests to private/internal/loopback/link-local addresses and
non-HTTP schemes. Used wherever scraped content chooses the address: media
URLs found in a page, and article links found in a feed.

Two checks, because one is not enough. validate_external_url reads the URL as
written, which settles a literal address or a known-dangerous name. It cannot
settle a name, and inside a compose deployment the dangerous addresses all have
names: a link to http://ollama:11434/ is a plain hostname that passes every
literal check and reaches an internal port. resolve_external_target adds the DNS
answer to the judgement, which is what a name actually means, and returns the
address it approved so the fetch connects to that one rather than resolving the
name a second time.

The judgement is one address at one moment, so it only holds if the request that
leaves carries it. `safe_fetch` is that path: it validates every redirect hop and
connects to the address returned here.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
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


@dataclass(frozen=True)
class ResolvedTarget:
    """Every address approved for one URL, at the moment it was resolved.

    address is the one the connection is made to. None means the caller could
    not resolve the name and must not pin one: a proxied fetch resolves at the
    proxy, and a .onion name has no address on this side of it.

    alternates are the other answers, every one of them judged by the same
    check. A multi-homed host whose first address is unreachable is a retry
    rather than a failed fetch, which is what a client resolving the name for
    itself would have done.
    """

    url: str
    hostname: str
    address: Optional[str]
    alternates: tuple[str, ...] = ()


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
        log.warning("net.ssrf_blocked", url=url, reason="blocked_hostname")
        return False

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            log.warning("net.ssrf_blocked", url=url, reason="private_ip")
            return False
        # Also block 0.0.0.0
        # SSRF blocklist; this blocks the address, it does not bind it
        if ip == ipaddress.ip_address("0.0.0.0"):  # nosec B104
            log.warning("net.ssrf_blocked", url=url, reason="zero_address")
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
        log.warning("net.ssrf_resolve_failed", hostname=hostname, error=str(exc))
        return []
    return [str(info[4][0]) for info in infos]


async def resolve_external_target(url: str) -> Optional[ResolvedTarget]:
    """Return the address to connect to for url, or None if it is not external.

    Deny by default in both directions: a name that resolves to nothing is
    refused, and a name answering with any internal address is refused even if
    it also answers with a public one, because we do not choose which answer a
    resolver would hand a client.

    The address is returned rather than discarded so the caller connects to the
    one that was judged. A name resolved here and again by the client is two
    answers, and an attacker who controls the zone chooses the second; there is
    no window if there is only one answer.
    """
    if not validate_external_url(url):
        return None

    hostname = urlparse(url).hostname or ""

    # A .onion name has no clearnet address, so resolving one asks a clearnet
    # resolver about a hidden service. That is the DNS leak the dark web path
    # exists to avoid, and it must not depend on the caller having picked the
    # proxied guard. Refused here, before anything is sent to a resolver.
    if hostname.endswith(".onion"):
        log.warning("net.ssrf_blocked", url=url, reason="onion_name_needs_the_tor_path")
        return None

    # Resolution is run for a literal address too, where it returns the address
    # itself. That keeps one judgement path, and catches the literals the
    # written-form check does not enumerate, such as the unspecified address.
    addresses = await _resolve_host(hostname)
    if not addresses:
        log.warning("net.ssrf_blocked", url=url, reason="unresolvable_host")
        return None

    internal = [addr for addr in addresses if _is_internal_address(addr)]
    if internal:
        log.warning(
            "net.ssrf_blocked",
            url=url,
            reason="resolves_to_internal_address",
            addresses=internal,
        )
        return None

    return ResolvedTarget(
        url=url,
        hostname=hostname,
        address=addresses[0],
        alternates=tuple(addresses[1:]),
    )


async def validate_external_url_resolved(url: str) -> bool:
    """Return True if url is external once its hostname has been resolved.

    The boolean form, for a caller deciding whether to proceed rather than
    issuing the request itself. A caller that fetches wants
    resolve_external_target, so the address it judged is the address it uses.
    """
    return await resolve_external_target(url) is not None
