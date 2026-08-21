"""Per-domain HTTP rate limiter — asyncio-based.

Enforces a minimum gap between consecutive HTTP requests to the same domain.
Used by the scraper to avoid WAF/rate-limit blocks when following article links.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from urllib.parse import urlparse

import structlog

from .settings import settings

log = structlog.get_logger(__name__)


class DomainRateLimiter:
    """Enforce minimum gap between requests to the same domain.

    Per-domain asyncio.Lock ensures concurrent requests to the same domain
    are serialized. Different domains run in parallel.
    """

    def __init__(self) -> None:
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def wait(self, url: str) -> None:
        """Wait if needed before making a request to url's domain."""
        domain = self._domain(url)
        async with self._locks[domain]:
            now = time.monotonic()
            last = self._last_request.get(domain, 0.0)
            gap = settings.scraper_per_domain_delay_s
            jitter = random.uniform(
                -settings.scraper_per_domain_jitter_s,
                settings.scraper_per_domain_jitter_s,
            )
            delay = gap + jitter - (now - last)
            if delay > 0:
                log.debug(
                    "scraper.domain_rate_limit",
                    domain=domain,
                    delay_s=round(delay, 2),
                )
                await asyncio.sleep(delay)
            self._last_request[domain] = time.monotonic()
