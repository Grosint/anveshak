"""Integration test conftest — shared fixtures for real-infra tests.

All integration tests use real PostgreSQL and Redis via Docker Compose.
Fixtures from the root conftest.py (db_pool, make_topic, make_source, etc.)
are automatically available here.
"""
from __future__ import annotations

import warnings

import asyncpg
import pytest

from tests.conftest import POSTGRES_URL

# Auto-apply markers to all tests in this directory
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(scope="session", autouse=True)
def _refuse_production_db():
    """Hard guard: refuse to run integration tests against the production database."""
    if POSTGRES_URL.rstrip("/").endswith("/anveshak") and "_test" not in POSTGRES_URL:
        pytest.exit(
            "SAFETY: Integration tests are targeting the production database "
            f"({POSTGRES_URL}). Set POSTGRES_TEST_URL or ensure the URL "
            "points to anveshak_test. Aborting.",
            returncode=1,
        )


@pytest.fixture(scope="session", autouse=True)
async def _leak_detector():
    """Post-session check: warn if integration tests leaked data into DB."""
    yield
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
    except Exception:
        return  # DB not available — skip check
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM topics WHERE "
            "name LIKE 'Test Topic %' OR name LIKE '%Test Topic' "
            "OR name LIKE 'Signal Test %' OR name LIKE 'E2E Validation%'"
        )
        if count > 0:
            warnings.warn(
                f"LEAK DETECTED: {count} test topics left in database after test run. "
                "Fix the leaking test's cleanup fixture.",
                stacklevel=1,
            )
    finally:
        await conn.close()
