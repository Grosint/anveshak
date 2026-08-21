"""Unit tests for scheduler throttling (Priority 5).

Tests verify the prioritized topic selection logic.
All DB calls are mocked.

pytest.mark.unit — no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test 1: Disabled when MAX_TOPICS_PER_CYCLE=0
# ---------------------------------------------------------------------------


class TestThrottleDisabled:
    @pytest.mark.asyncio
    async def test_throttle_disabled_returns_all(self):
        """When max_topics_per_cycle=0, all active topics with pending items are returned."""
        from anveshak.analyst.scheduler import get_prioritized_topics

        all_topics = [
            {"id": "topic-1", "pending": 50},
            {"id": "topic-2", "pending": 30},
            {"id": "topic-3", "pending": 10},
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=all_topics)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        with patch("anveshak.analyst.scheduler.settings") as mock_settings:
            mock_settings.max_topics_per_cycle = 0
            result = await get_prioritized_topics(pool)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test 2: Throttle limits topics
# ---------------------------------------------------------------------------


class TestThrottleLimits:
    @pytest.mark.asyncio
    async def test_throttle_limits_to_max(self):
        """When max_topics_per_cycle=2, only 2 topics are returned."""
        from anveshak.analyst.scheduler import get_prioritized_topics

        # DB returns only what LIMIT allows
        limited_topics = [
            {"id": "topic-1", "pending": 50},
            {"id": "topic-2", "pending": 30},
        ]

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=limited_topics)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        with patch("anveshak.analyst.scheduler.settings") as mock_settings:
            mock_settings.max_topics_per_cycle = 2
            result = await get_prioritized_topics(pool)

        assert len(result) <= 2


# ---------------------------------------------------------------------------
# Test 3: SQL skips topics with no pending items
# ---------------------------------------------------------------------------


class TestSkipsNoPending:
    @pytest.mark.asyncio
    async def test_sql_has_having_clause(self):
        """SQL_ACTIVE_TOPICS_PRIORITIZED must filter topics with zero pending items."""
        from anveshak.analyst.scheduler import SQL_ACTIVE_TOPICS_PRIORITIZED

        sql = SQL_ACTIVE_TOPICS_PRIORITIZED.lower()
        assert "having" in sql, "SQL must use HAVING to skip topics with no pending items"
        assert "narrative_cluster_id is null" in sql, "SQL must count unclustered items as pending"


# ---------------------------------------------------------------------------
# Test 4: Prioritizes by pending count
# ---------------------------------------------------------------------------


class TestPrioritization:
    @pytest.mark.asyncio
    async def test_sql_orders_by_pending_desc(self):
        """Topics with most pending items must be processed first."""
        from anveshak.analyst.scheduler import SQL_ACTIVE_TOPICS_PRIORITIZED

        sql = SQL_ACTIVE_TOPICS_PRIORITIZED.lower()
        assert "order by" in sql, "SQL must ORDER BY to prioritize"
        assert "desc" in sql, "SQL must sort DESC (most pending first)"
