"""Unit tests for temporal windowing in clustering (Phase 3 — P1a).

Tests:
  - Old items excluded when window_days is set
  - All items included with large window
  - Archived clusters excluded from signal breaching query
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from anveshak.analyst.clustering import EmbeddingRow


# ---------------------------------------------------------------------------
# load_embeddings windowing tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_windowed_query_uses_filtered_sql():
    """When window_days > 0, SQL_TOPIC_EMBEDDINGS_WINDOWED should be used."""
    from anveshak.analyst.clustering import load_embeddings, SQL_TOPIC_EMBEDDINGS_WINDOWED

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acq

    result = await load_embeddings("topic-1", mock_pool, window_days=30)

    assert result == []
    mock_conn.fetch.assert_called_once_with(
        SQL_TOPIC_EMBEDDINGS_WINDOWED, "topic-1", 0.0, 30,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unwindowed_query_uses_original_sql():
    """When window_days = 0, SQL_TOPIC_EMBEDDINGS (original) should be used."""
    from anveshak.analyst.clustering import load_embeddings, SQL_TOPIC_EMBEDDINGS

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acq

    result = await load_embeddings("topic-1", mock_pool, window_days=0)

    assert result == []
    mock_conn.fetch.assert_called_once_with(
        SQL_TOPIC_EMBEDDINGS, "topic-1", 0.0,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_window_is_zero():
    """Default window_days should be 0 (no filtering) for backward compat."""
    from anveshak.analyst.clustering import load_embeddings, SQL_TOPIC_EMBEDDINGS

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []

    mock_pool = MagicMock()
    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acq

    await load_embeddings("topic-1", mock_pool)  # no window_days arg
    mock_conn.fetch.assert_called_once_with(SQL_TOPIC_EMBEDDINGS, "topic-1", 0.0)


# ---------------------------------------------------------------------------
# Signal engine archived cluster exclusion
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_breaching_clusters_sql_excludes_archived():
    """SQL_BREACHING_CLUSTERS must contain 'archived_at IS NULL' filter."""
    from anveshak.analyst.signal_engine import SQL_BREACHING_CLUSTERS
    assert "archived_at IS NULL" in SQL_BREACHING_CLUSTERS


# ---------------------------------------------------------------------------
# Archive SQL validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_archive_sql_uses_make_interval():
    """Archival SQL should use MAKE_INTERVAL for day-based comparison."""
    from anveshak.analyst.scheduler import SQL_ARCHIVE_OLD_CLUSTERS
    assert "MAKE_INTERVAL" in SQL_ARCHIVE_OLD_CLUSTERS
    assert "archived_at IS NULL" in SQL_ARCHIVE_OLD_CLUSTERS
