"""Unit tests for label staleness detection (Phase 5 — P3).

Tests:
  - compute_item_hash determinism
  - Staleness detection with NULL hash, changed hash, same hash
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anveshak.analyst.labeller import compute_item_hash, check_label_staleness


# ---------------------------------------------------------------------------
# compute_item_hash tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_compute_item_hash_deterministic():
    """Same IDs in different order should produce the same hash."""
    ids_a = ["item-3", "item-1", "item-2"]
    ids_b = ["item-1", "item-2", "item-3"]
    assert compute_item_hash(ids_a) == compute_item_hash(ids_b)


@pytest.mark.unit
def test_compute_item_hash_differs_on_content_change():
    """Different ID sets produce different hashes."""
    hash_a = compute_item_hash(["item-1", "item-2", "item-3"])
    hash_b = compute_item_hash(["item-1", "item-2", "item-4"])
    assert hash_a != hash_b


@pytest.mark.unit
def test_compute_item_hash_is_64_hex():
    """SHA-256 produces 64-character hex string."""
    h = compute_item_hash(["item-1"])
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# check_label_staleness tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_null_hash_always_stale():
    """Cluster with label_item_hash=NULL should be considered stale."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"label_item_hash": None}

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    result = await check_label_staleness("cluster-1", mock_pool)
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_identical_composition_not_stale():
    """Same item hash → not stale, skip relabelling."""
    item_ids = ["item-1", "item-2", "item-3"]
    stored_hash = compute_item_hash(item_ids)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"label_item_hash": stored_hash}
    mock_conn.fetch.return_value = [{"id": i} for i in item_ids]

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    result = await check_label_staleness("cluster-1", mock_pool)
    assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stale_when_items_changed():
    """Different item hash → stale, needs relabelling."""
    old_ids = ["item-1", "item-2", "item-3"]
    new_ids = ["item-1", "item-4", "item-5"]  # 2 of 3 changed
    stored_hash = compute_item_hash(old_ids)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"label_item_hash": stored_hash}
    mock_conn.fetch.return_value = [{"id": i} for i in new_ids]

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    result = await check_label_staleness("cluster-1", mock_pool)
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_cluster_is_stale():
    """Cluster not found in DB should be considered stale (trigger labelling)."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    result = await check_label_staleness("nonexistent", mock_pool)
    assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_cluster_not_stale():
    """Cluster with no items should not trigger relabelling."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"label_item_hash": "somehash"}
    mock_conn.fetch.return_value = []  # no items

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    result = await check_label_staleness("empty-cluster", mock_pool)
    assert result is False
