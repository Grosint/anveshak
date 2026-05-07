"""Integration test conftest — shared fixtures for real-infra tests.

All integration tests use real PostgreSQL and Redis via Docker Compose.
Fixtures from the root conftest.py (db_pool, make_topic, make_source, etc.)
are automatically available here.
"""
from __future__ import annotations

import pytest

# Auto-apply markers to all tests in this directory
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
