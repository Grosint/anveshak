"""Unit tests for Engine C Step 7 — Identifier Search API.

Tests DB layer functions and route-level logic for 6 identifier endpoints:
  1. GET /identifiers/search — full-text + partial match
  2. GET /identifiers/top — most frequent identifiers by source_count
  3. GET /identifiers/clusters — list identifier clusters for a topic
  4. GET /identifiers/clusters/{cluster_id} — cluster detail with items + sources
  5. GET /identifiers/export — CSV/JSON export
  6. GET /identifiers/co-occurrence — content items sharing two identifiers
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# DB layer imports
# ---------------------------------------------------------------------------
from anveshak.api.db.identifiers import (
    export_identifiers,
    get_cluster_detail,
    get_co_occurrence,
    get_top_identifiers,
    list_identifier_clusters,
    search_identifiers,
)

# ---------------------------------------------------------------------------
# Route-level imports (SQL constants, helpers)
# ---------------------------------------------------------------------------
from anveshak.api.routes.identifiers import (
    EXPORT_COLUMNS,
    MAX_EXPORT_ROWS,
    _rows_to_csv,
    _rows_to_json,
    router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOPIC_ID = "topic-001"
CLUSTER_ID = "cluster-001"
ORG_ID = "org-001"


def _fake_user(role: str = "analyst", org_id: str = ORG_ID) -> dict:
    return {"sub": "user-1", "role": role, "org_id": org_id}


def _fake_search_row(
    *,
    entity_type: str = "PHONE_IN",
    entity_text: str = "9876543210",
    confidence: float = 0.95,
    content_item_id: str = "ci-001",
    content_url: str = "https://example.com/post/1",
    topic_id: str = TOPIC_ID,
) -> dict:
    return {
        "entity_type": entity_type,
        "entity_text": entity_text,
        "confidence": confidence,
        "content_item_id": content_item_id,
        "content_url": content_url,
        "topic_id": topic_id,
    }


def _fake_top_row(
    *,
    identifier_type: str = "PHONE_IN",
    identifier_value: str = "9876543210",
    source_count: int = 5,
    content_item_count: int = 12,
    first_seen_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "source_count": source_count,
        "content_item_count": content_item_count,
        "first_seen_at": first_seen_at or now,
        "last_seen_at": last_seen_at or now,
    }


def _fake_cluster_row(
    *,
    id: str = CLUSTER_ID,
    topic_id: str = TOPIC_ID,
    identifier_type: str = "UPI",
    identifier_value: str = "scammer@ybl",
    source_count: int = 3,
    content_item_count: int = 7,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": id,
        "topic_id": topic_id,
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "source_count": source_count,
        "content_item_count": content_item_count,
        "first_seen_at": now,
        "last_seen_at": now,
        "created_at": now,
    }


def _fake_cluster_item_row(
    *,
    content_item_id: str = "ci-001",
    source_id: str = "src-001",
    source_name: str = "Telegram: easy_money",
    source_platform: str = "telegram",
    content_url: str = "https://t.me/easy_money/42",
    captured_at: datetime | None = None,
) -> dict:
    return {
        "content_item_id": content_item_id,
        "source_id": source_id,
        "source_name": source_name,
        "source_platform": source_platform,
        "content_url": content_url,
        "captured_at": captured_at or datetime.now(timezone.utc),
    }


def _fake_co_occurrence_row(
    *,
    content_item_id: str = "ci-001",
    content_url: str = "https://example.com/post/1",
    captured_at: datetime | None = None,
    source_name: str = "Telegram: fraud_channel",
) -> dict:
    return {
        "content_item_id": content_item_id,
        "content_url": content_url,
        "captured_at": captured_at or datetime.now(timezone.utc),
        "source_name": source_name,
    }


def _fake_export_row(
    *,
    entity_type: str = "PHONE_IN",
    entity_text: str = "9876543210",
    confidence: float = 0.95,
    content_item_id: str = "ci-001",
    content_url: str = "https://example.com/1",
    source_name: str = "RSS: news",
    source_platform: str = "rss",
    captured_at: datetime | None = None,
) -> dict:
    return {
        "entity_type": entity_type,
        "entity_text": entity_text,
        "confidence": confidence,
        "content_item_id": content_item_id,
        "content_url": content_url,
        "source_name": source_name,
        "source_platform": source_platform,
        "captured_at": captured_at or datetime.now(timezone.utc),
    }


# ===========================================================================
# 1. search_identifiers
# ===========================================================================

class TestSearchIdentifiers:
    """DB function: search extracted_entities with partial match."""

    @pytest.mark.asyncio
    async def test_returns_matching_rows(self):
        conn = AsyncMock()
        row = _fake_search_row()
        conn.fetch.return_value = [row]

        result = await search_identifiers(
            conn, q="9876543210", topic_id=TOPIC_ID,
        )
        assert len(result) == 1
        assert result[0]["entity_text"] == "9876543210"

    @pytest.mark.asyncio
    async def test_filters_by_identifier_type(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_search_row(entity_type="PHONE_IN")]

        await search_identifiers(
            conn, q="987654", topic_id=TOPIC_ID, identifier_type="PHONE_IN",
        )
        # SQL should contain type filter
        sql = conn.fetch.call_args[0][0]
        assert "entity_type" in sql

    @pytest.mark.asyncio
    async def test_partial_match_phone_suffix(self):
        """Last 6 digits of phone should match."""
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_search_row(entity_text="9876543210")]

        result = await search_identifiers(
            conn, q="543210", topic_id=TOPIC_ID,
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        result = await search_identifiers(
            conn, q="nonexistent", topic_id=TOPIC_ID,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await search_identifiers(
            conn, q="987", topic_id=TOPIC_ID, limit=10,
        )
        # Limit param passed to SQL
        args = conn.fetch.call_args[0]
        assert 10 in args

    @pytest.mark.asyncio
    async def test_scopes_to_topic(self):
        """Query must filter by topic_id for multi-tenancy."""
        conn = AsyncMock()
        conn.fetch.return_value = []

        await search_identifiers(conn, q="test", topic_id=TOPIC_ID)
        args = conn.fetch.call_args[0]
        assert TOPIC_ID in args


# ===========================================================================
# 2. get_top_identifiers
# ===========================================================================

class TestGetTopIdentifiers:
    """DB function: most frequent identifiers from extracted_entities (grouped)."""

    @pytest.mark.asyncio
    async def test_returns_sorted_by_item_count(self):
        conn = AsyncMock()
        rows = [
            _fake_top_row(identifier_value="9876543210", source_count=5, content_item_count=12),
            _fake_top_row(identifier_value="easy@ybl", source_count=1, content_item_count=8),
        ]
        conn.fetch.return_value = rows

        result = await get_top_identifiers(conn, topic_id=TOPIC_ID)
        assert len(result) == 2
        # Should return both — not just multi-source clusters
        assert result[0]["content_item_count"] >= result[1]["content_item_count"]

    @pytest.mark.asyncio
    async def test_filters_by_type(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_top_row()]

        await get_top_identifiers(
            conn, topic_id=TOPIC_ID, identifier_type="PHONE_IN",
        )
        sql = conn.fetch.call_args[0][0]
        assert "entity_type" in sql or "identifier_type" in sql

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_top_identifiers(conn, topic_id=TOPIC_ID, limit=5)
        args = conn.fetch.call_args[0]
        assert 5 in args

    @pytest.mark.asyncio
    async def test_empty_topic_returns_empty(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        result = await get_top_identifiers(conn, topic_id="empty-topic")
        assert result == []

    @pytest.mark.asyncio
    async def test_queries_extracted_entities_not_clusters(self):
        """Top should query extracted_entities directly, not identifier_clusters."""
        from anveshak.api.db.identifiers import SQL_TOP_IDENTIFIERS
        sql = SQL_TOP_IDENTIFIERS.lower()
        assert "extracted_entities" in sql
        assert "identifier_clusters" not in sql

    @pytest.mark.asyncio
    async def test_groups_by_type_and_value(self):
        """SQL must GROUP BY to aggregate across content items."""
        from anveshak.api.db.identifiers import SQL_TOP_IDENTIFIERS
        sql = SQL_TOP_IDENTIFIERS.lower()
        assert "group by" in sql

    @pytest.mark.asyncio
    async def test_accepts_min_items_param(self):
        """Should accept min_items to filter noise."""
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_top_identifiers(conn, topic_id=TOPIC_ID, min_items=2)
        args = conn.fetch.call_args[0]
        assert 2 in args

    @pytest.mark.asyncio
    async def test_single_source_identifiers_included(self):
        """Identifiers from 1 source but multiple items should appear."""
        conn = AsyncMock()
        conn.fetch.return_value = [
            _fake_top_row(
                identifier_type="PHONE_INTL",
                identifier_value="+85253385012",
                source_count=1,
                content_item_count=5,
            ),
        ]

        result = await get_top_identifiers(conn, topic_id=TOPIC_ID)
        assert len(result) == 1
        assert result[0]["identifier_type"] == "PHONE_INTL"
        assert result[0]["source_count"] == 1


# ===========================================================================
# 3. list_identifier_clusters
# ===========================================================================

class TestListIdentifierClusters:
    """DB function: list identifier clusters for a topic."""

    @pytest.mark.asyncio
    async def test_returns_clusters(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_cluster_row()]

        result = await list_identifier_clusters(conn, topic_id=TOPIC_ID)
        assert len(result) == 1
        assert result[0]["identifier_type"] == "UPI"

    @pytest.mark.asyncio
    async def test_filters_by_type(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_cluster_row(identifier_type="PHONE_IN")]

        await list_identifier_clusters(
            conn, topic_id=TOPIC_ID, identifier_type="PHONE_IN",
        )
        sql = conn.fetch.call_args[0][0]
        assert "identifier_type" in sql

    @pytest.mark.asyncio
    async def test_pagination(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await list_identifier_clusters(
            conn, topic_id=TOPIC_ID, limit=10, offset=20,
        )
        args = conn.fetch.call_args[0]
        assert 10 in args
        assert 20 in args

    @pytest.mark.asyncio
    async def test_sorted_by_source_count_desc(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await list_identifier_clusters(conn, topic_id=TOPIC_ID)
        sql = conn.fetch.call_args[0][0]
        assert "source_count" in sql.lower()
        assert "desc" in sql.lower()


# ===========================================================================
# 4. get_cluster_detail
# ===========================================================================

class TestGetClusterDetail:
    """DB function: full cluster detail with items and sources."""

    @pytest.mark.asyncio
    async def test_returns_cluster_with_items(self):
        conn = AsyncMock()
        cluster_row = _fake_cluster_row()
        item_rows = [
            _fake_cluster_item_row(content_item_id="ci-001"),
            _fake_cluster_item_row(content_item_id="ci-002"),
        ]
        conn.fetchrow.return_value = cluster_row
        conn.fetch.return_value = item_rows

        result = await get_cluster_detail(conn, cluster_id=CLUSTER_ID)
        assert result is not None
        assert result["id"] == CLUSTER_ID
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_cluster(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None

        result = await get_cluster_detail(conn, cluster_id="nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_includes_source_breakdown(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = _fake_cluster_row()
        conn.fetch.return_value = [
            _fake_cluster_item_row(source_platform="telegram", source_name="S1"),
            _fake_cluster_item_row(source_platform="rss", source_name="S2"),
        ]

        result = await get_cluster_detail(conn, cluster_id=CLUSTER_ID)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_includes_cluster_metadata(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = _fake_cluster_row(
            identifier_type="CRYPTO_BTC",
            identifier_value="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        )
        conn.fetch.return_value = []

        result = await get_cluster_detail(conn, cluster_id=CLUSTER_ID)
        assert result["identifier_type"] == "CRYPTO_BTC"
        assert result["identifier_value"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


# ===========================================================================
# 5. export_identifiers
# ===========================================================================

class TestExportIdentifiers:
    """DB function: flat identifier export for CSV/JSON."""

    @pytest.mark.asyncio
    async def test_returns_flat_rows(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_export_row()]

        result = await export_identifiers(conn, topic_id=TOPIC_ID)
        assert len(result) == 1
        assert "entity_type" in result[0]
        assert "entity_text" in result[0]

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await export_identifiers(conn, topic_id=TOPIC_ID, limit=500)
        args = conn.fetch.call_args[0]
        assert 500 in args

    @pytest.mark.asyncio
    async def test_includes_source_metadata(self):
        conn = AsyncMock()
        row = _fake_export_row(source_name="Telegram: fraud", source_platform="telegram")
        conn.fetch.return_value = [row]

        result = await export_identifiers(conn, topic_id=TOPIC_ID)
        assert result[0]["source_name"] == "Telegram: fraud"
        assert result[0]["source_platform"] == "telegram"


# ===========================================================================
# 6. get_co_occurrence
# ===========================================================================

class TestGetCoOccurrence:
    """DB function: content items where both identifiers appear."""

    @pytest.mark.asyncio
    async def test_returns_shared_items(self):
        conn = AsyncMock()
        conn.fetch.return_value = [_fake_co_occurrence_row()]

        result = await get_co_occurrence(
            conn,
            topic_id=TOPIC_ID,
            identifier_a="9876543210",
            identifier_b="easy@ybl",
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_when_no_overlap(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        result = await get_co_occurrence(
            conn,
            topic_id=TOPIC_ID,
            identifier_a="111",
            identifier_b="222",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_scopes_to_topic(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_co_occurrence(
            conn, topic_id=TOPIC_ID,
            identifier_a="a", identifier_b="b",
        )
        args = conn.fetch.call_args[0]
        assert TOPIC_ID in args

    @pytest.mark.asyncio
    async def test_both_identifiers_in_query(self):
        conn = AsyncMock()
        conn.fetch.return_value = []

        await get_co_occurrence(
            conn, topic_id=TOPIC_ID,
            identifier_a="phone123", identifier_b="upi@bank",
        )
        args = conn.fetch.call_args[0]
        assert "phone123" in args
        assert "upi@bank" in args


# ===========================================================================
# 7. Route-level constants and structure
# ===========================================================================

class TestRouteConstants:
    """Verify route module exports expected constants."""

    def test_router_prefix(self):
        assert router.prefix == "/api/v1/identifiers"

    def test_export_columns_defined(self):
        assert isinstance(EXPORT_COLUMNS, list)
        assert "entity_type" in EXPORT_COLUMNS
        assert "entity_text" in EXPORT_COLUMNS

    def test_max_export_rows(self):
        assert MAX_EXPORT_ROWS == 10000

    def test_router_has_routes(self):
        """Router should have routes for all 6 endpoints."""
        paths = [r.path for r in router.routes]
        prefix = "/api/v1/identifiers"
        assert f"{prefix}/search" in paths
        assert f"{prefix}/top" in paths
        assert f"{prefix}/clusters" in paths
        assert f"{prefix}/clusters/{{cluster_id}}" in paths
        assert f"{prefix}/export" in paths
        assert f"{prefix}/co-occurrence" in paths


# ===========================================================================
# 8. SQL constants exist and are well-formed
# ===========================================================================

class TestSQLConstants:
    """Verify SQL constants are defined in DB module."""

    def test_search_sql_uses_trigram_or_like(self):
        from anveshak.api.db.identifiers import SQL_SEARCH_IDENTIFIERS
        sql = SQL_SEARCH_IDENTIFIERS.lower()
        # Must use ILIKE or trigram for partial match
        assert "ilike" in sql or "%" in sql or "similarity" in sql

    def test_top_sql_queries_extracted_entities(self):
        from anveshak.api.db.identifiers import SQL_TOP_IDENTIFIERS
        sql = SQL_TOP_IDENTIFIERS.lower()
        assert "extracted_entities" in sql
        assert "group by" in sql
        assert "desc" in sql

    def test_clusters_sql_scopes_to_topic(self):
        from anveshak.api.db.identifiers import SQL_LIST_CLUSTERS
        assert "topic_id" in SQL_LIST_CLUSTERS.lower()

    def test_cluster_detail_sql_joins_items(self):
        from anveshak.api.db.identifiers import SQL_CLUSTER_ITEMS
        sql = SQL_CLUSTER_ITEMS.lower()
        assert "identifier_cluster_items" in sql
        assert "join" in sql

    def test_export_sql_joins_sources(self):
        from anveshak.api.db.identifiers import SQL_EXPORT_IDENTIFIERS
        sql = SQL_EXPORT_IDENTIFIERS.lower()
        assert "source" in sql

    def test_co_occurrence_sql_self_joins(self):
        from anveshak.api.db.identifiers import SQL_CO_OCCURRENCE
        sql = SQL_CO_OCCURRENCE.lower()
        # Must join extracted_entities to itself
        assert "extracted_entities" in sql

    def test_identifier_type_filter_uses_partial_index_types(self):
        """When filtering by type, SQL should reference Engine C identifier types."""
        from anveshak.api.db.identifiers import SQL_SEARCH_IDENTIFIERS
        sql = SQL_SEARCH_IDENTIFIERS.lower()
        # Must filter by entity_type within identifier types
        assert "entity_type" in sql


# ===========================================================================
# 9. CSV/JSON export helpers
# ===========================================================================

class TestExportHelpers:
    """Test _rows_to_csv and _rows_to_json pure functions."""

    def test_csv_has_header_row(self):
        rows = [_fake_export_row()]
        result = _rows_to_csv(rows, EXPORT_COLUMNS)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == EXPORT_COLUMNS

    def test_csv_has_data_row(self):
        rows = [_fake_export_row(entity_text="9876543210")]
        result = _rows_to_csv(rows, EXPORT_COLUMNS)
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        data = next(reader)
        assert "9876543210" in data

    def test_csv_handles_none_values(self):
        row = _fake_export_row()
        row["confidence"] = None
        result = _rows_to_csv([row], EXPORT_COLUMNS)
        assert "None" not in result  # None → empty string

    def test_csv_multiple_rows(self):
        rows = [
            _fake_export_row(entity_text="aaa"),
            _fake_export_row(entity_text="bbb"),
        ]
        result = _rows_to_csv(rows, EXPORT_COLUMNS)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # header + 2 data

    def test_json_valid(self):
        rows = [_fake_export_row()]
        result = _rows_to_json(rows)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_json_handles_datetime(self):
        rows = [_fake_export_row()]
        result = _rows_to_json(rows)
        # Should not raise — datetime serialized via default=str
        parsed = json.loads(result)
        assert "captured_at" in parsed[0]

    def test_csv_empty_rows(self):
        result = _rows_to_csv([], EXPORT_COLUMNS)
        lines = result.strip().split("\n")
        assert len(lines) == 1  # header only
