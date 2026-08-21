"""Unit tests: WhatsApp adapter — Baileys bridge sidecar + Redis buffer.

TDD RED phase: these tests define the expected behavior of WhatsAppAdapter.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.social.adapters.base import AdapterAuthError
from anveshak.social.adapters.whatsapp import (
    WhatsAppAdapter,
    WhatsAppBufferMessage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bridge_health(status: str = "connected", groups: int = 3) -> dict:
    return {"status": status, "groups": groups, "buffer_length": 0}


def _buffer_msg(
    group_jid: str = "120363001234567890@g.us",
    text: str = "Test message",
    media_path: str | None = None,
    **overrides,
) -> bytes:
    msg = {
        "group_jid": group_jid,
        "group_name": "Test Group",
        "sender": "919876543210@s.whatsapp.net",
        "sender_name": "Test User",
        "message_id": "3EB0B430A1B2C3D4E5",
        "text": text,
        "timestamp": 1719200400,
        "media_path": media_path,
        "media_type": "image" if media_path else None,
        "reply_to_id": None,
        "forwarded": False,
    }
    msg.update(overrides)
    return json.dumps(msg).encode()


def _logout_sentinel() -> bytes:
    return json.dumps({"_type": "logout", "timestamp": 1719200400, "reason": "logged_out"}).encode()


def _make_adapter(redis_mock: AsyncMock | None = None) -> WhatsAppAdapter:
    adapter = WhatsAppAdapter(redis=redis_mock)
    adapter._connected = True
    adapter._bridge_url = "http://test-bridge:3002"
    adapter._bridge_token = "test-token"
    return adapter


# ---------------------------------------------------------------------------
# WhatsAppBufferMessage model tests
# ---------------------------------------------------------------------------


class TestWhatsAppBufferMessage:
    @pytest.mark.unit
    def test_parse_valid_message(self):
        raw = _buffer_msg()
        msg = WhatsAppBufferMessage.from_json(raw)
        assert msg.group_jid == "120363001234567890@g.us"
        assert msg.text == "Test message"
        assert msg.timestamp == 1719200400

    @pytest.mark.unit
    def test_parse_logout_sentinel(self):
        raw = _logout_sentinel()
        msg = WhatsAppBufferMessage.from_json(raw)
        assert msg.type_ == "logout"

    @pytest.mark.unit
    def test_parse_media_only(self):
        raw = _buffer_msg(text=None, media_path="/app/media/group/2026/06/24/abc.jpg")
        msg = WhatsAppBufferMessage.from_json(raw)
        assert msg.text is None
        assert msg.media_path == "/app/media/group/2026/06/24/abc.jpg"

    @pytest.mark.unit
    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            WhatsAppBufferMessage.from_json(b"not-json{{{")


# ---------------------------------------------------------------------------
# authenticate() tests
# ---------------------------------------------------------------------------


class TestWhatsAppAuthenticate:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_auth_success(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"

        with patch("anveshak.social.adapters.whatsapp.settings") as mock_settings:
            mock_settings.whatsapp_adapter_enabled = True
            mock_settings.whatsapp_bridge_url = "http://test:3002"
            mock_settings.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_resp.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                await adapter.authenticate()
                assert adapter._connected is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_auth_bridge_down(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"

        with patch("anveshak.social.adapters.whatsapp.settings") as mock_settings:
            mock_settings.whatsapp_adapter_enabled = True
            mock_settings.whatsapp_bridge_url = "http://test:3002"
            mock_settings.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
                mock_client_cls.return_value = mock_client

                with pytest.raises(AdapterAuthError, match="unreachable"):
                    await adapter.authenticate()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_auth_bridge_logged_out(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"

        with patch("anveshak.social.adapters.whatsapp.settings") as mock_settings:
            mock_settings.whatsapp_adapter_enabled = True
            mock_settings.whatsapp_bridge_url = "http://test:3002"
            mock_settings.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("logged_out")
                mock_resp.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                with pytest.raises(AdapterAuthError, match="logged out"):
                    await adapter.authenticate()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_auth_disabled_no_exception(self):
        adapter = WhatsAppAdapter()

        with patch("anveshak.social.adapters.whatsapp.settings") as mock_settings:
            mock_settings.whatsapp_adapter_enabled = False
            await adapter.authenticate()
            assert adapter._connected is False


# ---------------------------------------------------------------------------
# collect() tests
# ---------------------------------------------------------------------------


class TestWhatsAppCollect:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_drains_buffer(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text="msg1"),
                _buffer_msg(text="msg2"),
                _buffer_msg(text="msg3"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect(
                        ["keywords"], ["120363001234567890@g.us"], "topic-1"
                    )
                ]

        assert len(items) == 3
        assert items[0].raw_text == "msg1"
        assert items[0].platform == "whatsapp"
        assert items[0].source_handle == "120363001234567890@g.us"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_filters_by_source_handles(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(group_jid="group-a@g.us", text="wanted"),
                _buffer_msg(group_jid="group-b@g.us", text="unwanted"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [item async for item in adapter.collect([], ["group-a@g.us"], "topic-1")]

        assert len(items) == 1
        assert items[0].raw_text == "wanted"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_respects_drain_max(self):
        redis_mock = AsyncMock()
        # More messages than drain_max
        redis_mock.lpop = AsyncMock(
            side_effect=[_buffer_msg(text=f"msg{i}") for i in range(10)] + [None]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 2
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                [item async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")]

        # Should have called lpop at most drain_max times
        assert redis_mock.lpop.call_count == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_empty_buffer(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(return_value=None)
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert len(items) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_media_only_message(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text=None, media_path="/app/media/group/2026/06/24/abc.jpg"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert len(items) == 1
        assert "[media:image]" in items[0].raw_text
        assert items[0].media_urls == ["/app/media/group/2026/06/24/abc.jpg"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_skip_no_text_no_media(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text=None, media_path=None),  # should be skipped
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert len(items) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_malformed_json_skipped(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                b"not-valid-json{{{",
                _buffer_msg(text="valid"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert len(items) == 1
        assert items[0].raw_text == "valid"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_timestamp_utc(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text="msg", timestamp=1719200400),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert items[0].captured_at.tzinfo is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_media_path_traversal_rejected(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text="has media", media_path="/../../../etc/passwd"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        # Item is still yielded (has text) but media_urls should be empty
        assert len(items) == 1
        assert items[0].media_urls == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_logout_sentinel_raises(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _logout_sentinel(),
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                with pytest.raises(AdapterAuthError, match="logged out"):
                    [
                        item
                        async for item in adapter.collect(
                            [], ["120363001234567890@g.us"], "topic-1"
                        )
                    ]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_health_check_logged_out(self):
        redis_mock = AsyncMock()
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("logged_out")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                with pytest.raises(AdapterAuthError, match="logged out"):
                    [
                        item
                        async for item in adapter.collect(
                            [], ["120363001234567890@g.us"], "topic-1"
                        )
                    ]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_author_fields(self):
        redis_mock = AsyncMock()
        redis_mock.lpop = AsyncMock(
            side_effect=[
                _buffer_msg(text="test", sender="919876543210@s.whatsapp.net", sender_name="Ravi"),
                None,
            ]
        )
        adapter = _make_adapter(redis_mock)

        with patch("anveshak.social.adapters.whatsapp.settings") as ms:
            ms.whatsapp_buffer_drain_max = 100
            ms.media_storage_root = "/app/media"
            ms.whatsapp_bridge_url = "http://test:3002"
            ms.whatsapp_bridge_token = ""

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = _bridge_health("connected")
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                items = [
                    item
                    async for item in adapter.collect([], ["120363001234567890@g.us"], "topic-1")
                ]

        assert items[0].author_id == "919876543210@s.whatsapp.net"
        assert items[0].author_handle == "Ravi"


# ---------------------------------------------------------------------------
# health() tests
# ---------------------------------------------------------------------------


class TestWhatsAppHealth:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_connected(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"
        adapter._bridge_token = ""

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _bridge_health("connected")
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await adapter.health()

        assert result["status"] == "HEALTHY"
        assert "checked_at" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_bridge_down(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"
        adapter._bridge_token = ""

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=ConnectionError("down"))
            mock_client_cls.return_value = mock_client

            result = await adapter.health()

        assert result["status"] == "DOWN"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_logged_out(self):
        adapter = WhatsAppAdapter()
        adapter._bridge_url = "http://test:3002"
        adapter._bridge_token = ""

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _bridge_health("logged_out")
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await adapter.health()

        assert result["status"] == "DOWN"
