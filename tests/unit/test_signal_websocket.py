"""Tests for WebSocket signal broadcast in services/api/anveshak/api/routes/signals.py.

Validates broadcast delivery, dead connection cleanup, and empty session handling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from services.api.anveshak.api.routes.signals import _sessions, broadcast_signal

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Ensure _sessions is empty before and after each test."""
    _sessions.clear()
    yield
    _sessions.clear()


def _make_ws(*, healthy: bool = True) -> AsyncMock:
    """Create a mock WebSocket. If not healthy, send_json raises."""
    ws = AsyncMock()
    if not healthy:
        ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))
    return ws


# ---- Test 1: Broadcast sends to all sessions ----


@pytest.mark.unit
async def test_broadcast_signal_sends_to_all_sessions() -> None:
    """Two connected sessions should both receive the signal payload."""
    ws1 = _make_ws()
    ws2 = _make_ws()
    now = datetime.now(UTC)
    _sessions["session-1"] = (ws1, now)
    _sessions["session-2"] = (ws2, now)

    signal = {"type": "signal", "signal_id": "sig-001", "severity": "high"}
    await broadcast_signal(signal)

    ws1.send_json.assert_awaited_once_with(signal)
    ws2.send_json.assert_awaited_once_with(signal)
    # Both sessions should remain
    assert "session-1" in _sessions
    assert "session-2" in _sessions


# ---- Test 2: Dead connection is removed ----


@pytest.mark.unit
async def test_broadcast_signal_removes_dead_sessions() -> None:
    """A session that raises on send_json gets removed from _sessions."""
    ws_healthy = _make_ws()
    ws_dead = _make_ws(healthy=False)
    now = datetime.now(UTC)
    _sessions["alive"] = (ws_healthy, now)
    _sessions["dead"] = (ws_dead, now)

    signal = {"type": "signal", "signal_id": "sig-002"}
    await broadcast_signal(signal)

    # Healthy session still present, dead one removed
    assert "alive" in _sessions
    assert "dead" not in _sessions
    # Healthy one still received the signal
    ws_healthy.send_json.assert_awaited_once_with(signal)


# ---- Test 3: Empty sessions -> no error ----


@pytest.mark.unit
async def test_broadcast_signal_empty_sessions() -> None:
    """Broadcasting with no connected sessions should not raise."""
    assert len(_sessions) == 0
    await broadcast_signal({"type": "signal", "signal_id": "sig-003"})
    # No exception, still empty
    assert len(_sessions) == 0
