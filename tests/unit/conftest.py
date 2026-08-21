"""Unit test conftest — shared mocks and model factories.

All unit tests are pure: no database, no network, no Docker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
