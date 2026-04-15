"""Reddit adapter — M3 (criteria 3.12–3.16).

Uses PRAW (synchronous) wrapped in asyncio.to_thread() since PRAW has no
native async support. Polls both `new` and `hot` feeds per subreddit source.
Content deduplication is handled downstream via content_hash ON CONFLICT.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import AsyncIterator

import praw
import praw.exceptions
import structlog

from .base import (
    AdapterAuthError,
    AdapterDegradedError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
)
from ..settings import settings

log = structlog.get_logger(__name__)

_BACKOFF_SECONDS = [5, 15, 60]   # exponential backoff steps on rate limit


class RedditAdapter(SourceAdapterBase):
    """Polls Reddit subreddits defined as sources in the sources table.

    Source url_or_handle must be in the form "r/subreddit" (criteria 3.13).
    """

    adapter_id = "reddit-v1"
    platform = "reddit"
    adapter_version = "1.0.0"

    def __init__(self) -> None:
        self._reddit: praw.Reddit | None = None

    # ------------------------------------------------------------------
    # SourceAdapterBase implementation
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Initialise PRAW client from settings (criteria 3.12)."""
        if not settings.reddit_adapter_enabled:
            log.warning("social.adapter_disabled", adapter=self.adapter_id,
                        hint="Set REDDIT_ADAPTER_ENABLED=true to activate")
            return
        if not settings.reddit_client_id or not settings.reddit_client_secret:
            raise AdapterAuthError(
                "Reddit adapter enabled but REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set"
            )
        try:
            self._reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
                # read-only mode — no username/password needed for public subreddits
            )
            # Verify credentials by calling a lightweight endpoint in a thread
            await asyncio.to_thread(lambda: self._reddit.user.me())
        except praw.exceptions.PRAWException as exc:
            raise AdapterAuthError(f"Reddit authentication failed: {exc}") from exc

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Yield posts from subreddit sources matching topic keywords (criteria 3.14).

        source_handles: list of "r/subreddit" strings from sources.url_or_handle.
        topic_id: used for media storage path in Phase 4; recorded on RawItem.media_urls.
        """
        if self._reddit is None:
            log.warning("reddit.adapter.not_authenticated")
            return

        for handle in source_handles:
            subreddit_name = handle.lstrip("r/")
            async for item in self._poll_subreddit(subreddit_name, handle, topic_keywords):
                yield item

    async def health(self) -> dict:
        if self._reddit is None:
            return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
        try:
            await asyncio.to_thread(lambda: list(self._reddit.subreddit("announcements").hot(limit=1)))
            return {"status": "HEALTHY", "checked_at": datetime.now(UTC).isoformat()}
        except Exception as exc:
            return {
                "status": "DEGRADED",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _poll_subreddit(
        self,
        subreddit_name: str,
        handle: str,
        topic_keywords: list[str],
    ) -> AsyncIterator[RawItem]:
        """Poll new + hot feeds for a subreddit with backoff on rate-limit."""
        for feed_type in ("new", "hot"):
            for attempt, backoff in enumerate([0] + _BACKOFF_SECONDS):
                if backoff:
                    log.warning(
                        "reddit.rate_limit_backoff",
                        subreddit=subreddit_name,
                        feed=feed_type,
                        seconds=backoff,
                    )
                    await asyncio.sleep(backoff)
                try:
                    posts = await asyncio.to_thread(
                        self._fetch_feed, subreddit_name, feed_type
                    )
                    break
                except praw.exceptions.RedditAPIException as exc:
                    if "RATELIMIT" in str(exc).upper():
                        if attempt >= len(_BACKOFF_SECONDS):
                            raise AdapterRateLimitError(
                                f"Reddit rate limit exhausted for r/{subreddit_name}"
                            ) from exc
                        continue  # retry after backoff
                    log.warning(
                        "reddit.api_error",
                        subreddit=subreddit_name,
                        error=str(exc),
                    )
                    return
                except Exception as exc:
                    log.warning(
                        "reddit.fetch_error",
                        subreddit=subreddit_name,
                        feed=feed_type,
                        error=str(exc),
                    )
                    return

            for post in posts:
                text = self._post_to_text(post)
                if not text:
                    continue
                yield RawItem(
                    raw_text=text,
                    url=f"https://www.reddit.com{post.permalink}",   # criteria 3.15
                    platform=self.platform,
                    captured_at=datetime.fromtimestamp(post.created_utc, tz=UTC),
                    source_handle=handle,
                    media_urls=self._extract_media_urls(post),
                )

    def _fetch_feed(self, subreddit_name: str, feed_type: str) -> list:
        """Synchronous PRAW call — runs in asyncio.to_thread()."""
        sub = self._reddit.subreddit(subreddit_name)
        feed = sub.new(limit=25) if feed_type == "new" else sub.hot(limit=25)
        return list(feed)

    @staticmethod
    def _post_to_text(post: praw.models.Submission) -> str:
        """Combine title + selftext for clean text. Skip link-only posts with no body."""
        parts = [post.title]
        if post.selftext and post.selftext not in ("[removed]", "[deleted]"):
            parts.append(post.selftext)
        return "\n\n".join(parts).strip()

    @staticmethod
    def _extract_media_urls(post: praw.models.Submission) -> list[str]:
        """Extract image/video URLs for Phase 4 media ingestion."""
        urls: list[str] = []
        if hasattr(post, "url") and post.url and any(
            post.url.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".mp4")
        ):
            urls.append(post.url)
        return urls
