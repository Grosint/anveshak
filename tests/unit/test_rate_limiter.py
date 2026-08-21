"""Tests for rate_limit.py middleware functions.

Validates sliding window logic, client IP extraction, JWT sub extraction,
and the per-key window growth pattern.
"""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import MagicMock

import pytest

from services.api.anveshak.api.middleware.rate_limit import (
    _WINDOW_S,
    _check_rate,
    _client_ip,
    _jwt_sub,
    _windows,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_windows():
    """Prevent test pollution — clear the module-level _windows dict."""
    _windows.clear()
    yield
    _windows.clear()


def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "10.0.0.1",
) -> MagicMock:
    """Build a mock FastAPI Request with configurable headers and client."""
    req = MagicMock()
    req.headers = headers or {}
    req.client = MagicMock()
    req.client.host = client_host
    return req


def _make_jwt_token(payload: dict) -> str:
    """Build a fake JWT (header.payload.signature) with the given payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


# ---- Test 1: Under limit -> all allowed ----


@pytest.mark.unit
def test_check_rate_allows_under_limit() -> None:
    """5 requests under a limit of 10 should all be allowed."""
    for i in range(5):
        allowed, retry_after = _check_rate("test-key-1", 10)
        assert allowed is True, f"Request {i + 1} should be allowed"
        assert retry_after == 0


# ---- Test 2: At limit -> blocked with retry_after ----


@pytest.mark.unit
def test_check_rate_blocks_at_limit() -> None:
    """The 11th request at limit 10 should be blocked."""
    for _ in range(10):
        allowed, _ = _check_rate("test-key-2", 10)
        assert allowed is True

    allowed, retry_after = _check_rate("test-key-2", 10)
    assert allowed is False
    assert retry_after > 0


# ---- Test 3: Window slides — old timestamps evicted ----


@pytest.mark.unit
def test_check_rate_window_slides() -> None:
    """After the window expires, old timestamps are evicted and new requests allowed."""
    key = "test-key-3"
    # Fill up the limit
    for _ in range(5):
        _check_rate(key, 5)

    # All 5 slots used
    allowed, _ = _check_rate(key, 5)
    assert allowed is False

    # Manually age all timestamps beyond the window
    window = _windows[key]
    aged = time.monotonic() - _WINDOW_S - 1
    for i in range(len(window)):
        window[i] = aged

    # Now a new request should succeed (old ones evicted)
    allowed, retry_after = _check_rate(key, 5)
    assert allowed is True
    assert retry_after == 0


# ---- Test 4: X-Forwarded-For -> first IP ----


@pytest.mark.unit
def test_client_ip_from_forwarded_for() -> None:
    """X-Forwarded-For with multiple IPs returns the first one (client IP)."""
    req = _make_request(headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert _client_ip(req) == "1.2.3.4"


# ---- Test 5: No header -> falls back to request.client.host ----


@pytest.mark.unit
def test_client_ip_from_remote_addr() -> None:
    """Without X-Forwarded-For, fall back to request.client.host."""
    req = _make_request(client_host="192.168.1.50")
    assert _client_ip(req) == "192.168.1.50"


# ---- Test 6: Valid JWT -> extracts "sub" field ----


@pytest.mark.unit
def test_jwt_sub_extraction() -> None:
    """A valid base64 JWT should have its 'sub' field extracted."""
    token = _make_jwt_token({"sub": "analyst-42", "exp": 9999999999})
    req = _make_request(headers={"Authorization": f"Bearer {token}"})
    assert _jwt_sub(req) == "analyst-42"


# ---- Test 7: Malformed token -> returns None ----


@pytest.mark.unit
def test_jwt_sub_malformed_token() -> None:
    """Garbage token should return None, not raise."""
    req = _make_request(headers={"Authorization": "Bearer not.a.valid.token!!!"})
    assert _jwt_sub(req) is None


# ---- Test 8: No Bearer prefix -> returns None ----


@pytest.mark.unit
def test_jwt_sub_missing_bearer() -> None:
    """Authorization header without 'Bearer ' prefix returns None."""
    token = _make_jwt_token({"sub": "user-1"})
    req = _make_request(headers={"Authorization": f"Token {token}"})
    assert _jwt_sub(req) is None


# ---- Test 9: Unique keys create separate entries in _windows ----


@pytest.mark.unit
def test_windows_grow_per_key() -> None:
    """Each unique rate-limit key creates a new deque in _windows (verifying unbounded growth pattern)."""
    assert len(_windows) == 0

    for i in range(100):
        _check_rate(f"unique-key-{i}", 10)

    # Each key should have its own entry — this is the memory leak pattern
    assert len(_windows) == 100
    # Each window should have exactly 1 entry
    for i in range(100):
        assert len(_windows[f"unique-key-{i}"]) == 1
