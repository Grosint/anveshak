"""Unit tests for source effectiveness analytics (Phase 8)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# asyncio_mode = "auto" in pyproject.toml already marks the async tests here.
# An explicit asyncio mark also lands on the sync ones and emits a PytestWarning.
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Rank computation (pure function)
# ---------------------------------------------------------------------------


def test_compute_rank_most_recommended():
    """most_recommended: approved in 2+ topics AND contributed to 3+ signals."""
    from anveshak.analyst.effectiveness import compute_recommendation_rank

    rank = compute_recommendation_rank(
        topics_approved=3,
        signal_contributions=5,
        relevance_hit_rate=0.8,
    )
    assert rank == "most_recommended"


def test_compute_rank_proven():
    """proven: approved in 1+ topic AND items entered clusters."""
    from anveshak.analyst.effectiveness import compute_recommendation_rank

    rank = compute_recommendation_rank(
        topics_approved=1,
        signal_contributions=1,
        relevance_hit_rate=0.5,
    )
    assert rank == "proven"


def test_compute_rank_curated():
    """curated: never approved — pure catalog entry."""
    from anveshak.analyst.effectiveness import compute_recommendation_rank

    rank = compute_recommendation_rank(
        topics_approved=0,
        signal_contributions=0,
        relevance_hit_rate=None,
    )
    assert rank == "curated"


def test_compute_rank_low_performer():
    """low_performer: approved but < 10% items pass relevance gate after 2 weeks."""
    from anveshak.analyst.effectiveness import compute_recommendation_rank

    rank = compute_recommendation_rank(
        topics_approved=1,
        signal_contributions=0,
        relevance_hit_rate=0.05,
    )
    assert rank == "low_performer"


# ---------------------------------------------------------------------------
# Effectiveness job
# ---------------------------------------------------------------------------


async def test_compute_source_effectiveness_updates_catalog():
    """compute_source_effectiveness traces signals to sources and updates catalog."""
    from anveshak.analyst.effectiveness import compute_source_effectiveness

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock: one catalog entry with approval data
    mock_conn.fetch = AsyncMock(
        side_effect=[
            # SQL_APPROVED_CATALOG_ENTRIES
            [
                {
                    "catalog_entry_id": "ce1",
                    "source_id": "s1",
                    "topics_approved_count": 2,
                },
            ],
            # SQL_SIGNAL_CONTRIBUTIONS for source s1
            [{"signal_count": 5}],
            # SQL_RELEVANCE_HIT_RATE for source s1
            [{"hit_rate": 0.78}],
            # SQL_CLUSTER_PARTICIPATION for source s1
            [{"cluster_rate": 0.45}],
        ]
    )
    mock_conn.execute = AsyncMock()

    count = await compute_source_effectiveness(mock_pool)
    assert count == 1
    mock_conn.execute.assert_called_once()


async def test_compute_source_effectiveness_no_approvals():
    """compute_source_effectiveness returns 0 with no approved entries."""
    from anveshak.analyst.effectiveness import compute_source_effectiveness

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetch = AsyncMock(return_value=[])

    count = await compute_source_effectiveness(mock_pool)
    assert count == 0
