"""SourceAdapterBase — contract all social platform adapters must implement."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, TypeVar

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AdapterAuthError(Exception):
    """Credentials invalid, expired, or missing."""


class AdapterRateLimitError(Exception):
    """Source platform is rate-limiting us. Caller should back off."""


class AdapterDegradedError(Exception):
    """Adapter is partially functional — some data may be missing."""


_ClientT = TypeVar("_ClientT")


def require_client(client: _ClientT | None, adapter: str) -> _ClientT:
    """Return the platform client, or raise AdapterAuthError if it is unset.

    Every adapter assigns its client in authenticate() and leaves it None until
    then. Reaching a collect path with it still None means authenticate() never
    ran or failed without propagating. Without this, that surfaces as
    ``AttributeError: 'NoneType' object has no attribute 'iter_messages'`` several
    frames from the real cause, and outside the adapter error hierarchy callers
    catch.
    """
    if client is None:
        raise AdapterAuthError(f"{adapter}: not authenticated, call authenticate() first")
    return client


# ---------------------------------------------------------------------------
# RawItem — unprocessed content yielded by an adapter
# ---------------------------------------------------------------------------


@dataclass
class RawItem:
    """Raw content from a social platform, before normalisation and DB insert.

    Adapters yield RawItems. ingest.py converts them to content_items rows.
    Never add analysis logic here — adapters only collect, never transform.
    """

    raw_text: str
    url: str
    platform: str  # web|telegram|twitter|reddit|bluesky|instagram|youtube|whatsapp
    captured_at: datetime  # timezone-aware UTC
    source_handle: str  # channel/subreddit/handle — matches sources.url_or_handle
    media_urls: list[str] = field(default_factory=list)  # images/videos to download later (Phase 4)
    language: str | None = None  # ISO 639-1; None = detect in analyst pipeline
    forwarded_from_channel_id: str | None = (
        None  # Telegram: origin channel ID for forwarded messages
    )
    forwarded_from_channel_name: str | None = None  # Telegram: origin channel name
    # Engagement metrics — keys vary per platform (likes, views, score, etc.)
    engagement: dict[str, int | float] | None = None
    # Network/threading — for reply graph and influence analysis
    reply_to_id: str | None = None  # platform-specific parent post/message ID
    author_id: str | None = None  # platform-specific author identifier
    author_handle: str | None = None  # display handle of post author
    # Platform-durable identity for this item, e.g. "video:dQw4w9WgXcQ".
    # Set it only where the platform guarantees a stable ID whose *text* can
    # legitimately change; leave it None everywhere else. See content_hash().
    stable_id: str | None = None

    def content_hash(self) -> str:
        """SHA-256 dedup key — architectural rule 3.

        Default is the normalised text, matching the scraper convention.

        When stable_id is set the key becomes ``{platform}:{stable_id}`` instead.
        This is the narrow exception rule 3 allows: text hashing treats an edit
        as new content, which is right for a post but wrong for an item the
        platform re-transcribes. A YouTube ASR re-run rewrites the transcript of
        an unchanged video, and text hashing would re-ingest it every time.
        The platform prefix keeps two platforms' IDs from colliding.
        """
        if self.stable_id is not None:
            return hashlib.sha256(f"{self.platform}:{self.stable_id}".encode()).hexdigest()
        normalised = " ".join(self.raw_text.lower().split())
        return hashlib.sha256(normalised.encode()).hexdigest()


# ---------------------------------------------------------------------------
# SourceAdapterBase — ABC every adapter must implement
# ---------------------------------------------------------------------------


class SourceAdapterBase(ABC):
    """Abstract base class for all social platform adapters.

    Lifecycle:
        1. authenticate() — called once at service startup
        2. collect(topic_keywords, sources, topic_id) — called per poll cycle, yields RawItems
        3. health() — called by health check endpoint
    """

    adapter_id: str  # kebab-case identifier, e.g. "reddit-v1"
    platform: str  # matches sources.platform column value
    adapter_version: str  # semver

    @abstractmethod
    async def authenticate(self) -> None:
        """Load and validate credentials from env/settings.

        Raises:
            AdapterAuthError: if credentials are missing or rejected by the platform.
        """

    @abstractmethod
    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Yield RawItem records for a poll cycle.

        Args:
            topic_keywords: keywords from topic.keywords — used for search queries
            source_handles: list of sources.url_or_handle values for this platform
            topic_id:       UUID of the topic being monitored — used for media storage
                            path (criteria 3.10: media/{topic_id}/{date}/{hash}.ext)

        Yields:
            RawItem — one per piece of content found

        Never raises — log and continue on per-item errors. Only raises on total failure
        that makes the adapter non-functional for this cycle (AdapterDegradedError).
        """
        # yield required to make this an async generator in subclasses
        return
        yield  # unreachable: makes this an async generator for mypy

    async def refresh_credentials(self) -> bool:
        """Attempt to refresh expired credentials.

        Called when AdapterAuthError is raised during collect().
        Returns True if credentials were successfully refreshed.
        Default implementation returns False (no refresh possible).
        Override in subclasses that support credential refresh.
        """
        return False

    async def fetch_profile_metadata(self, handle: str) -> dict | None:
        """Fetch platform profile metadata for a source handle.

        Returns platform-specific metadata dict (subscriber count, bio,
        account creation date, etc.) or None if not supported / failed.
        Default implementation returns None — override in subclasses
        that support profile fetching.
        """
        return None

    @abstractmethod
    async def health(self) -> dict:
        """Return adapter health status.

        Returns:
            {"status": "HEALTHY"|"DEGRADED"|"DOWN", "checked_at": ISO8601}
        """
