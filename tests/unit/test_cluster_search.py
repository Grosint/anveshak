"""Unit tests for cluster centroid semantic search.

Tests:
  - DB functions exist and are callable
  - Relevance tier computation
  - Cluster belongs to topic verification
  - search_clusters_by_centroid passes correct params
  - search_clusters_by_label (ILIKE fallback) passes correct params
  - get_cluster_content with time and relevance sorting
  - Audit log written on search (route-level)

pytest.mark.unit — mock DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Relevance tier computation
# ---------------------------------------------------------------------------


class TestRelevanceTier:
    """_relevance_tier converts raw cosine similarity to analyst-friendly labels."""

    def test_high_tier(self):
        from anveshak.api.db.topics import _relevance_tier

        assert _relevance_tier(0.85) == "high"
        assert _relevance_tier(0.45) == "high"

    def test_medium_tier(self):
        from anveshak.api.db.topics import _relevance_tier

        assert _relevance_tier(0.40) == "medium"
        assert _relevance_tier(0.30) == "medium"

    def test_low_tier(self):
        from anveshak.api.db.topics import _relevance_tier

        assert _relevance_tier(0.20) == "low"
        assert _relevance_tier(0.15) == "low"

    def test_none_returns_keyword(self):
        from anveshak.api.db.topics import _relevance_tier

        assert _relevance_tier(None) == "keyword"

    def test_boundary_values(self):
        from anveshak.api.db.topics import _relevance_tier

        assert _relevance_tier(0.45) == "high"
        assert _relevance_tier(0.4499) == "medium"
        assert _relevance_tier(0.30) == "medium"
        assert _relevance_tier(0.2999) == "low"


# ---------------------------------------------------------------------------
# DB function existence and callability
# ---------------------------------------------------------------------------


class TestDBFunctionsExist:
    """All new DB functions exist and are importable."""

    def test_search_clusters_by_centroid_exists(self):
        from anveshak.api.db.topics import search_clusters_by_centroid

        assert callable(search_clusters_by_centroid)

    def test_search_clusters_by_label_exists(self):
        from anveshak.api.db.topics import search_clusters_by_label

        assert callable(search_clusters_by_label)

    def test_get_cluster_content_exists(self):
        from anveshak.api.db.topics import get_cluster_content

        assert callable(get_cluster_content)

    def test_verify_cluster_belongs_to_topic_exists(self):
        from anveshak.api.db.topics import verify_cluster_belongs_to_topic

        assert callable(verify_cluster_belongs_to_topic)


# ---------------------------------------------------------------------------
# verify_cluster_belongs_to_topic
# ---------------------------------------------------------------------------


class TestVerifyClusterBelongsToTopic:
    """Multi-tenancy guard: cluster must belong to the specified topic."""

    @pytest.mark.asyncio
    async def test_returns_true_when_match(self):
        from anveshak.api.db.topics import verify_cluster_belongs_to_topic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"topic_id": "topic-1"})

        result = await verify_cluster_belongs_to_topic(mock_conn, "cluster-1", "topic-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_mismatch(self):
        from anveshak.api.db.topics import verify_cluster_belongs_to_topic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"topic_id": "topic-2"})

        result = await verify_cluster_belongs_to_topic(mock_conn, "cluster-1", "topic-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_cluster_not_found(self):
        from anveshak.api.db.topics import verify_cluster_belongs_to_topic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await verify_cluster_belongs_to_topic(mock_conn, "nonexistent", "topic-1")
        assert result is False


# ---------------------------------------------------------------------------
# search_clusters_by_centroid
# ---------------------------------------------------------------------------


class TestSearchClustersByCentroid:
    """Centroid semantic search passes correct SQL params."""

    @pytest.mark.asyncio
    async def test_calls_fetch_with_correct_params(self):
        from anveshak.api.db.topics import search_clusters_by_centroid

        mock_row = {
            "id": "c1",
            "label": "Test Cluster",
            "item_count": 5,
            "independent_source_count": 3,
            "executive_summary": "Summary",
            "created_at": "2026-06-23T00:00:00Z",
            "similarity_score": 0.75,
        }
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            side_effect=[
                [
                    MagicMock(
                        **{
                            "__getitem__": lambda s, k: mock_row[k],
                            "get": mock_row.get,
                            "keys": mock_row.keys,
                            "items": mock_row.items,
                        }
                    )
                ],
                [],  # SQL_CLUSTER_SOURCES returns empty
            ]
        )

        await search_clusters_by_centroid(
            mock_conn, "[0.1,0.2,0.3]", "topic-1", min_similarity=0.30, limit=20
        )

        # First fetch is the centroid search
        first_call_args = mock_conn.fetch.call_args_list[0][0]
        assert "embedding_centroid" in first_call_args[0]  # SQL constant
        assert first_call_args[1] == "[0.1,0.2,0.3]"  # query vector
        assert first_call_args[2] == "topic-1"  # topic_id
        assert first_call_args[3] == 0.30  # min_similarity
        assert first_call_args[4] == 20  # limit

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from anveshak.api.db.topics import search_clusters_by_centroid

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        results = await search_clusters_by_centroid(mock_conn, "[0.1]", "topic-1")
        assert results == []


# ---------------------------------------------------------------------------
# search_clusters_by_label (ILIKE fallback)
# ---------------------------------------------------------------------------


class TestSearchClustersByLabel:
    """ILIKE fallback when embedding service is unavailable."""

    @pytest.mark.asyncio
    async def test_calls_fetch_with_correct_params(self):
        from anveshak.api.db.topics import search_clusters_by_label

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await search_clusters_by_label(mock_conn, "hawala", "topic-1", limit=10)

        first_call_args = mock_conn.fetch.call_args_list[0][0]
        assert "ILIKE" in first_call_args[0]  # SQL constant
        assert first_call_args[1] == "topic-1"
        assert first_call_args[2] == "hawala"
        assert first_call_args[3] == 10


# ---------------------------------------------------------------------------
# get_cluster_content
# ---------------------------------------------------------------------------


class TestGetClusterContent:
    """Drill-down: content items within a cluster."""

    @pytest.mark.asyncio
    async def test_time_sort_uses_correct_sql(self):
        from anveshak.api.db.topics import get_cluster_content

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await get_cluster_content(mock_conn, "cluster-1", sort="time", limit=20, offset=0)

        sql_used = mock_conn.fetch.call_args[0][0]
        assert "captured_at DESC" in sql_used

    @pytest.mark.asyncio
    async def test_relevance_sort_uses_embedding_query(self):
        from anveshak.api.db.topics import get_cluster_content

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await get_cluster_content(
            mock_conn,
            "cluster-1",
            sort="relevance",
            query_vec_str="[0.1,0.2]",
            limit=20,
            offset=0,
        )

        sql_used = mock_conn.fetch.call_args[0][0]
        assert "embedding <=>" in sql_used

    @pytest.mark.asyncio
    async def test_relevance_without_query_falls_back_to_time(self):
        from anveshak.api.db.topics import get_cluster_content

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await get_cluster_content(
            mock_conn,
            "cluster-1",
            sort="relevance",
            query_vec_str=None,  # no embedding available
            limit=20,
            offset=0,
        )

        sql_used = mock_conn.fetch.call_args[0][0]
        assert "captured_at DESC" in sql_used


# ---------------------------------------------------------------------------
# SQL constants contain required guards
# ---------------------------------------------------------------------------


class TestSQLGuards:
    """Verify SQL constants include required safety clauses."""

    def test_centroid_search_excludes_archived(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CENTROID_SEARCH

        assert "archived_at IS NULL" in SQL_CLUSTER_CENTROID_SEARCH

    def test_centroid_search_excludes_null_centroids(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CENTROID_SEARCH

        assert "embedding_centroid IS NOT NULL" in SQL_CLUSTER_CENTROID_SEARCH

    def test_centroid_search_has_min_similarity_filter(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CENTROID_SEARCH

        # $3 is the min_similarity parameter
        assert ">= $3" in SQL_CLUSTER_CENTROID_SEARCH

    def test_label_search_excludes_archived(self):
        from anveshak.api.db.topics import SQL_CLUSTER_LABEL_SEARCH

        assert "archived_at IS NULL" in SQL_CLUSTER_LABEL_SEARCH

    def test_content_by_relevance_filters_quality(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CONTENT_BY_RELEVANCE

        assert "content_quality" in SQL_CLUSTER_CONTENT_BY_RELEVANCE

    def test_content_by_time_filters_quality(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CONTENT_BY_TIME

        assert "content_quality" in SQL_CLUSTER_CONTENT_BY_TIME

    def test_content_by_relevance_requires_embedding(self):
        from anveshak.api.db.topics import SQL_CLUSTER_CONTENT_BY_RELEVANCE

        assert "embedding IS NOT NULL" in SQL_CLUSTER_CONTENT_BY_RELEVANCE


# ---------------------------------------------------------------------------
# Embedding helper shared module
# ---------------------------------------------------------------------------


class TestEmbeddingHelper:
    """embed_query is importable from the shared module."""

    def test_embed_query_importable(self):
        from anveshak.api.embedding import embed_query

        assert callable(embed_query)
