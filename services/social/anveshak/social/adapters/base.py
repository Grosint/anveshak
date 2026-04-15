"""SourceAdapterBase — contract all social platform adapters must implement."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AdapterAuthError(Exception):
    """Credentials invalid, expired, or missing."""


class AdapterRateLimitError(Exception):
    """Source platform is rate-limiting us. Caller should back off."""


class AdapterDegradedError(Exception):
    """Adapter is partially functional — some data may be missing."""


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
    platform: str                              # web|telegram|twitter|reddit|bluesky
    captured_at: datetime                      # timezone-aware UTC
    source_handle: str                         # channel/subreddit/handle — matches sources.url_or_handle
    media_urls: list[str] = field(default_factory=list)   # images/videos to download later (Phase 4)
    language: str | None = None                # ISO 639-1; None = detect in analyst pipeline

    def content_hash(self) -> str:
        """SHA-256 of normalised text — dedup key, same as scraper convention."""
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

    adapter_id: str        # kebab-case identifier, e.g. "reddit-v1"
    platform: str          # matches sources.platform column value
    adapter_version: str   # semver

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
        yield  # noqa: unreachable — makes mypy happy

    @abstractmethod
    async def health(self) -> dict:
        """Return adapter health status.

        Returns:
            {"status": "HEALTHY"|"DEGRADED"|"DOWN", "checked_at": ISO8601}
        """
