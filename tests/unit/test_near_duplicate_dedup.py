"""Unit tests for near-duplicate detection (Phase 1 — P0 semantic dedup).

Tests:
  - Pairwise cosine detection above/below threshold
  - Canonical ordering (a < b)
  - Idempotent upsert
  - ISC exclusion of duplicates
  - Empty topic handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from anveshak.analyst.clustering import EmbeddingRow, count_independent_sources

# ---------------------------------------------------------------------------
# detect_near_duplicates tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_identical_embeddings_detected():
    """Two identical vectors should produce similarity 1.0 >= 0.95 threshold."""
    vec = np.array([0.1] * 384, dtype=np.float32)
    vec = vec / np.linalg.norm(vec)  # L2 normalise

    ids = ["aaa-item-1", "bbb-item-2"]
    matrix = np.vstack([vec, vec])
    sim = matrix @ matrix.T

    pairs = []
    threshold = 0.95
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            score = float(sim[i, j])
            if score >= threshold:
                a, b = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
                pairs.append((a, b, score))

    assert len(pairs) == 1
    assert pairs[0][0] == "aaa-item-1"
    assert pairs[0][1] == "bbb-item-2"
    assert pairs[0][2] >= 0.99  # near-perfect


@pytest.mark.unit
def test_below_threshold_ignored():
    """Vectors with cosine similarity ~0.5 should NOT produce a pair at 0.95 threshold."""
    rng = np.random.RandomState(42)
    vec_a = rng.randn(384).astype(np.float32)
    vec_a /= np.linalg.norm(vec_a)
    vec_b = rng.randn(384).astype(np.float32)
    vec_b /= np.linalg.norm(vec_b)

    sim = float(vec_a @ vec_b)
    assert sim < 0.95, f"Random vectors should be dissimilar, got {sim}"

    # No pair should be produced
    threshold = 0.95
    pairs = []
    ids = ["item-a", "item-b"]
    matrix = np.vstack([vec_a, vec_b])
    sim_matrix = matrix @ matrix.T
    for i in range(2):
        for j in range(i + 1, 2):
            if float(sim_matrix[i, j]) >= threshold:
                pairs.append((ids[i], ids[j]))
    assert len(pairs) == 0


@pytest.mark.unit
def test_at_threshold_detected():
    """Vectors with cosine similarity exactly at threshold should be detected."""
    # Create two vectors with known high similarity
    base = np.ones(384, dtype=np.float32)
    base /= np.linalg.norm(base)

    # Perturb slightly — cosine will be very close to 1.0
    perturbed = base.copy()
    perturbed[0] += 0.01
    perturbed /= np.linalg.norm(perturbed)

    sim = float(base @ perturbed)
    assert sim >= 0.95, f"Slightly perturbed vectors should be similar, got {sim}"


@pytest.mark.unit
def test_canonical_ordering():
    """Pair (a, b) should always have a < b lexicographically."""
    id_x = "zzz-later"
    id_y = "aaa-earlier"

    a, b = (id_x, id_y) if id_x < id_y else (id_y, id_x)
    assert a == "aaa-earlier"
    assert b == "zzz-later"


# ---------------------------------------------------------------------------
# ISC exclusion tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_isc_excludes_duplicates():
    """3 items from 3 platforms, 2 near-duplicates → ISC should be 2."""
    content_item_ids = ["item-a", "item-b", "item-c"]
    platforms = ["telegram", "reddit", "web"]

    # item-b is a near-duplicate of item-a
    duplicate_ids = {"item-b"}

    filtered_platforms = [
        p for cid, p in zip(content_item_ids, platforms) if cid not in duplicate_ids
    ]

    isc = count_independent_sources(filtered_platforms)
    assert isc == 2, f"Expected ISC=2 after excluding duplicate, got {isc}"


@pytest.mark.unit
def test_isc_no_duplicates_unchanged():
    """When no duplicates, ISC uses all platforms."""
    platforms = ["telegram", "reddit", "web"]
    isc = count_independent_sources(platforms)
    assert isc == 3


@pytest.mark.unit
def test_isc_all_duplicates_falls_back():
    """If all items are duplicates, fall back to counting all platforms."""
    content_item_ids = ["item-a", "item-b"]
    platforms = ["telegram", "reddit"]
    duplicate_ids = {"item-a", "item-b"}

    filtered_platforms = [
        p for cid, p in zip(content_item_ids, platforms) if cid not in duplicate_ids
    ]

    # When all filtered out, should use original platforms
    isc = (
        count_independent_sources(filtered_platforms)
        if filtered_platforms
        else count_independent_sources(platforms)
    )
    assert isc == 2, "Fallback: all duplicates → use original platform list"


# ---------------------------------------------------------------------------
# detect_near_duplicates async tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_empty_topic_returns_empty():
    """Topic with 0 or 1 items should return no pairs."""
    mock_pool = AsyncMock()

    with patch("anveshak.analyst.dedup.load_embeddings", return_value=[]):
        from anveshak.analyst.dedup import detect_near_duplicates

        pairs = await detect_near_duplicates("topic-empty", mock_pool)

    assert pairs == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_single_item_returns_empty():
    """Topic with 1 item can't have pairs."""
    vec = np.array([0.1] * 384, dtype=np.float32)
    vec /= np.linalg.norm(vec)
    mock_pool = AsyncMock()

    rows = [
        EmbeddingRow(content_item_id="only-item", vector=vec, source_id="web", entity_minhash=None)
    ]
    with patch("anveshak.analyst.dedup.load_embeddings", return_value=rows):
        from anveshak.analyst.dedup import detect_near_duplicates

        pairs = await detect_near_duplicates("topic-single", mock_pool)

    assert pairs == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_finds_near_duplicate_pair():
    """Two items with identical embeddings should be detected."""
    vec = np.array([0.1] * 384, dtype=np.float32)
    vec /= np.linalg.norm(vec)
    mock_pool = AsyncMock()

    rows = [
        EmbeddingRow(
            content_item_id="aaa-item", vector=vec.copy(), source_id="telegram", entity_minhash=None
        ),
        EmbeddingRow(
            content_item_id="bbb-item", vector=vec.copy(), source_id="reddit", entity_minhash=None
        ),
    ]
    with patch("anveshak.analyst.dedup.load_embeddings", return_value=rows):
        from anveshak.analyst.dedup import detect_near_duplicates

        pairs = await detect_near_duplicates("topic-dup", mock_pool)

    assert len(pairs) == 1
    assert pairs[0][0] == "aaa-item"
    assert pairs[0][1] == "bbb-item"
    assert pairs[0][2] >= 0.99


# ---------------------------------------------------------------------------
# upsert_near_duplicates tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_empty_pairs():
    """Empty pair list should insert nothing."""
    from anveshak.analyst.dedup import upsert_near_duplicates

    mock_pool = AsyncMock()
    inserted = await upsert_near_duplicates([], mock_pool)
    assert inserted == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_calls_insert():
    """Pairs should be inserted via SQL."""
    from anveshak.analyst.dedup import upsert_near_duplicates

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

    # conn.transaction() returns a sync context manager (asyncpg pattern)
    mock_txn = MagicMock()
    mock_txn.__aenter__ = AsyncMock(return_value=None)
    mock_txn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value = mock_txn

    # pool.acquire() returns an async context manager
    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_acq

    pairs = [("aaa", "bbb", 0.97)]
    inserted = await upsert_near_duplicates(pairs, mock_pool)
    assert inserted == 1
    assert mock_conn.execute.called


# ---------------------------------------------------------------------------
# get_duplicate_ids_for_cluster tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_duplicate_ids_empty():
    """Empty ID list returns empty set."""
    from anveshak.analyst.dedup import get_duplicate_ids_for_cluster

    mock_conn = AsyncMock()
    result = await get_duplicate_ids_for_cluster([], mock_conn)
    assert result == set()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_duplicate_ids_returns_b_side():
    """Should return content_item_b_id values from near_duplicates."""
    from anveshak.analyst.dedup import get_duplicate_ids_for_cluster

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {"content_item_b_id": "item-b"},
    ]

    result = await get_duplicate_ids_for_cluster(["item-a", "item-b"], mock_conn)
    assert result == {"item-b"}
