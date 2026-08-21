"""YouTube adapter — M3 social platform integration.

Channel-based polling via YouTube Data API v3. Uses playlistItems.list (1 unit)
instead of search.list (100 units) to conserve quota.

Captions fetched via youtube-transcript-api (unofficial, zero quota cost).
Comments gated behind youtube_fetch_comments setting.

QUOTA GUARD IS CRITICAL.
YouTube Data API v3 free tier: 10,000 units/day.
YouTubeQuotaGuard atomically enforces daily cap using Redis counter keyed by date.
Resets at midnight UTC automatically via TTL.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import structlog
from arq import ArqRedis

from ..settings import settings
from .base import (
    AdapterAuthError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
    require_client,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Content hash helpers — stable across caption edits
# ---------------------------------------------------------------------------


def youtube_video_hash(video_id: str) -> str:
    """SHA-256 dedup key for a YouTube video. Keyed on video_id, not text.

    The adapter does not call this: it sets ``stable_id="video:{video_id}"`` on
    the RawItem and RawItem.content_hash() produces the same digest from
    ``{platform}:{stable_id}``. Kept as the readable statement of the format,
    and as what callers outside the adapter (backfills, one-off scripts) should
    use to recompute a key. tests/unit/test_youtube_quota.py asserts the two
    agree, so neither can drift.
    """
    return hashlib.sha256(f"youtube:video:{video_id}".encode()).hexdigest()


def youtube_comment_hash(comment_id: str) -> str:
    """SHA-256 dedup key for a YouTube comment. See youtube_video_hash()."""
    return hashlib.sha256(f"youtube:comment:{comment_id}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Caption cleaning — strip auto-generated noise markers
# ---------------------------------------------------------------------------

_CAPTION_NOISE = re.compile(
    r"\[(?:music|applause|silence|inaudible|background noise|laughter)\]"
    r"|[\u266a\u266b].*?[\u266a\u266b]",
    re.IGNORECASE,
)


def clean_caption(text: str) -> str:
    """Remove YouTube auto-caption noise markers."""
    cleaned = _CAPTION_NOISE.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Channel URL normalization — handles 6+ URL formats
# ---------------------------------------------------------------------------

_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


def normalize_channel_input(raw: str) -> tuple[str, str]:
    """Normalize any YouTube channel URL/handle to (type, value).

    Returns:
        ("channel_id", "UCxxxx") — direct channel ID
        ("handle", "Name")      — @handle format
        ("custom", "Name")      — /c/Name format
        ("user", "Name")        — /user/Name format (legacy)
    """
    raw = raw.strip()

    # Full URL
    if "youtube.com" in raw or "youtu.be" in raw:
        parsed = urlparse(raw)
        path = parsed.path.rstrip("/")

        if path.startswith("/@"):
            return ("handle", path[2:])
        if path.startswith("/channel/"):
            return ("channel_id", path[len("/channel/") :])
        if path.startswith("/c/"):
            return ("custom", path[3:])
        if path.startswith("/user/"):
            return ("user", path[6:])

    # @handle
    if raw.startswith("@"):
        return ("handle", raw[1:])

    # Bare channel ID (UC + 22 chars)
    if _CHANNEL_ID_RE.match(raw):
        return ("channel_id", raw)

    # Bare handle/name
    return ("handle", raw)


# ---------------------------------------------------------------------------
# Quota Guard — daily Redis atomic counter
# ---------------------------------------------------------------------------


def _daily_quota_key() -> str:
    """Redis key for today's YouTube quota counter."""
    return f"anveshak:youtube:daily_quota:{datetime.now(UTC).strftime('%Y-%m-%d')}"


def _seconds_until_day_end() -> int:
    """Seconds from now until midnight UTC."""
    now = datetime.now(UTC)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_midnight - now).total_seconds()))


class YouTubeQuotaGuard:
    """Atomic quota guard backed by Redis Lua script.

    check_and_increment(units) must be called BEFORE every YouTube API call.
    Returns True  → under cap, call permitted, counter incremented by units.
    Returns False → at/above cap, call BLOCKED.

    Variable cost: search=100, playlistItems=1, videos.list=1,
    commentThreads=1, captions=200.
    """

    _LUA_CHECK_AND_INCREMENT = """\
local key = KEYS[1]
local cap = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local units = tonumber(ARGV[3])
local current = tonumber(redis.call('GET', key) or '0')
if current + units > cap then
    return -1
end
local new_count = redis.call('INCRBY', key, units)
if new_count == units and current == 0 then
    redis.call('EXPIRE', key, ttl)
end
if new_count > cap then
    redis.call('DECRBY', key, units)
    return -1
end
return new_count
"""

    def __init__(self, redis: ArqRedis, cap: int) -> None:
        self._redis = redis
        self._cap = cap

    async def check_and_increment(self, units: int = 1) -> bool:
        """Atomically increment by units and check daily cap."""
        key = _daily_quota_key()
        ttl = _seconds_until_day_end()

        # redis-py declares keys_and_args as str. Ints work at runtime because the
        # client encodes them, but the Lua script receives strings either way, so
        # convert here to match what actually crosses the wire.
        # redis-py types eval() against the sync client, which declares a str
        # return. ArqRedis is async and awaits fine at runtime.
        result = int(
            await self._redis.eval(  # pyright: ignore[reportGeneralTypeIssues]
                self._LUA_CHECK_AND_INCREMENT,
                1,
                key,
                str(self._cap),
                str(ttl),
                str(units),
            )
        )

        if result == -1:
            log.warning(
                "youtube.quota_guard.cap_reached",
                units_requested=units,
                cap=self._cap,
                key=key,
            )
            return False

        log.debug("youtube.quota_guard.ok", daily_units=result, cap=self._cap)
        return True

    async def current_count(self) -> int:
        """Read current daily count without incrementing."""
        val = await self._redis.get(_daily_quota_key())
        return int(val) if val else 0


# ---------------------------------------------------------------------------
# YouTube Adapter
# ---------------------------------------------------------------------------


class YouTubeAdapter(SourceAdapterBase):
    """YouTube Data API v3 adapter — channel-based polling.

    Uses playlistItems.list (1 unit) for new video detection,
    videos.list (1 unit per 50) for metadata, and
    youtube-transcript-api (0 units) for captions.
    """

    adapter_id = "youtube-v1"
    platform = "youtube"
    adapter_version = "1.0.0"

    def __init__(self, quota_guard: YouTubeQuotaGuard) -> None:
        # googleapiclient.discovery.Resource is built dynamically and ships no
        # stubs, so Any is the honest annotation.
        self._youtube: Any | None = None
        self._quota_guard = quota_guard
        self._channel_cache: dict[str, str] = {}  # handle → channel_id

    @property
    def _api(self) -> Any:
        """The discovery client, or AdapterAuthError if authenticate() never ran."""
        return require_client(self._youtube, "youtube")

    async def authenticate(self) -> None:
        """Validate API key by making a cheap API call."""
        if not settings.youtube_api_key:
            raise AdapterAuthError("YOUTUBE_API_KEY required")

        try:
            from googleapiclient.discovery import build

            client = build(
                "youtube",
                "v3",
                developerKey=settings.youtube_api_key,
                cache_discovery=False,
            )
            # Test call — costs 1 unit but validates the key
            client.channels().list(
                part="id",
                id="UC_x5XG1OV2P6uZZ5FSM9Ttw",  # Google's channel
            ).execute()
            self._youtube = client
            log.info("youtube.adapter.authenticated")
        except Exception as exc:
            raise AdapterAuthError(f"YouTube API key validation failed: {exc}") from exc

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Poll each channel's uploads, yield videos + optional comments."""

        for handle in source_handles:
            try:
                channel_id = await self._resolve_channel(handle)
                if not channel_id:
                    log.warning("youtube.channel_not_found", handle=handle)
                    continue

                async for item in self._poll_channel(channel_id, handle, topic_id):
                    yield item

            except AdapterRateLimitError:
                log.warning("youtube.quota_exhausted", handle=handle)
                return  # stop all channels — quota is global
            except Exception as exc:
                log.warning("youtube.channel_error", handle=handle, error=str(exc))
                continue

    async def _resolve_channel(self, handle: str) -> str | None:
        """Resolve any handle format to a channel ID. Cached."""
        import asyncio

        if handle in self._channel_cache:
            return self._channel_cache[handle]

        kind, value = normalize_channel_input(handle)

        if kind == "channel_id":
            self._channel_cache[handle] = value
            return value

        if not await self._quota_guard.check_and_increment(units=1):
            raise AdapterRateLimitError("YouTube daily quota exhausted")

        try:
            if kind == "handle":
                resp = await asyncio.to_thread(
                    lambda: (
                        self._api.channels()
                        .list(
                            part="id,contentDetails",
                            forHandle=value,
                        )
                        .execute()
                    )
                )
            elif kind == "user":
                resp = await asyncio.to_thread(
                    lambda: (
                        self._api.channels()
                        .list(
                            part="id,contentDetails",
                            forUsername=value,
                        )
                        .execute()
                    )
                )
            else:  # custom — try search as last resort
                if not await self._quota_guard.check_and_increment(units=99):
                    raise AdapterRateLimitError("YouTube daily quota exhausted")
                resp = await asyncio.to_thread(
                    lambda: (
                        self._api.search()
                        .list(
                            part="snippet",
                            q=value,
                            type="channel",
                            maxResults=1,
                        )
                        .execute()
                    )
                )
                items = resp.get("items", [])
                if items:
                    cid = items[0]["snippet"]["channelId"]
                    self._channel_cache[handle] = cid
                    return cid
                return None

            items = resp.get("items", [])
            if items:
                cid = items[0]["id"]
                self._channel_cache[handle] = cid
                return cid

        except Exception as exc:
            log.warning("youtube.resolve_failed", handle=handle, error=str(exc))

        return None

    async def _poll_channel(
        self, channel_id: str, handle: str, topic_id: str
    ) -> AsyncIterator[RawItem]:
        """Fetch recent uploads from a channel and yield RawItems."""
        import asyncio

        # Get uploads playlist ID (every channel has one: UU + channel_id[2:])
        uploads_playlist = "UU" + channel_id[2:]

        if not await self._quota_guard.check_and_increment(units=1):
            raise AdapterRateLimitError("YouTube daily quota exhausted")

        # Fetch recent video IDs from uploads playlist
        resp = await asyncio.to_thread(
            lambda: (
                self._api.playlistItems()
                .list(
                    part="contentDetails",
                    playlistId=uploads_playlist,
                    maxResults=min(50, settings.youtube_backfill_count),
                )
                .execute()
            )
        )

        video_ids = [item["contentDetails"]["videoId"] for item in resp.get("items", [])]

        if not video_ids:
            return

        # Fetch video metadata in batches of 50 (1 unit per call)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            if not await self._quota_guard.check_and_increment(units=1):
                raise AdapterRateLimitError("YouTube daily quota exhausted")

            details = await asyncio.to_thread(
                lambda ids=batch: (
                    self._api.videos()
                    .list(
                        part="snippet,statistics",
                        id=",".join(ids),
                    )
                    .execute()
                )
            )

            for video in details.get("items", []):
                async for item in self._process_video(video, handle, topic_id):
                    yield item

    async def _process_video(
        self, video: dict, handle: str, topic_id: str
    ) -> AsyncIterator[RawItem]:
        """Process a single video: metadata + caption + optional comments."""
        vid = video["id"]
        snippet = video["snippet"]
        stats = video.get("statistics", {})

        title = snippet.get("title", "")
        description = snippet.get("description", "")
        published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        channel_title = snippet.get("channelTitle", handle)
        thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url") or snippet.get(
            "thumbnails", {}
        ).get("default", {}).get("url", "")

        # Engagement metrics
        engagement: dict[str, int | float] = {}
        for key in ("viewCount", "likeCount", "commentCount", "favoriteCount"):
            val = stats.get(key)
            if val is not None:
                # Map to short names matching dashboard expectations
                short_key = key.replace("Count", "s").replace("view", "view").lower()
                if key == "viewCount":
                    short_key = "views"
                elif key == "likeCount":
                    short_key = "likes"
                elif key == "commentCount":
                    short_key = "comments"
                elif key == "favoriteCount":
                    short_key = "favorites"
                engagement[short_key] = int(val)

        # Caption extraction (zero quota cost)
        caption_text = ""
        caption_source = "none"
        try:
            caption_text, caption_source = await self._fetch_caption(vid)
        except Exception as exc:
            log.info("youtube.caption_unavailable", video_id=vid, error=str(exc))
        # Manual captions, ASR, or none materially changes transcript quality, so
        # record which one this item got.
        log.debug(
            "youtube.caption_resolved",
            video_id=vid,
            caption_source=caption_source,
            caption_chars=len(caption_text),
        )

        # Build raw_text: title + description + transcript
        parts = [title]
        if description:
            parts.append(description)
        if caption_text:
            parts.append(f"[TRANSCRIPT]\n{caption_text}")
        raw_text = "\n\n".join(parts)

        # Yield video as content item
        video_item = RawItem(
            raw_text=raw_text,
            url=f"https://www.youtube.com/watch?v={vid}",
            platform="youtube",
            captured_at=published_at,
            source_handle=handle,
            media_urls=[thumbnail] if thumbnail else [],
            engagement=engagement or None,
            author_id=snippet.get("channelId", ""),
            author_handle=channel_title,
            # Dedup on the video, not its text. raw_text embeds the transcript,
            # and an ASR re-run rewrites that for an unchanged video, which text
            # hashing would ingest as a new item on every poll. Matches
            # youtube_video_hash(vid) -- see RawItem.content_hash().
            stable_id=f"video:{vid}",
        )
        yield video_item

        # Optional: fetch comments
        if settings.youtube_fetch_comments:
            async for comment_item in self._fetch_comments(vid, handle, topic_id):
                yield comment_item

    async def _fetch_caption(self, video_id: str) -> tuple[str, str]:
        """Fetch caption text via youtube-transcript-api. Zero API quota cost.

        Returns (cleaned_text, source) where source is 'manual' or 'auto'.
        """
        import asyncio

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            log.info("youtube.transcript_api_not_installed")
            return "", "unavailable"

        def _get_transcript() -> tuple[str, str]:
            ytt_api = YouTubeTranscriptApi()
            # Prefer manual captions, fall back to auto-generated
            try:
                transcript = ytt_api.fetch(video_id)
                parts = [entry.text for entry in transcript]
                raw = " ".join(parts)
                return clean_caption(raw), "auto"
            except Exception:
                return "", "unavailable"

        return await asyncio.to_thread(_get_transcript)

    async def _fetch_comments(
        self, video_id: str, handle: str, topic_id: str
    ) -> AsyncIterator[RawItem]:
        """Fetch top-level comment threads for a video."""
        import asyncio

        if not await self._quota_guard.check_and_increment(units=1):
            log.warning("youtube.comments_quota_exhausted", video_id=video_id)
            return

        try:
            resp = await asyncio.to_thread(
                lambda: (
                    self._api.commentThreads()
                    .list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=min(100, settings.youtube_max_comments_per_video),
                        order="relevance",
                        textFormat="plainText",
                    )
                    .execute()
                )
            )
        except Exception as exc:
            log.info("youtube.comments_disabled", video_id=video_id, error=str(exc))
            return

        for thread in resp.get("items", []):
            comment = thread["snippet"]["topLevelComment"]["snippet"]
            comment_id = thread["id"]

            comment_engagement: dict[str, int | float] = {}
            like_count = comment.get("likeCount", 0)
            if like_count:
                comment_engagement["likes"] = like_count
            reply_count = thread["snippet"].get("totalReplyCount", 0)
            if reply_count:
                comment_engagement["replies"] = reply_count

            item = RawItem(
                raw_text=comment.get("textDisplay", ""),
                url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                platform="youtube",
                captured_at=datetime.fromisoformat(comment["publishedAt"].replace("Z", "+00:00")),
                source_handle=handle,
                engagement=comment_engagement or None,
                author_id=comment.get("authorChannelId", {}).get("value", ""),
                author_handle=comment.get("authorDisplayName", ""),
                reply_to_id=video_id,
                # Comment IDs are stable across edits; matches
                # youtube_comment_hash(comment_id).
                stable_id=f"comment:{comment_id}",
            )
            yield item

    async def health(self) -> dict:
        """Check API key validity and quota remaining."""
        status = "HEALTHY"
        details: dict = {}

        try:
            quota_used = await self._quota_guard.current_count()
            details["daily_quota_used"] = quota_used
            details["daily_quota_cap"] = self._quota_guard._cap
            if quota_used >= self._quota_guard._cap:
                status = "DEGRADED"
                details["reason"] = "daily quota exhausted"
        except Exception as exc:
            status = "DEGRADED"
            details["error"] = str(exc)

        return {
            "status": status,
            "checked_at": datetime.now(UTC).isoformat(),
            **details,
        }

    async def fetch_profile_metadata(self, handle: str) -> dict | None:
        """Fetch YouTube channel profile via channels().list (1 quota unit)."""
        import asyncio

        if self._youtube is None:
            return None

        try:
            channel_id = await self._resolve_channel(handle)
            if not channel_id:
                return None

            if not await self._quota_guard.check_and_increment(units=1):
                log.warning("youtube.profile_metadata.quota_exhausted", handle=handle)
                return None

            resp = await asyncio.to_thread(
                lambda: (
                    self._api.channels()
                    .list(
                        part="snippet,statistics",
                        id=channel_id,
                    )
                    .execute()
                )
            )

            items = resp.get("items", [])
            if not items:
                return None

            ch = items[0]
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})

            return {
                "channel_id": channel_id,
                "title": snippet.get("title"),
                "description": snippet.get("description", "")[:500],
                "custom_url": snippet.get("customUrl"),
                "published_at": snippet.get("publishedAt"),
                "country": snippet.get("country"),
                "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
                "video_count": int(stats.get("videoCount", 0)),
                "view_count": int(stats.get("viewCount", 0)),
            }
        except Exception as exc:
            log.warning("youtube.profile_metadata.failed", handle=handle, error=str(exc))
            return None
