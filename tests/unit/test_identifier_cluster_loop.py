"""Unit tests for identifier_cluster_loop in analyst scheduler.

Verifies that the scheduler:
  1. Queries unclustered identifier entities per topic
  2. Calls build_clusters() from identifier_clustering.py
  3. Upserts results into identifier_clusters + identifier_cluster_items tables
  4. Loop is registered in scheduler lifespan

pytest.mark.unit -- no external dependencies, no DB, no network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SCHED_MOD = "anveshak.analyst.scheduler"


@pytest.mark.unit
class TestIdentifierClusterLoopExists:
    """scheduler.py must have identifier_cluster_loop function."""

    def test_function_exists(self):
        from anveshak.analyst.scheduler import identifier_cluster_loop

        assert callable(identifier_cluster_loop)


@pytest.mark.unit
class TestIdentifierClusterLoopRegistered:
    """identifier_cluster_loop must be in lifespan tasks."""

    def test_registered_in_lifespan(self):
        import inspect

        from anveshak.analyst import scheduler

        source = inspect.getsource(scheduler.lifespan)
        assert "identifier_cluster_loop" in source, (
            "identifier_cluster_loop must be registered in lifespan tasks"
        )


@pytest.mark.unit
class TestIdentifierClusterLoopQueriesEntities:
    """Loop must query extracted_entities with Engine C identifier types."""

    def test_sql_unclustered_identifiers_exists(self):
        from anveshak.analyst.scheduler import SQL_UNCLUSTERED_IDENTIFIERS

        sql_lower = SQL_UNCLUSTERED_IDENTIFIERS.lower()
        assert "extracted_entities" in sql_lower, "SQL must query extracted_entities table"
        assert (
            "identifier_cluster_items" in sql_lower
            or "not exists" in sql_lower
            or "left join" in sql_lower
        ), "SQL must filter out already-clustered entities"


@pytest.mark.unit
class TestIdentifierClusterLoopUpsertsCluster:
    """Loop must upsert into identifier_clusters table."""

    def test_sql_upsert_cluster_exists(self):
        from anveshak.analyst.scheduler import SQL_UPSERT_IDENTIFIER_CLUSTER

        sql_lower = SQL_UPSERT_IDENTIFIER_CLUSTER.lower()
        assert "identifier_clusters" in sql_lower, "SQL must target identifier_clusters table"
        assert "on conflict" in sql_lower, "SQL must use ON CONFLICT for idempotent upsert"


@pytest.mark.unit
class TestIdentifierClusterLoopInsertsItems:
    """Loop must insert into identifier_cluster_items junction table."""

    def test_sql_insert_cluster_item_exists(self):
        from anveshak.analyst.scheduler import SQL_INSERT_IDENTIFIER_CLUSTER_ITEM

        sql_lower = SQL_INSERT_IDENTIFIER_CLUSTER_ITEM.lower()
        assert "identifier_cluster_items" in sql_lower, (
            "SQL must target identifier_cluster_items table"
        )
        assert "on conflict" in sql_lower, "SQL must use ON CONFLICT DO NOTHING for idempotency"


@pytest.mark.unit
class TestIdentifierClusterLoopCallsBuildClusters:
    """Loop must call build_clusters from identifier_clustering module."""

    @pytest.mark.asyncio
    async def test_build_clusters_called(self):
        """Simulate one cycle: query returns entities → build_clusters called → upsert."""
        from anveshak.analyst.identifier_clustering import (
            IdentifierCluster,
        )

        now = datetime.now(timezone.utc)

        fake_entity_rows = [
            {
                "entity_type": "PHONE_IN",
                "entity_text": "9876543210",
                "confidence": 0.95,
                "content_item_id": "ci-1",
                "source_id": "src-1",
                "captured_at": now,
                "topic_id": "topic-1",
            },
            {
                "entity_type": "PHONE_IN",
                "entity_text": "9876543210",
                "confidence": 0.95,
                "content_item_id": "ci-2",
                "source_id": "src-2",
                "captured_at": now,
                "topic_id": "topic-1",
            },
        ]

        fake_cluster = IdentifierCluster(
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            content_item_ids=frozenset(["ci-1", "ci-2"]),
            source_ids=frozenset(["src-1", "src-2"]),
            source_count=2,
            content_item_count=2,
            first_seen_at=now,
            last_seen_at=now,
        )

        conn = AsyncMock()
        conn.fetch = AsyncMock(
            side_effect=[
                # First call: active topics
                [{"id": "topic-1"}],
                # Second call: unclustered identifiers for topic-1
                fake_entity_rows,
            ]
        )
        conn.fetchrow = AsyncMock(return_value={"id": "cluster-1"})
        conn.execute = AsyncMock()

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_SCHED_MOD}.build_clusters", return_value=[fake_cluster]) as mock_build,
        ):
            from anveshak.analyst.scheduler import _run_identifier_cluster_cycle

            await _run_identifier_cluster_cycle(pool)

        mock_build.assert_called_once()
        # Verify ContentIdentifier objects were passed
        call_args = mock_build.call_args
        identifiers = call_args.args[0]
        assert len(identifiers) == 2
        assert all(hasattr(i, "identifier_type") for i in identifiers)
