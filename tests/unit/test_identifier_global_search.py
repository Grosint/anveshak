"""Unit tests for global identifier search + convergence — cross-topic, org-scoped.

Endpoints:
  GET /api/v1/identifiers/search-global — cross-topic identifier search
  GET /api/v1/identifiers/convergence   — identifiers appearing in 2+ topics
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from anveshak.api.db.identifiers import (
    SQL_IDENTIFIER_CONVERGENCE,
    SQL_SEARCH_IDENTIFIERS_GLOBAL,
    SQL_SEARCH_IDENTIFIERS_GLOBAL_WITH_TYPE,
    get_identifier_convergence,
    search_identifiers_global,
)
from anveshak.api.routes.identifiers import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ORG_ID = "org-001"
TOPIC_A = "topic-001"
TOPIC_B = "topic-002"


def _fake_global_result(
    *,
    identifier_type: str = "PHONE_IN",
    identifier_value: str = "9876543210",
    topic_id: str = TOPIC_A,
    topic_name: str = "Cyber Fraud Ring X",
    source_count: int = 5,
    content_item_count: int = 12,
    last_seen_at: datetime | None = None,
) -> dict:
    return {
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "source_count": source_count,
        "content_item_count": content_item_count,
        "last_seen_at": last_seen_at or datetime.now(timezone.utc),
    }


# ===========================================================================
# 1. SQL constants exist and are well-formed
# ===========================================================================

class TestGlobalSearchSQL:
    """Verify SQL constants for global identifier search."""

    def test_sql_constant_exists(self):
        assert SQL_SEARCH_IDENTIFIERS_GLOBAL is not None

    def test_sql_with_type_constant_exists(self):
        assert SQL_SEARCH_IDENTIFIERS_GLOBAL_WITH_TYPE is not None

    def test_sql_joins_topics_for_name(self):
        sql = SQL_SEARCH_IDENTIFIERS_GLOBAL.lower()
        assert "topics" in sql
        assert "topic_name" in sql or "t.name" in sql

    def test_sql_filters_by_org_id(self):
        """CRITICAL: cross-topic query MUST filter by org_id."""
        sql = SQL_SEARCH_IDENTIFIERS_GLOBAL.lower()
        assert "org_id" in sql

    def test_sql_uses_ilike_for_partial_match(self):
        sql = SQL_SEARCH_IDENTIFIERS_GLOBAL.lower()
        assert "ilike" in sql

    def test_sql_orders_by_source_count(self):
        sql = SQL_SEARCH_IDENTIFIERS_GLOBAL.lower()
        assert "source_count" in sql
        assert "desc" in sql

    def test_type_filter_sql_has_identifier_type(self):
        sql = SQL_SEARCH_IDENTIFIERS_GLOBAL_WITH_TYPE.lower()
        assert "identifier_type" in sql


# ===========================================================================
# 2. DB function: search_identifiers_global
# ===========================================================================

class TestSearchIdentifiersGlobal:
    """DB function: cross-topic identifier search, org-scoped."""

    @pytest.mark.asyncio
    async def test_returns_matching_rows(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_global_result()]

        result = await search_identifiers_global(
            conn, q="9876543210", org_id=ORG_ID,
        )
        assert len(result) == 1
        assert result[0]["identifier_value"] == "9876543210"

    @pytest.mark.asyncio
    async def test_includes_topic_name(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            _fake_global_result(topic_name="Cyber Fraud Ring X"),
        ]

        result = await search_identifiers_global(
            conn, q="987654", org_id=ORG_ID,
        )
        assert result[0]["topic_name"] == "Cyber Fraud Ring X"

    @pytest.mark.asyncio
    async def test_includes_topic_id(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            _fake_global_result(topic_id=TOPIC_A),
        ]

        result = await search_identifiers_global(
            conn, q="987654", org_id=ORG_ID,
        )
        assert result[0]["topic_id"] == TOPIC_A

    @pytest.mark.asyncio
    async def test_scopes_to_org(self):
        """Query MUST pass org_id to SQL — cross-org leak prevention."""
        conn = AsyncMock()
        conn.fetch.return_value = []

        await search_identifiers_global(conn, q="test", org_id=ORG_ID)
        args = conn.fetch.call_args[0]
        assert ORG_ID in args

    @pytest.mark.asyncio
    async def test_filters_by_type(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_global_result()]

        await search_identifiers_global(
            conn, q="987", org_id=ORG_ID, identifier_type="PHONE_IN",
        )
        sql = conn.fetch.call_args[0][0]
        assert "identifier_type" in sql

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await search_identifiers_global(
            conn, q="test", org_id=ORG_ID, limit=10,
        )
        args = conn.fetch.call_args[0]
        assert 10 in args

    @pytest.mark.asyncio
    async def test_results_across_multiple_topics(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            _fake_global_result(topic_id=TOPIC_A, topic_name="Case A"),
            _fake_global_result(topic_id=TOPIC_B, topic_name="Case B"),
        ]

        result = await search_identifiers_global(
            conn, q="9876543210", org_id=ORG_ID,
        )
        assert len(result) == 2
        topic_ids = {r["topic_id"] for r in result}
        assert topic_ids == {TOPIC_A, TOPIC_B}

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        result = await search_identifiers_global(
            conn, q="nonexistent", org_id=ORG_ID,
        )
        assert result == []


# ===========================================================================
# 3. Route registration
# ===========================================================================

class TestGlobalSearchRoute:
    """Verify the search-global route is registered."""

    def test_route_exists(self):
        paths = [r.path for r in router.routes]
        assert "/api/v1/identifiers/search-global" in paths

    def test_route_is_get(self):
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/v1/identifiers/search-global":
                assert "GET" in route.methods
                break
        else:
            pytest.fail("search-global route not found")


# ===========================================================================
# 4. Convergence — SQL constants
# ===========================================================================

def _fake_convergence_result(
    *,
    identifier_type: str = "PHONE_IN",
    identifier_value: str = "9876543210",
    topic_count: int = 3,
    total_source_count: int = 8,
    topic_names: list[str] | None = None,
) -> dict:
    return {
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "topic_count": topic_count,
        "total_source_count": total_source_count,
        "topic_names": topic_names or ["Case A", "Case B", "Case C"],
    }


class TestConvergenceSQL:
    """Verify SQL constants for identifier convergence."""

    def test_sql_constant_exists(self):
        assert SQL_IDENTIFIER_CONVERGENCE is not None

    def test_sql_groups_by_identifier(self):
        sql = SQL_IDENTIFIER_CONVERGENCE.lower()
        assert "group by" in sql
        assert "identifier_value" in sql

    def test_sql_filters_by_org_id(self):
        """CRITICAL: cross-topic query MUST filter by org_id."""
        sql = SQL_IDENTIFIER_CONVERGENCE.lower()
        assert "org_id" in sql

    def test_sql_requires_multiple_topics(self):
        """HAVING COUNT(DISTINCT topic_id) >= 2."""
        sql = SQL_IDENTIFIER_CONVERGENCE.lower()
        assert "having" in sql
        assert "topic_id" in sql

    def test_sql_orders_by_topic_count(self):
        sql = SQL_IDENTIFIER_CONVERGENCE.lower()
        assert "topic_count" in sql or "count" in sql
        assert "desc" in sql

    def test_sql_includes_topic_names(self):
        """Should aggregate topic names for display."""
        sql = SQL_IDENTIFIER_CONVERGENCE.lower()
        assert "array_agg" in sql or "string_agg" in sql


# ===========================================================================
# 5. Convergence — DB function
# ===========================================================================

class TestGetIdentifierConvergence:
    """DB function: identifiers appearing in 2+ topics, org-scoped."""

    @pytest.mark.asyncio
    async def test_returns_converging_identifiers(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_convergence_result()]

        result = await get_identifier_convergence(conn, org_id=ORG_ID)
        assert len(result) == 1
        assert result[0]["identifier_value"] == "9876543210"
        assert result[0]["topic_count"] == 3

    @pytest.mark.asyncio
    async def test_scopes_to_org(self):
        """Query MUST pass org_id — cross-org leak prevention."""
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_identifier_convergence(conn, org_id=ORG_ID)
        args = conn.fetch.call_args[0]
        assert ORG_ID in args

    @pytest.mark.asyncio
    async def test_includes_topic_names(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            _fake_convergence_result(topic_names=["Case A", "Case B"]),
        ]

        result = await get_identifier_convergence(conn, org_id=ORG_ID)
        assert "Case A" in result[0]["topic_names"]
        assert "Case B" in result[0]["topic_names"]

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_identifier_convergence(conn, org_id=ORG_ID, limit=5)
        args = conn.fetch.call_args[0]
        assert 5 in args

    @pytest.mark.asyncio
    async def test_empty_when_no_convergence(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        result = await get_identifier_convergence(conn, org_id=ORG_ID)
        assert result == []


# ===========================================================================
# 6. Convergence — Route registration
# ===========================================================================

class TestConvergenceRoute:
    """Verify the convergence route is registered."""

    def test_route_exists(self):
        paths = [r.path for r in router.routes]
        assert "/api/v1/identifiers/convergence" in paths

    def test_route_is_get(self):
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/v1/identifiers/convergence":
                assert "GET" in route.methods
                break
        else:
            pytest.fail("convergence route not found")
