"""Bluesky adapter — M3 (criteria 3.17–3.19).

Uses atproto SDK. Searches posts via app.bsky.feed.searchPosts for each topic keyword.
Bluesky's API is public-read with password auth for search endpoints.
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import AsyncIterator

import structlog
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

    def __init__(self) -> None:
        self._client: AsyncClient | None = None
        self._my_did: str | None = None

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
