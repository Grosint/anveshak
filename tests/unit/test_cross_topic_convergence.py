"""Unit tests for cross-topic cluster convergence detection (Phase 6 — P2b).

Tests:
  - Convergence detection above/below threshold
  - Same-topic clusters excluded (SQL uses topic_a < topic_b)
  - Dedup within 24h window
  - Archived clusters excluded
  - Evidence JSON contains all IDs
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anveshak.analyst.convergence import (
    SQL_CONVERGENT_CLUSTERS,
    check_cross_topic_convergence,
)
from anveshak.analyst.signal_engine import _SIGNAL_TYPE_CROSS_TOPIC


# ---------------------------------------------------------------------------
# SQL validation tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_convergent_sql_excludes_same_topic():
    """SQL should use nc1.topic_id < nc2.topic_id to prevent same-topic comparison."""
    assert "nc1.topic_id < nc2.topic_id" in SQL_CONVERGENT_CLUSTERS


@pytest.mark.unit
def test_convergent_sql_excludes_archived():
    """SQL should filter out archived clusters."""
    assert "nc1.archived_at IS NULL" in SQL_CONVERGENT_CLUSTERS
    assert "nc2.archived_at IS NULL" in SQL_CONVERGENT_CLUSTERS


@pytest.mark.unit
def test_signal_type_constant():
    """Cross-topic signal type should be 'cross_topic_convergence'."""
    assert _SIGNAL_TYPE_CROSS_TOPIC == "cross_topic_convergence"


# ---------------------------------------------------------------------------
# check_cross_topic_convergence tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_convergence_detected_above_threshold():
    """Convergent pair above threshold should fire signal."""
    mock_conn = AsyncMock()

    # SQL_CONVERGENT_CLUSTERS returns one pair
    mock_conn.fetch.return_value = [
        {
            "cluster_a_id": "cluster-a",
            "topic_a_id": "topic-1",
            "cluster_a_label": "IAF Procurement",
            "cluster_b_id": "cluster-b",
            "topic_b_id": "topic-2",
            "cluster_b_label": "Defence Budget",
            "similarity": 0.92,
        },
    ]

    # is_duplicate_signal returns False (no dedup)
    mock_conn.fetchrow.return_value = None

    # SQL_INSERT_SIGNAL succeeds
    mock_conn.execute.return_value = "INSERT 0 1"

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    fired = await check_cross_topic_convergence(mock_pool)
    assert fired == 1
    assert mock_conn.execute.called


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_convergence_returns_zero():
    """No convergent pairs → 0 signals fired."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []  # no pairs above threshold

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    fired = await check_cross_topic_convergence(mock_pool)
    assert fired == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dedup_skips_duplicate_signal():
    """Duplicate signal within 24h should be skipped."""
    mock_conn = AsyncMock()

    mock_conn.fetch.return_value = [
        {
            "cluster_a_id": "cluster-a",
            "topic_a_id": "topic-1",
            "cluster_a_label": "Test",
            "cluster_b_id": "cluster-b",
            "topic_b_id": "topic-2",
            "cluster_b_label": "Test",
            "similarity": 0.90,
        },
    ]

    # is_duplicate_signal returns True (already fired)
    mock_conn.fetchrow.return_value = {"id": "existing-signal"}

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    fired = await check_cross_topic_convergence(mock_pool)
    assert fired == 0
    # execute should NOT have been called for INSERT (only fetch + fetchrow)
    mock_conn.execute.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evidence_contains_both_clusters():
    """Signal evidence JSON should contain both cluster and topic IDs."""
    import json

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "cluster_a_id": "c-aaa",
            "topic_a_id": "t-111",
            "cluster_a_label": "Label A",
            "cluster_b_id": "c-bbb",
            "topic_b_id": "t-222",
            "cluster_b_label": "Label B",
            "similarity": 0.88,
        },
    ]
    mock_conn.fetchrow.return_value = None  # no dedup
    mock_conn.execute.return_value = "INSERT 0 1"

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    await check_cross_topic_convergence(mock_pool)

    # Check the execute call args for SQL_INSERT_SIGNAL
    # Args: (SQL, signal_id, topic_a_id, cluster_a_id, signal_type, description, evidence, now)
    call_args = mock_conn.execute.call_args[0]
    evidence_json = call_args[6]  # 7th positional arg (index 6) is evidence
    evidence = json.loads(evidence_json)

    assert evidence["cluster_a_id"] == "c-aaa"
    assert evidence["cluster_b_id"] == "c-bbb"
    assert evidence["topic_a_id"] == "t-111"
    assert evidence["topic_b_id"] == "t-222"
    assert evidence["similarity"] == 0.88
