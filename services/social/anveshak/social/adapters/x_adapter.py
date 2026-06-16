"""X/Twitter adapter — M3 (criteria 3.20–3.26).

SPEND GUARD IS CRITICAL.
X API charges $0.005 per read. XSpendGuard atomically enforces the monthly cap
using a Redis counter keyed by calendar month. It hard-stops ALL X API calls
when the cap is reached — never exceeded silently (criteria 3.22, 3.30).

Monthly reset is automatic: the counter key includes {YYYY-MM}, so a new
month produces a fresh key with a TTL set to the seconds remaining in the month
(criteria 3.24).

XPollingAdapter:  default mode — tweepy recent search, 15-min intervals
XStreamAdapter:   raises NotImplementedError (Enterprise API required, criteria 3.26)
make_x_adapter(): factory that returns the correct class by settings.x_adapter_mode
"""
from __future__ import annotations

import calendar
from datetime import datetime, UTC
from typing import AsyncIterator

import structlog
import tweepy
import tweepy.asynchronous
from arq import ArqRedis

from .base import (
    AdapterAuthError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)
from ..settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Spend Guard — Redis atomic counter (criteria 3.22–3.24)
# ---------------------------------------------------------------------------

def _monthly_key() -> str:
    """Redis key for the current month's X read counter."""
    return f"anveshak:x:monthly_reads:{datetime.now(UTC).strftime('%Y-%m')}"


def _seconds_until_month_end() -> int:
    """Seconds from now until midnight on the 1st of next month (UTC)."""
    now = datetime.now(UTC)
    last_day = calendar.monthrange(now.year, now.month)[1]
    # First second of next month
    if now.month == 12:
        next_month_start = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month_start = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return max(1, int((next_month_start - now).total_seconds()))


class XSpendGuard:
    """Atomic spend guard backed by Redis Lua script.

    check_and_increment() must be called BEFORE every X API call.
    Returns True  → under cap, call is permitted, counter incremented.
    Returns False → at or above cap, call is BLOCKED, warning logged.

    Uses a Lua script for true atomicity — no race window between
    INCR and cap check that could allow concurrent calls to overshoot.
    """

    # Lua script: atomically check cap, increment if under, set TTL on first use.
    # Returns new count on success, -1 if at/over cap.
    _LUA_CHECK_AND_INCREMENT = """\
local key = KEYS[1]
local cap = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current >= cap then
    return -1
end
local new_count = redis.call('INCR', key)
if new_count == 1 then
    redis.call('EXPIRE', key, ttl)
end
if new_count > cap then
    redis.call('DECR', key)
    return -1
end
return new_count
"""

    def __init__(self, redis: ArqRedis, cap: int) -> None:
        self._redis = redis
        self._cap = cap

    async def check_and_increment(self) -> bool:
        """Atomically increment and check monthly cap via Lua script.

        The entire check-increment-TTL sequence runs as a single atomic
        Redis operation. Concurrent calls cannot race past the cap.
        """
        key = _monthly_key()
        ttl = _seconds_until_month_end()

        result = int(await self._redis.eval(
            self._LUA_CHECK_AND_INCREMENT, 1, key, self._cap, ttl
        ))

        if result == -1:
            log.warning(
                "x.spend_guard.cap_reached",
                cap=self._cap,
                key=key,
            )
            return False

        if result == 1:
            log.info("x.spend_guard.month_started", cap=self._cap, ttl_seconds=ttl)

        log.debug("x.spend_guard.ok", monthly_reads=result, cap=self._cap)
        return True

    async def current_count(self) -> int:
        """Read current monthly count without incrementing (for health checks)."""
        val = await self._redis.get(_monthly_key())
        return int(val) if val else 0


# ---------------------------------------------------------------------------
# X Polling Adapter (criteria 3.20–3.25)
# ---------------------------------------------------------------------------

class XPollingAdapter(SourceAdapterBase):
    """Polls Twitter/X recent search API.

    Pay-per-use: $0.005/read. spend_guard is called before every API request.
    source_handles are ignored (X recent search is keyword-based, not account-based).
    """

    adapter_id = "x-polling-v1"
    platform = "twitter"
    adapter_version = "1.0.0"

    def __init__(self, redis: ArqRedis) -> None:
        self._client: tweepy.asynchronous.AsyncClient | None = None
        self._spend_guard: XSpendGuard | None = None
        self._redis = redis

    # ------------------------------------------------------------------
    # SourceAdapterBase implementation
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Initialise tweepy AsyncClient from bearer token (criteria 3.20)."""
        if not settings.x_adapter_enabled:
            log.warning("social.adapter_disabled", adapter=self.adapter_id,
                        hint="Set X_ADAPTER_ENABLED=true to activate")
            return
        if not settings.x_bearer_token:
            raise AdapterAuthError(
                "X adapter enabled but X_BEARER_TOKEN not set"
            )
        if settings.x_adapter_mode != "polling":
            raise ValueError(
                f"XPollingAdapter called with mode={settings.x_adapter_mode}"
            )
        self._client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.x_bearer_token,
            wait_on_rate_limit=False,   # we manage rate limit ourselves
        )
        self._spend_guard = XSpendGuard(self._redis, settings.x_monthly_read_cap)
        log.info("x.authenticated", mode="polling", cap=settings.x_monthly_read_cap)

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Search recent tweets for topic keywords (criteria 3.21)."""
        if self._client is None or self._spend_guard is None:
            log.warning("x.adapter.not_authenticated")
            return

        query = " OR ".join(f'"{kw}"' for kw in topic_keywords if kw)
        if not query:
            return

        # SPEND GUARD — must check before every API call (criteria 3.22, 3.30)
        allowed = await self._spend_guard.check_and_increment()
        if not allowed:
            return   # hard stop — no API call made (criteria 3.30)

        try:
            response = await self._client.search_recent_tweets(
                query=f"{query} -is:retweet lang:en",
                max_results=10,
                tweet_fields=["created_at", "lang", "author_id"],
            )
        except tweepy.TooManyRequests as exc:
            raise AdapterRateLimitError("X API rate limit hit") from exc
        except tweepy.Unauthorized as exc:
            raise AdapterAuthError(f"X bearer token rejected: {exc}") from exc
        except tweepy.TweepyException as exc:
            log.warning("x.search_error", error=str(exc))
            return

        if not response.data:
            return

        for tweet in response.data:
            yield RawItem(
                raw_text=tweet.text,
                url=f"https://x.com/i/web/status/{tweet.id}",
                platform=self.platform,
                captured_at=tweet.created_at or datetime.now(UTC),
                source_handle=settings.x_bearer_token[:8] + "...",  # anonymised
                language=tweet.lang if hasattr(tweet, "lang") else None,
            )

    async def health(self) -> dict:
        now = datetime.now(UTC).isoformat()
        if self._client is None:
            return {"status": "DOWN", "checked_at": now}
        count = await self._spend_guard.current_count() if self._spend_guard else 0
        remaining = max(0, settings.x_monthly_read_cap - count)
        status = "HEALTHY" if remaining > 0 else "DEGRADED"
        return {
            "status": status,
            "checked_at": now,
            "monthly_reads_used": count,
            "monthly_reads_remaining": remaining,
            "cap": settings.x_monthly_read_cap,
        }


# ---------------------------------------------------------------------------
# X Stream Adapter — Enterprise API only (criteria 3.26)
# ---------------------------------------------------------------------------

class XStreamAdapter(SourceAdapterBase):
    """Real-time filtered stream — requires X Enterprise API contract."""

    adapter_id = "x-stream-v1"
    platform = "twitter"
    adapter_version = "1.0.0"

    async def authenticate(self) -> None:
        raise NotImplementedError(
            "X filtered stream requires Enterprise API access. "
            "Contact X Corp to negotiate a contract post-award. "
            "See hardware.md for upgrade path."
        )

    async def collect(self, topic_keywords, source_handles, topic_id):  # type: ignore[override]
        raise NotImplementedError("Enterprise API required")
        return  # unreachable — satisfies AsyncIterator typing
        yield

    async def health(self) -> dict:
        return {
            "status": "DOWN",
            "checked_at": datetime.now(UTC).isoformat(),
            "reason": "XStreamAdapter requires Enterprise API — not implemented",
        }


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def make_x_adapter(redis: ArqRedis) -> SourceAdapterBase:
    """Return the correct X adapter based on settings.x_adapter_mode."""
    mode = settings.x_adapter_mode
    if mode == "polling":
        return XPollingAdapter(redis)
    if mode == "stream":
        return XStreamAdapter()
    raise ValueError(f"Unknown x_adapter_mode: {mode!r}. Expected 'polling' or 'stream'.")
