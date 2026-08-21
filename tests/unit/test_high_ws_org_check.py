"""Unit tests for WebSocket org boundary check — HIGH-8.

A non-super-admin JWT missing org_id should be rejected with code 4003.
Super-admin (role=super-admin) can connect without org_id to see all signals.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestWebSocketOrgBoundary:
    @pytest.mark.asyncio
    async def test_analyst_without_org_id_rejected(self):
        """Non-super-admin with missing org_id → close 4003."""
        from anveshak.api.routes.signals import signal_websocket

        ws = _make_ws()
        payload = {"sub": "user-1", "role": "analyst"}  # no org_id!

        with patch("anveshak.api.auth.jwt.verify_token", return_value=payload) as _:
            await signal_websocket(ws, "session-1", token="fake.jwt")

        ws.close.assert_called_once()
        close_code = ws.close.call_args[1].get("code") or ws.close.call_args[0][0]
        assert close_code == 4003

    @pytest.mark.asyncio
    async def test_super_admin_without_org_id_accepted(self):
        """Super-admin can connect without org_id — sees all signals."""
        from anveshak.api.routes.signals import signal_websocket

        ws = _make_ws()
        payload = {"sub": "admin-1", "role": "super-admin"}  # no org_id, but super-admin

        with (
            patch("anveshak.api.auth.jwt.verify_token", return_value=payload) as _,
            patch("anveshak.api.db.pool.get_pool", return_value=None),
        ):
            # Will accept and enter ping loop — mock sleep to break it
            ws.send_json = AsyncMock(side_effect=Exception("break loop"))
            try:
                await signal_websocket(ws, "session-1", token="fake.jwt")
            except Exception:
                pass

        ws.accept.assert_called_once()
        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyst_with_org_id_accepted(self):
        """Normal analyst with org_id → accepted."""
        from anveshak.api.routes.signals import signal_websocket

        ws = _make_ws()
        payload = {"sub": "user-1", "role": "analyst", "org_id": "org-1"}

        with (
            patch("anveshak.api.auth.jwt.verify_token", return_value=payload) as _,
            patch("anveshak.api.db.pool.get_pool", return_value=None),
        ):
            ws.send_json = AsyncMock(side_effect=Exception("break loop"))
            try:
                await signal_websocket(ws, "session-1", token="fake.jwt")
            except Exception:
                pass

        ws.accept.assert_called_once()
