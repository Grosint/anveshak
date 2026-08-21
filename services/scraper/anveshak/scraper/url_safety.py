"""SSRF protection — validate URLs before downloading media.

Blocks requests to private/internal/loopback/link-local addresses and
non-HTTP schemes. Used by _download_page_media() to prevent
attacker-controlled HTML from reaching internal services.
"""

from __future__ import annotations

import ipaddress
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
