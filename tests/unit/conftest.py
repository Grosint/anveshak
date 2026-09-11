"""Unit test conftest — shared mocks and model factories.

All unit tests are pure: no database, no network, no Docker.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Auto-apply unit marker to all tests in this directory
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Shared mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_conn() -> AsyncMock:
    """Mock asyncpg connection — used by DB function unit tests."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def mock_pool(mock_conn) -> MagicMock:
    """Mock asyncpg pool that yields mock_conn on acquire."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

SAMPLE_LABELS = {
    "classification": "OPEN",
    "domain": "osint",
    "owner_org": "anveshak",
}


# ---------------------------------------------------------------------------
# Outbound fetch helpers
# ---------------------------------------------------------------------------
#
# Every outbound fetch runs through anveshak.net.safe_fetch, which resolves the
# host, connects to the address it approved and revalidates each redirect hop.
# A test therefore fixes two things rather than standing in for the client:
# the transport that answers, and the answer the resolver gives.


_REAL_ASYNC_CLIENT = httpx.AsyncClient


@contextlib.contextmanager
def _serve_over_mock_transport(handler, addresses: list[str] | None = None):
    """Serve handler to the guarded fetch path, with resolution fixed."""

    def _factory(*args, **kwargs):
        # A proxy would mount its own transport ahead of this one, and a test
        # transport already stands in for whatever the proxy would have reached.
        kwargs.pop("proxy", None)
        kwargs.pop("mounts", None)
        return _REAL_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch("anveshak.net.safe_fetch.httpx.AsyncClient", new=_factory),
        patch(
            "anveshak.net.url_safety._resolve_host",
            new=AsyncMock(return_value=addresses or ["93.184.216.34"]),
        ),
    ):
        yield


def _serve_bytes(
    content: bytes,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    addresses: list[str] | None = None,
):
    """Serve one fixed response to every request the fetch path makes.

    addresses fixes what the host resolves to, for a test about the guard's
    verdict rather than about the body.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers=headers or {})

    return _serve_over_mock_transport(handler, addresses)


def _serve_error(exc: Exception):
    """Fail every request the fetch path makes, as an unreachable host would."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return _serve_over_mock_transport(handler)


@pytest.fixture
def serve_bytes():
    """Serve fixed bytes to the guarded fetch path: ``with serve_bytes(b"x"):``."""
    return _serve_bytes


@pytest.fixture
def serve_error():
    """Fail every guarded fetch: ``with serve_error(httpx.ConnectError("...")):``."""
    return _serve_error


@pytest.fixture
def serve_handler():
    """Serve a per-request handler, for a test asserting on the hops themselves."""
    return _serve_over_mock_transport
