"""Source health check logic for the daily check_all_source_health ARQ job.

Health status transitions:
  0 consecutive failures  → healthy
  1–2 failures            → degraded
  3+ failures             → down
  New / non-HTTP source   → unverified (unchanged)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from .fetch import fetch_url
from .settings import settings

log = structlog.get_logger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_PAYWALL_PATTERNS = frozenset({
    "subscribe", "paywall", "premium content",
    "sign in to read", "create an account", "subscribers only",
})

SQL_GET_ALL_ACTIVE_SOURCES = """
    SELECT id, url_or_handle, platform, consecutive_failures
    FROM sources
    WHERE is_active = TRUE AND platform IN ('rss', 'web')
"""

SQL_UPDATE_HEALTH = """
    UPDATE sources
    SET health_status        = $2,
        consecutive_failures = $3,
        health_error         = $4,
        last_checked_at      = NOW(),
        updated_at           = NOW()
    WHERE id = $1
"""


@dataclass
class HealthResult:
    status: str           # healthy | degraded | down
    error: Optional[str]  # None when healthy


async def check_rss_health(url: str) -> HealthResult:
    """Fetch feed XML and verify at least one entry is parseable."""
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        import asyncio
        import feedparser  # lazy — only imported in scraper worker

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, resp.content)

        if not feed.entries:
            return HealthResult("degraded", "Feed reachable but contains no entries")
        return HealthResult("healthy", None)

    except httpx.HTTPStatusError as exc:
        return HealthResult("degraded", f"HTTP {exc.response.status_code}")
    except Exception as exc:
        return HealthResult("degraded", str(exc)[:200])


async def check_web_health(url: str) -> HealthResult:
    """Fetch the page and check for paywall indicators or empty content."""
    try:
        text = await fetch_url(url)
        if not text:
            return HealthResult("degraded", "Fetch returned no content — may be blocked or paywalled")
        if len(text) < 200:
            return HealthResult("degraded", f"Content too short ({len(text)} chars) — possible paywall")
        lower = text.lower()
        for pattern in _PAYWALL_PATTERNS:
            if pattern in lower:
                return HealthResult("degraded", f"Possible paywall detected: '{pattern}' found in content")
        return HealthResult("healthy", None)
    except Exception as exc:
        return HealthResult("degraded", str(exc)[:200])


def _next_status(result: HealthResult, prev_failures: int) -> tuple[str, int]:
    """Compute new health_status and consecutive_failures from a check result."""
    if result.status == "healthy":
        return "healthy", 0
    failures = prev_failures + 1
    return ("down" if failures >= 3 else "degraded"), failures


async def run_all_health_checks(db_pool) -> int:
    """Check every active web/rss source. Returns count of sources checked."""
    import asyncio

    async with db_pool.acquire() as conn:
        sources = await conn.fetch(SQL_GET_ALL_ACTIVE_SOURCES)

    checked = 0
    for source in sources:
        source_id: str = source["id"]
        url: str = source["url_or_handle"]
        platform: str = source["platform"]
        prev_failures: int = source["consecutive_failures"]

        try:
            if platform == "rss":
                result = await check_rss_health(url)
            else:
                result = await check_web_health(url)

            new_status, new_failures = _next_status(result, prev_failures)

            async with db_pool.acquire() as conn:
                await conn.execute(
                    SQL_UPDATE_HEALTH,
                    source_id, new_status, new_failures, result.error,
                )

            log.info(
                "health.source_checked",
                source_id=source_id,
                platform=platform,
                status=new_status,
                failures=new_failures,
            )
            checked += 1

        except Exception as exc:
            log.warning("health.check_error", source_id=source_id, error=str(exc))

        # Stagger checks — one per second to avoid hammering sources
        await asyncio.sleep(1)

    return checked
