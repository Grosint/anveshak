"""Bluesky adapter — M3 (criteria 3.17–3.19).

Uses atproto SDK. Searches posts via app.bsky.feed.searchPosts for each topic keyword.
Bluesky's API is public-read with password auth for search endpoints.

BlueskyQuotaGuard: atomic Redis INCR counter for daily API call cap (7200/day).
Mirrors XSpendGuard pattern — see learned/redis-atomic-budget-guard.md.
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import AsyncIterator

import structlog
from arq import ArqRedis
from atproto import AsyncClient
from atproto_client.exceptions import AtProtocolError

from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)
from ..settings import settings

log = structlog.get_logger(__name__)

_MAX_RESULTS_PER_KEYWORD = 25


# ---------------------------------------------------------------------------
# Quota Guard — Redis atomic counter (daily cap)
# ---------------------------------------------------------------------------

def _daily_key() -> str:
    """Redis key for the current day's Bluesky call counter."""
    return f"anveshak:bluesky:daily_calls:{datetime.now(UTC).strftime('%Y-%m-%d')}"


def _seconds_until_day_end() -> int:
    """Seconds from now until midnight UTC."""
    now = datetime.now(UTC)
    tomorrow = datetime(now.year, now.month, now.day, tzinfo=UTC)
    tomorrow = tomorrow.replace(day=now.day) + __import__("datetime").timedelta(days=1)
    return max(1, int((tomorrow - now).total_seconds()))


class BlueskyQuotaGuard:
    """Atomic quota guard backed by Redis INCR.

    check_and_increment() must be called BEFORE every Bluesky API call.
    Returns True  → under cap, call is permitted, counter incremented.
    Returns False → at or above cap, call is BLOCKED, warning logged.

    Daily reset is automatic: the counter key includes {YYYY-MM-DD},
    so a new day produces a fresh key with TTL set to seconds until midnight.
    """

    def __init__(self, redis: ArqRedis, cap: int) -> None:
        self._redis = redis
        self._cap = cap

    async def check_and_increment(self) -> bool:
        """Atomically increment and check daily cap."""
        key = _daily_key()
        new_count = await self._redis.incr(key)

        if new_count == 1:
            ttl = _seconds_until_day_end()
            await self._redis.expire(key, ttl)
            log.info("bluesky.quota_guard.day_started", cap=self._cap, ttl_seconds=ttl)

        if new_count > self._cap:
            await self._redis.decr(key)
            log.warning(
                "bluesky.quota_guard.cap_reached",
                daily_calls=new_count - 1,
                cap=self._cap,
                key=key,
            )
            return False

        log.debug("bluesky.quota_guard.ok", daily_calls=new_count, cap=self._cap)
        return True

    async def current_count(self) -> int:
        """Read current daily count without incrementing (for health checks)."""
        val = await self._redis.get(_daily_key())
        return int(val) if val else 0


class BlueskyAdapter(SourceAdapterBase):
    """Searches Bluesky posts by topic keywords.

    Unlike Telegram/Reddit which monitor specific channels/subreddits,
    Bluesky adapter runs keyword searches across the entire network.
    source_handles are ignored (no per-handle filtering in Bluesky search).
    The source_handle in yielded RawItems uses the poster's handle.
    """

    adapter_id = "bluesky-v1"
    platform = "bluesky"
    adapter_version = "1.0.0"

    def __init__(self, quota_guard: BlueskyQuotaGuard | None = None) -> None:
        self._client: AsyncClient | None = None
        self._my_did: str | None = None
        self._quota_guard = quota_guard

    # ------------------------------------------------------------------
    # SourceAdapterBase implementation
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Login with handle + password from settings (criteria 3.17)."""
        if not settings.bluesky_adapter_enabled:
            log.warning("social.adapter_disabled", adapter=self.adapter_id,
                        hint="Set BLUESKY_ADAPTER_ENABLED=true to activate")
            return
        if not settings.bluesky_handle or not settings.bluesky_password:
            raise AdapterAuthError(
                "Bluesky adapter enabled but BLUESKY_HANDLE / BLUESKY_PASSWORD not set"
            )
        try:
            self._client = AsyncClient()
            profile = await self._client.login(
                settings.bluesky_handle, settings.bluesky_password
            )
            self._my_did = profile.did
            log.info("bluesky.authenticated", handle=settings.bluesky_handle)
        except AtProtocolError as exc:
            raise AdapterAuthError(f"Bluesky authentication failed: {exc}") from exc

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Search Bluesky for each topic keyword (criteria 3.18)."""
        if self._client is None:
            log.warning("bluesky.adapter.not_authenticated")
            return

        seen_uris: set[str] = set()

        for keyword in topic_keywords:
            # Enforce daily quota before each API call
            if self._quota_guard and not await self._quota_guard.check_and_increment():
                log.warning("bluesky.quota_exhausted", keyword=keyword)
                return

            try:
                response = await self._client.app.bsky.feed.search_posts(
                    params={"q": keyword, "limit": _MAX_RESULTS_PER_KEYWORD}
                )
            except AtProtocolError as exc:
                if "RateLimitExceeded" in str(exc):
                    raise AdapterRateLimitError(f"Bluesky rate limit: {exc}") from exc
                log.warning("bluesky.search_error", keyword=keyword, error=str(exc))
                continue

            for post in response.posts:
                uri = post.uri  # at://did:plc:.../app.bsky.feed.post/rkey
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)

                text = post.record.text if hasattr(post.record, "text") else ""
                if not text:
                    continue

                url = self._uri_to_url(uri, post.author.handle)
                yield RawItem(
                    raw_text=text,
                    url=url,    # criteria 3.19
                    platform=self.platform,
                    captured_at=self._parse_indexed_at(post.indexed_at),
                    source_handle=settings.bluesky_handle,  # registered source handle
                    media_urls=self._extract_media_urls(post),
                )

    async def refresh_credentials(self) -> bool:
        """Re-authenticate with Bluesky handle + password."""
        try:
            await self.authenticate()
            log.info("bluesky.credentials_refreshed")
            return True
        except AdapterAuthError as exc:
            log.warning("bluesky.refresh_failed", error=str(exc))
            return False

    async def health(self) -> dict:
        if self._client is None:
            return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
        try:
            await self._client.app.bsky.feed.search_posts(
                params={"q": "test", "limit": 1}
            )
            return {"status": "HEALTHY", "checked_at": datetime.now(UTC).isoformat()}
        except Exception as exc:
            return {
                "status": "DEGRADED",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uri_to_url(uri: str, author_handle: str) -> str:
        """Convert AT URI to human-readable bsky.app URL (criteria 3.19).

        at://did:plc:xyz.../app.bsky.feed.post/rkey
            → https://bsky.app/profile/{handle}/post/{rkey}
        """
        rkey = uri.split("/")[-1]
        return f"https://bsky.app/profile/{author_handle}/post/{rkey}"

    @staticmethod
    def _parse_indexed_at(indexed_at: str) -> datetime:
        """Parse ISO 8601 timestamp from Bluesky API."""
        try:
            return datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return datetime.now(UTC)

    @staticmethod
    def _extract_media_urls(post) -> list[str]:
        """Extract image URLs from post embed for Phase 4 media ingestion."""
        urls: list[str] = []
        try:
            embed = post.record.embed
            if embed and hasattr(embed, "images"):
                for img in embed.images:
                    if hasattr(img, "image") and hasattr(img.image, "ref"):
                        cid = img.image.ref.link
                        did = post.author.did
                        urls.append(
                            f"https://bsky.social/xrpc/com.atproto.sync.getBlob"
                            f"?did={did}&cid={cid}"
                        )
        except Exception:
            pass
        return urls
