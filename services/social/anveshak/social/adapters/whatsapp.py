"""WhatsApp adapter — Baileys bridge sidecar + Redis buffer.

Architecture: Node.js Baileys bridge → RPUSH to Redis buffer → this adapter
drains via LPOP in collect(). Fully self-hosted, no Meta Business API.

Auth is QR-based on the bridge sidecar — no env var credentials needed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import AsyncIterator
from urllib.parse import quote

import httpx
import structlog
from arq import ArqRedis
from pydantic import BaseModel, ConfigDict, ValidationError

from ..settings import settings
from .base import (
    AdapterAuthError,
    RawItem,
    SourceAdapterBase,
)

log = structlog.get_logger(__name__)

BUFFER_KEY = "anveshak:whatsapp:buffer"


class WhatsAppBufferMessage(BaseModel):
    """Validates JSON from Redis buffer."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    type_: str | None = None  # "logout" sentinel or None for regular messages
    group_jid: str | None = None
    group_name: str | None = None
    sender: str | None = None
    sender_name: str | None = None
    message_id: str | None = None
    text: str | None = None
    timestamp: int | None = None
    media_path: str | None = None
    media_type: str | None = None
    reply_to_id: str | None = None
    forwarded: bool = False

    @classmethod
    def from_json(cls, raw_json: bytes | str) -> "WhatsAppBufferMessage":
        """Parse JSON with _type field mapping."""
        data = json.loads(raw_json)
        if "_type" in data:
            data["type_"] = data.pop("_type")
        return cls.model_validate(data)


class WhatsAppAdapter(SourceAdapterBase):
    """Poll-based WhatsApp adapter that drains a Redis buffer filled by the bridge."""

    adapter_id = "whatsapp-v1"
    platform = "whatsapp"
    adapter_version = "1.0.0"

    def __init__(self, redis: ArqRedis | None = None) -> None:
        self._redis = redis
        self._bridge_url: str = settings.whatsapp_bridge_url
        self._bridge_token: str = settings.whatsapp_bridge_token
        self._connected: bool = False

    async def authenticate(self) -> None:
        """Check bridge is connected. Raises AdapterAuthError if not."""
        if not settings.whatsapp_adapter_enabled:
            log.warning(
                "social.adapter_disabled",
                adapter=self.adapter_id,
                hint="Set WHATSAPP_ADAPTER_ENABLED=true to activate",
            )
            return

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if self._bridge_token:
                    headers["Authorization"] = f"Bearer {self._bridge_token}"
                resp = await client.get(f"{self._bridge_url}/health", headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ConnectionError, TimeoutError, OSError) as exc:
            raise AdapterAuthError(
                f"WhatsApp bridge unreachable at {self._bridge_url}: {exc}"
            ) from exc

        status = data.get("status", "unknown")
        if status == "logged_out":
            raise AdapterAuthError(
                f"WhatsApp session logged out — re-scan QR at {self._bridge_url}/qr"
            )
        if status != "connected":
            raise AdapterAuthError(
                f"WhatsApp bridge not connected (status={status}) — scan QR at {self._bridge_url}/qr"
            )
        self._connected = True
        log.info("social.whatsapp.authenticated", groups=data.get("groups", 0))

    async def collect(
        self,
        topic_keywords: list[str],
        source_handles: list[str],
        topic_id: str,
    ) -> AsyncIterator[RawItem]:
        """Drain Redis buffer, filter by source_handles, yield RawItems."""
        if not self._connected:
            log.warning("social.whatsapp.not_connected", adapter_id=self.adapter_id)
            return

        if not self._redis:
            log.error("social.whatsapp.no_redis", adapter_id=self.adapter_id)
            return

        # Pre-collect health check — detect logout before draining empty buffer
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if self._bridge_token:
                    headers["Authorization"] = f"Bearer {self._bridge_token}"
                resp = await client.get(f"{self._bridge_url}/health", headers=headers)
                data = resp.json()
                if data.get("status") == "logged_out":
                    self._connected = False
                    raise AdapterAuthError("WhatsApp session logged out — re-scan QR")
        except AdapterAuthError:
            raise
        except Exception:
            pass  # bridge health check failure is non-fatal for collect

        allowed_jids = {h.strip() for h in source_handles}
        drain_max = settings.whatsapp_buffer_drain_max
        media_root = settings.media_storage_root

        for _ in range(drain_max):
            raw_bytes = await self._redis.lpop(BUFFER_KEY)  # type: ignore[arg-type]
            if raw_bytes is None:
                break
            if not isinstance(raw_bytes, (bytes, str)):
                # lpop returns a list only when called with a count, which this is
                # not. Skip rather than hand a list to a JSON parser.
                log.warning(
                    "social.whatsapp.unexpected_buffer_type",
                    returned_type=type(raw_bytes).__name__,
                )
                continue

            try:
                msg = WhatsAppBufferMessage.from_json(raw_bytes)
            except (json.JSONDecodeError, ValidationError) as exc:
                log.warning("social.whatsapp.invalid_buffer_msg", error=str(exc))
                continue

            # Logout sentinel
            if msg.type_ == "logout":
                self._connected = False
                raise AdapterAuthError("WhatsApp session logged out")

            # Filter by monitored groups
            if not msg.group_jid or msg.group_jid not in allowed_jids:
                continue

            # Skip empty messages (no text and no media)
            if not msg.text and not msg.media_path:
                continue

            # Media path validation — prevent path traversal
            media_urls: list[str] = []
            if msg.media_path:
                from pathlib import Path

                try:
                    Path(msg.media_path).resolve().relative_to(Path(media_root).resolve())
                    media_urls = [msg.media_path]
                except ValueError:
                    log.warning(
                        "social.whatsapp.media_path_rejected",
                        path=msg.media_path,
                        allowed_root=media_root,
                    )

            # Build raw_text
            raw_text = msg.text or f"[media:{msg.media_type or 'unknown'}] {msg.media_path}"

            # Synthetic URL (URL-encoded for safety)
            group_num = msg.group_jid.split("@")[0] if "@" in msg.group_jid else msg.group_jid
            msg_id = msg.message_id or "unknown"
            url = f"https://wa.me/g/{quote(group_num)}/{quote(msg_id)}"

            # Timestamp
            captured_at = (
                datetime.fromtimestamp(msg.timestamp, tz=UTC)
                if msg.timestamp
                else datetime.now(UTC)
            )

            yield RawItem(
                raw_text=raw_text,
                url=url,
                platform="whatsapp",
                captured_at=captured_at,
                source_handle=msg.group_jid,
                media_urls=media_urls,
                language=None,
                engagement=None,
                reply_to_id=msg.reply_to_id,
                author_id=msg.sender,
                author_handle=msg.sender_name,
            )

    async def health(self) -> dict:
        """Check bridge health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {}
                if self._bridge_token:
                    headers["Authorization"] = f"Bearer {self._bridge_token}"
                resp = await client.get(f"{self._bridge_url}/health", headers=headers)
                data = resp.json()
                status = data.get("status", "unknown")
                if status == "connected":
                    return {"status": "HEALTHY", "checked_at": datetime.now(UTC).isoformat()}
                if status == "logged_out":
                    return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
                return {"status": "DEGRADED", "checked_at": datetime.now(UTC).isoformat()}
        except Exception:
            return {"status": "DOWN", "checked_at": datetime.now(UTC).isoformat()}
