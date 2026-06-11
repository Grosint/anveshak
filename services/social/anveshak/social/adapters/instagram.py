"""Instagram adapter — Engine C Step 5.

Uses Instagrapi (unofficial Meta API). Two collection modes:
  - Profile monitoring: fetch recent posts from registered handles
  - Hashtag search: search posts by hashtag (conservative rate limits)
Bio extraction: profile bio text → feed through Engine C for identifiers.

Circuit breaker: threshold=10 (Meta API is flaky), cooldown=86400s (24h bans).
Rate limiting: 100 requests/hour via Redis atomic counter.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import AsyncIterator

import structlog
from arq import ArqRedis

from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)
from ..settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Circuit breaker params — higher threshold + longer cooldown for Meta
# ---------------------------------------------------------------------------

INSTAGRAM_CIRCUIT_BREAKER_THRESHOLD = 10
INSTAGRAM_CIRCUIT_BREAKER_COOLDOWN_S = 86400  # 24 hours

_MAX_POSTS_PER_PROFILE = 20
_MAX_POSTS_PER_HASHTAG = 25


# ---------------------------------------------------------------------------
# Rate limit guard — 100 requests/hour via Redis atomic counter
# ---------------------------------------------------------------------------

def _hourly_key() -> str:
    """Redis key for current hour's Instagram call counter."""
    return f"anveshak:instagram:hourly_calls:{datetime.now(UTC).strftime('%Y-%m-%d-%H')}"


def _seconds_until_hour_end() -> int:
    """Seconds from now until the next hour boundary."""
    now = datetime.now(UTC)
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    next_hour = next_hour + timedelta(hours=1)
    return max(1, int((next_hour - now).total_seconds()))


class InstagramRateLimitGuard:
    """Atomic rate limit guard backed by Redis INCR.

    check_and_increment() must be called BEFORE every Instagram API call.
    Returns True  -> under cap, call is permitted, counter incremented.
    Returns False -> at or above cap, call is BLOCKED, warning logged.

    Hourly reset is automatic: counter key includes {YYYY-MM-DD-HH},
    so a new hour produces a fresh key with TTL set to seconds until hour end.
    """

    def __init__(self, redis: ArqRedis, cap: int = 100) -> None:
        self._redis = redis
        self._cap = cap

    async def check_and_increment(self) -> bool:
        """Atomically increment and check hourly cap."""
        key = _hourly_key()
        new_count = await self._redis.incr(key)

        if new_count == 1:
            ttl = _seconds_until_hour_end()
            await self._redis.expire(key, ttl)
            log.info("instagram.rate_limit.hour_started", cap=self._cap, ttl_seconds=ttl)

        if new_count > self._cap:
            await self._redis.decr(key)
            log.warning(
                "instagram.rate_limit.cap_reached",
                hourly_calls=new_count - 1,
                cap=self._cap,
                key=key,
            )
            return False

        log.debug("instagram.rate_limit.ok", hourly_calls=new_count, cap=self._cap)
        return True

    async def current_count(self) -> int:
        """Read current hourly count without incrementing (for health checks)."""
        val = await self._redis.get(_hourly_key())
        return int(val) if val else 0


# ---------------------------------------------------------------------------
# Instagram Adapter
# ---------------------------------------------------------------------------

class InstagramAdapter(SourceAdapterBase):
    """Monitor Instagram profiles and hashtag searches for OSINT content.

    Two collection modes:
      1. Profile monitoring: fetch recent posts from registered profile handles
      2. Hashtag search: search posts by topic keywords as hashtags

    Bio text is extracted on first fetch + periodic refresh and fed through
    Engine C identifier extraction pipeline.
    """

    adapter_id = "instagram-v1"
    platform = "instagram"
    adapter_version = "1.0.0"

    def __init__(self, rate_guard: InstagramRateLimitGuard | None = None) -> None:
        self._client = None  # instagrapi.Client instance
        self._rate_guard = rate_guard

    # ------------------------------------------------------------------
    # SourceAdapterBase implementation
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Login via Instagrapi with username/password or stored session."""
        if not settings.instagram_adapter_enabled:
            log.warning(
                "social.adapter_disabled",
                adapter=self.adapter_id,
                hint="Set INSTAGRAM_ADAPTER_ENABLED=true to activate",
            )
            return

        if not settings.instagram_username or not settings.instagram_password:
            raise AdapterAuthError(
                "Instagram adapter enabled but INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD not set"
            )

        try:
            from instagrapi import Client
            self._client = Client()

            # Load session if path provided (avoids repeated logins)
            session_path = getattr(settings, "instagram_session_path", "")
            if session_path:
                try:
                    self._client.load_settings(session_path)
                    self._client.login(settings.instagram_username, settings.instagram_password)
                    log.info("instagram.session_restored", username=settings.instagram_username)
                except Exception as session_exc:
                    log.info("instagram.session_expired_relogging", error=str(session_exc))
                    self._client = Client()
                    self._client.login(settings.instagram_username, settings.instagram_password)
            else:
                self._client.login(settings.instagram_username, settings.instagram_password)

            log.info("instagram.authenticated", username=settings.instagram_username)
        except Exception as exc:
            self._client = None
            raise AdapterAuthError(f"Instagram authentication failed: {exc}") from exc

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Yield RawItems from profile posts + hashtag searches."""
        if self._client is None:
            log.warning("instagram.adapter.not_authenticated")
            return

        import asyncio

        # Mode 1: Profile monitoring — fetch recent posts from registered handles
        for handle in source_handles:
            normalised = self._normalise_handle(handle)

            if self._rate_guard and not await self._rate_guard.check_and_increment():
                log.warning("instagram.rate_limit_exhausted", handle=normalised)
                return

            try:
                user_info = await asyncio.to_thread(
                    self._client.user_info_by_username, normalised
                )
            except Exception as exc:
                if "login_required" in str(exc).lower():
                    raise AdapterAuthError(f"Instagram session expired: {exc}") from exc
                if "rate" in str(exc).lower() or "429" in str(exc):
                    raise AdapterRateLimitError(f"Instagram rate limited: {exc}") from exc
                log.warning("instagram.profile_error", handle=normalised, error=str(exc))
                continue

            # Extract bio as separate content item
            if user_info.biography:
                yield self._bio_to_raw_item(user_info)

            # Skip private profiles
            if user_info.is_private:
                log.info("instagram.profile_private", handle=normalised)
                continue

            # Fetch recent posts
            if self._rate_guard and not await self._rate_guard.check_and_increment():
                log.warning("instagram.rate_limit_exhausted", handle=normalised)
                return

            try:
                medias = await asyncio.to_thread(
                    self._client.user_medias, user_info.pk, _MAX_POSTS_PER_PROFILE
                )
            except Exception as exc:
                log.warning("instagram.medias_error", handle=normalised, error=str(exc))
                continue

            for media in medias:
                raw = self._media_to_raw_item(media, normalised)
                if raw.raw_text:  # skip empty captions
                    yield raw

        # Mode 2: Hashtag search — search by topic keywords
        for keyword in topic_keywords:
            hashtag = keyword.replace(" ", "").lower()
            if not hashtag:
                continue

            if self._rate_guard and not await self._rate_guard.check_and_increment():
                log.warning("instagram.rate_limit_exhausted", keyword=keyword)
                return

            try:
                medias = await asyncio.to_thread(
                    self._client.hashtag_medias_recent, hashtag, _MAX_POSTS_PER_HASHTAG
                )
            except Exception as exc:
                if "rate" in str(exc).lower() or "429" in str(exc):
                    raise AdapterRateLimitError(f"Instagram rate limited: {exc}") from exc
                log.warning("instagram.hashtag_error", hashtag=hashtag, error=str(exc))
                continue

            for media in medias:
                handle = getattr(media.user, "username", hashtag) if media.user else hashtag
                raw = self._media_to_raw_item(media, handle)
                if raw.raw_text:
                    yield raw

    async def refresh_credentials(self) -> bool:
        """Re-authenticate with Instagram credentials."""
        try:
            await self.authenticate()
            log.info("instagram.credentials_refreshed")
            return True
        except AdapterAuthError as exc:
            log.warning("instagram.refresh_failed", error=str(exc))
            return False

    async def health(self) -> dict:
        """Return adapter health status."""
        if self._client is None:
            return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
        try:
            import asyncio
            await asyncio.to_thread(self._client.account_info)
            result = {"status": "HEALTHY", "checked_at": datetime.now(UTC).isoformat()}
            if self._rate_guard:
                result["hourly_calls_used"] = await self._rate_guard.current_count()
            return result
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
    def _normalise_handle(handle: str) -> str:
        """Normalise Instagram handle: strip @, URL prefix, lowercase.

        Accepts: @ScamSeller, ScamSeller, https://instagram.com/ScamSeller/
        Returns: scamseller
        """
        h = handle.strip().rstrip("/")
        # Strip Instagram URL prefix
        for prefix in ("https://www.instagram.com/", "https://instagram.com/",
                       "http://www.instagram.com/", "http://instagram.com/"):
            if h.lower().startswith(prefix):
                h = h[len(prefix):]
                break
        # Strip @ prefix
        if h.startswith("@"):
            h = h[1:]
        return h.lower()

    @staticmethod
    def _media_to_raw_item(media, source_handle: str) -> RawItem:
        """Convert Instagrapi Media object to RawItem."""
        caption = media.caption_text if hasattr(media, "caption_text") else ""
        if caption is None:
            caption = ""
        shortcode = media.code if hasattr(media, "code") else ""

        # Parse timestamp
        taken_at = media.taken_at if hasattr(media, "taken_at") else None
        if isinstance(taken_at, (int, float)):
            captured_at = datetime.fromtimestamp(taken_at, tz=UTC)
        elif isinstance(taken_at, datetime):
            if taken_at.tzinfo is None:
                captured_at = taken_at.replace(tzinfo=UTC)
            else:
                captured_at = taken_at
        else:
            captured_at = datetime.now(UTC)

        return RawItem(
            raw_text=caption,
            url=f"https://www.instagram.com/p/{shortcode}/",
            platform="instagram",
            captured_at=captured_at,
            source_handle=source_handle,
            media_urls=InstagramAdapter._extract_media_urls(media),
        )

    @staticmethod
    def _bio_to_raw_item(user_info) -> RawItem:
        """Convert profile bio to RawItem for Engine C identifier extraction."""
        username = user_info.username if hasattr(user_info, "username") else "unknown"
        biography = user_info.biography if hasattr(user_info, "biography") else ""

        return RawItem(
            raw_text=biography,
            url=f"https://www.instagram.com/{username}/",
            platform="instagram_bio",
            captured_at=datetime.now(UTC),
            source_handle=username,
            media_urls=[],
        )

    @staticmethod
    def _extract_media_urls(media) -> list[str]:
        """Extract image/video URLs from Instagrapi Media object."""
        urls: list[str] = []
        try:
            # Thumbnail
            thumb = getattr(media, "thumbnail_url", None)
            if thumb:
                urls.append(str(thumb))

            # Video URL
            video = getattr(media, "video_url", None)
            if video:
                urls.append(str(video))
        except Exception as exc:
            log.debug("instagram.media_url_extraction_error", error=str(exc))
        return urls
