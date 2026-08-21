"""Telegram adapter — M3 (criteria 3.6–3.11).

Uses Telethon with a StringSession for stateless deployment.
Monitors channels/groups listed in sources.url_or_handle (e.g. "t.me/channelname").
Media attachments are downloaded to the configured media path for Phase 4 ingestion.

Session string is generated once via scripts/bootstrap_telegram_session.py.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import AsyncIterator

import structlog
from telethon import TelegramClient
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    SessionExpiredError,
    UserDeactivatedBanError,
)
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

from ..settings import settings
from .base import (
    AdapterAuthError,
    AdapterRateLimitError,
    RawItem,
    SourceAdapterBase,
    require_client,
)

log = structlog.get_logger(__name__)

_MEDIA_BASE = Path(os.environ.get("MEDIA_STORAGE_ROOT", "/app/media"))
_MESSAGES_PER_CHANNEL = 50  # max messages per poll cycle per channel


class TelegramAdapter(SourceAdapterBase):
    """Monitors Telegram channels/groups defined in sources table.

    source url_or_handle examples: "t.me/channelname", "@channelname"
    Yields one RawItem per message. Media downloaded to local storage.
    """

    adapter_id = "telegram-v1"
    platform = "telegram"
    adapter_version = "1.0.0"

    def __init__(self) -> None:
        self._client: TelegramClient | None = None
        self._needs_reauth: bool = False

    # ------------------------------------------------------------------
    # SourceAdapterBase implementation
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Connect with StringSession from settings (criteria 3.6)."""
        if not settings.telegram_adapter_enabled:
            log.warning(
                "social.adapter_disabled",
                adapter=self.adapter_id,
                hint="Set TELEGRAM_ADAPTER_ENABLED=true to activate",
            )
            return
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            raise AdapterAuthError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required")
        if not settings.telegram_session_string:
            raise AdapterAuthError(
                "TELEGRAM_SESSION_STRING not set. "
                "Run scripts/bootstrap_telegram_session.py to generate it. "  # criteria 3.7
                "Store the output in .env as TELEGRAM_SESSION_STRING."
            )
        try:
            self._client = TelegramClient(
                StringSession(settings.telegram_session_string),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )
            await self._client.connect()
            if not await self._client.is_user_authorized():
                raise AdapterAuthError(
                    "Telegram session is not authorised — regenerate session string"
                )
            log.info("telegram.authenticated")
        except SessionExpiredError as exc:
            raise AdapterAuthError("Telegram session expired — regenerate session string") from exc
        except UserDeactivatedBanError as exc:
            raise AdapterAuthError("Telegram account is banned") from exc
        except (ConnectionError, TimeoutError, OSError) as exc:
            raise AdapterAuthError(
                f"Telegram connection failed — check network/firewall: {exc}"
            ) from exc

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Iterate recent messages from each channel source (criteria 3.8)."""
        if self._client is None or not await self._client.is_user_authorized():
            log.warning("telegram.adapter.not_authenticated")
            return

        for handle in source_handles:
            channel_id = self._normalise_handle(handle)
            async for item in self._iter_channel(channel_id, handle, topic_id):
                yield item

    async def health(self) -> dict:
        if self._client is None:
            return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
        try:
            authorised = await self._client.is_user_authorized()
            status = "HEALTHY" if authorised else "DEGRADED"
            return {"status": status, "checked_at": datetime.now(UTC).isoformat()}
        except Exception as exc:
            return {
                "status": "DOWN",
                "checked_at": datetime.now(UTC).isoformat(),
                "error": str(exc),
            }

    async def fetch_profile_metadata(self, handle: str) -> dict | None:
        """Fetch Telegram channel/group metadata via GetFullChannel."""
        if self._client is None:
            return None
        try:
            channel_id = self._normalise_handle(handle)
            entity = await self._client.get_entity(channel_id)
            full = await self._client(
                __import__(
                    "telethon.tl.functions.channels", fromlist=["GetFullChannelRequest"]
                ).GetFullChannelRequest(channel=entity)
            )
            # telethon types client(request) as list; GetFullChannelRequest
            # actually returns a ChatFull with .chats and .full_chat.
            chat = full.chats[0] if full.chats else entity  # pyright: ignore[reportAttributeAccessIssue]
            full_chat = full.full_chat  # pyright: ignore[reportAttributeAccessIssue]
            # Bind once: two separate getattr calls are not the same value to a
            # type checker, and would not be at runtime either if chat mutated.
            chat_date = getattr(chat, "date", None)
            return {
                "title": getattr(chat, "title", None),
                "username": getattr(chat, "username", None),
                "about": getattr(full_chat, "about", None) or "",
                "participants_count": getattr(full_chat, "participants_count", None),
                "created_at": chat_date.isoformat() if chat_date else None,
                "is_verified": getattr(chat, "verified", False),
                "is_scam": getattr(chat, "scam", False),
                "is_fake": getattr(chat, "fake", False),
            }
        except (ChannelPrivateError, ChannelInvalidError):
            log.info("telegram.profile_metadata.private", handle=handle)
            return None
        except FloodWaitError as exc:
            log.warning("telegram.profile_metadata.flood", seconds=exc.seconds)
            return None
        except Exception as exc:
            log.warning("telegram.profile_metadata.failed", handle=handle, error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _iter_channel(
        self, channel_id: str, handle: str, topic_id: str
    ) -> AsyncIterator[RawItem]:
        """Yield messages from one channel. Handles access errors gracefully (criteria 3.11)."""
        client = require_client(self._client, "telegram")
        try:
            async for message in client.iter_messages(channel_id, limit=_MESSAGES_PER_CHANNEL):
                if not message.text and not message.media:
                    continue

                text = message.text or ""
                media_urls: list[str] = []

                if message.media:
                    media_path = await self._download_media(message, topic_id)
                    if media_path:
                        media_urls.append(str(media_path))

                if not text and not media_urls:
                    continue

                msg_url = f"https://t.me/{channel_id.lstrip('@')}/{message.id}"  # criteria 3.9

                # Capture forwarding metadata for Level 2 discovery
                fwd_channel_id = None
                fwd_channel_name = None
                if message.forward and message.forward.chat:
                    fwd_chat = message.forward.chat
                    fwd_channel_id = str(fwd_chat.id)
                    fwd_channel_name = getattr(fwd_chat, "title", None) or getattr(
                        fwd_chat, "username", None
                    )
                elif message.forward and message.forward.from_id:
                    # from_id is a TypePeer (PeerChannel/PeerUser/PeerChat), not an int
                    from telethon import utils as tl_utils

                    fwd_channel_id = str(tl_utils.get_peer_id(message.forward.from_id))

                # Capture engagement metrics (views/forwards) and reply threading
                engagement: dict[str, int | float] = {}
                if getattr(message, "views", None) is not None:
                    engagement["views"] = message.views
                if getattr(message, "forwards", None) is not None:
                    engagement["forwards"] = message.forwards

                reply_to_id = None
                if message.reply_to and getattr(message.reply_to, "reply_to_msg_id", None):
                    reply_to_id = str(message.reply_to.reply_to_msg_id)

                author_id = None
                if getattr(message, "from_id", None):
                    from telethon import utils as _tl_utils

                    try:
                        author_id = str(_tl_utils.get_peer_id(message.from_id))
                    except Exception:
                        pass

                yield RawItem(
                    raw_text=text or f"[media] {msg_url}",
                    url=msg_url,
                    platform=self.platform,
                    captured_at=message.date.replace(tzinfo=UTC)
                    if message.date.tzinfo is None
                    else message.date,
                    source_handle=handle,
                    media_urls=media_urls,
                    forwarded_from_channel_id=fwd_channel_id,
                    forwarded_from_channel_name=fwd_channel_name,
                    engagement=engagement or None,
                    reply_to_id=reply_to_id,
                    author_id=author_id,
                )

        except ChannelPrivateError:
            log.warning("telegram.channel_private", channel=channel_id)  # criteria 3.11
        except ChannelInvalidError:
            log.warning("telegram.channel_invalid", channel=channel_id)  # criteria 3.11
        except SessionExpiredError:
            log.warning("telegram.session_expired_mid_channel", channel=channel_id)
            self._needs_reauth = True
        except FloodWaitError as exc:
            log.warning("telegram.flood_wait", seconds=exc.seconds)
            raise AdapterRateLimitError(f"Telegram flood wait: {exc.seconds}s") from exc
        except Exception as exc:
            log.warning("telegram.channel_error", channel=channel_id, error=str(exc))

    async def _download_media(self, message, topic_id: str) -> Path | None:
        """Download media attachment to local storage path (criteria 3.10).

        Path: media/{topic_id}/{YYYY}/{MM}/{DD}/{content_hash}.{ext}
        Returns local path on success, None on failure.
        """
        if not isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
            return None
        try:
            now = datetime.now(UTC)
            date_path = _MEDIA_BASE / topic_id / now.strftime("%Y/%m/%d")
            date_path.mkdir(parents=True, exist_ok=True)

            # Download to a temp name first; rename once we have the hash
            tmp_path = date_path / f"tmp_{message.id}"
            client = require_client(self._client, "telegram")
            downloaded = await client.download_media(message, file=str(tmp_path))
            if not downloaded:
                return None
            if not isinstance(downloaded, str):
                # Telethon returns bytes only when downloading to memory. We always
                # pass a file path, so this means the call did something unexpected.
                log.warning(
                    "telegram.media_download_not_a_path",
                    returned_type=type(downloaded).__name__,
                )
                return None

            # Compute hash of raw bytes and rename
            import hashlib

            downloaded_path = Path(downloaded)
            raw_bytes = downloaded_path.read_bytes()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            ext = downloaded_path.suffix or ".bin"
            final_path = date_path / f"{file_hash}{ext}"
            downloaded_path.rename(final_path)
            return final_path
        except Exception as exc:
            log.warning("telegram.media_download_failed", error=str(exc))
            return None

    @staticmethod
    def _normalise_handle(handle: str) -> str:
        """Convert 't.me/channel' or '@channel' to '@channel' form for Telethon."""
        handle = handle.strip()
        if handle.startswith("t.me/"):
            handle = "@" + handle[5:]
        if not handle.startswith("@"):
            handle = "@" + handle
        return handle
