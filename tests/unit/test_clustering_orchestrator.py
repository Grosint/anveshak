"""Unit tests for clustering orchestrator (Phase 2, criteria 2.1-2.10).

pytest.mark.unit -- no external dependencies, no DB, no network.
Tests pure functions: assign_to_nearest_cluster, compute_centroid,
_compute_blended_similarity. DB-dependent functions use mock pools.

Embedding realism: all test vectors are L2-normalized using seeded RNG
per learned/test-embedding-realism.md.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from anveshak.analyst.clustering import (
    ClusterCentroid,
    EmbeddingRow,
    _compute_blended_similarity,
    assign_to_nearest_cluster,
    compute_centroid,
)

# ---------------------------------------------------------------------------
# Test vector helpers -- L2-normalized, seeded RNG
# ---------------------------------------------------------------------------

_RNG = np.random.default_rng(42)


def _random_unit_vector(dim: int = 384) -> np.ndarray:
    """Generate a random L2-normalized vector."""
    v = _RNG.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def _perturb(base: np.ndarray, noise: float = 0.02) -> np.ndarray:
    """Add controlled noise and re-normalize (tight cluster = 0.02)."""
    v = base + _RNG.standard_normal(base.shape).astype(np.float32) * noise
    return (v / np.linalg.norm(v)).astype(np.float32)


def _make_row(
    cid: str,
    vector: np.ndarray,
    platform: str = "web",
    minhash: list[int] | None = None,
) -> EmbeddingRow:
    return EmbeddingRow(
        content_item_id=cid,
        vector=vector,
        source_id=platform,
        entity_minhash=minhash,
    )


def _make_centroid(
    cid: str,
    vector: np.ndarray,
    isc: int = 2,
    item_count: int = 5,
) -> ClusterCentroid:
    return ClusterCentroid(
        cluster_id=cid,
        vector=vector,
        isc=isc,
        item_count=item_count,
    )


# ---------------------------------------------------------------------------
# assign_to_nearest_cluster
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssignToNearestCluster:
    def test_above_threshold_assigned(self):
        """Item similar to centroid (>= threshold) is assigned."""
        base = _random_unit_vector()
        item = _make_row("item-1", _perturb(base, noise=0.02))
        centroid = _make_centroid("cluster-a", base)

        assigned, unassigned = assign_to_nearest_cluster(
            [item],
            [centroid],
            threshold=0.90,
        )

        assert "cluster-a" in assigned
        assert len(assigned["cluster-a"]) == 1
        assert assigned["cluster-a"][0].content_item_id == "item-1"
        assert unassigned == []

    def test_below_threshold_unassigned(self):
        """Item dissimilar to all centroids goes to unassigned."""
        item = _make_row("item-1", _random_unit_vector())
        # Orthogonal centroid -- cosine sim ~ 0
        centroid_vec = _random_unit_vector()
        # Force near-zero similarity by using a very different vector
        centroid = _make_centroid("cluster-a", centroid_vec)

        assigned, unassigned = assign_to_nearest_cluster(
            [item],
            [centroid],
            threshold=0.99,  # unreachably high
        )

        assert assigned == {}
        assert len(unassigned) == 1
        assert unassigned[0].content_item_id == "item-1"

    def test_multiple_centroids_picks_most_similar(self):
        """Item goes to the MOST similar centroid, not the first."""
        base_a = _random_unit_vector()
        base_b = _random_unit_vector()

        # Item is a slight perturbation of base_b -- much closer to B
        item = _make_row("item-1", _perturb(base_b, noise=0.01))
        centroid_a = _make_centroid("cluster-a", base_a)
        centroid_b = _make_centroid("cluster-b", base_b)

        # Put the worse match first to test it doesn't short-circuit
        assigned, unassigned = assign_to_nearest_cluster(
            [item],
            [centroid_a, centroid_b],
            threshold=0.50,
        )

        # Should be assigned to cluster-b (closer)
        assert "cluster-b" in assigned, (
            f"Expected cluster-b but got assigned to: {list(assigned.keys())}"
        )


# ---------------------------------------------------------------------------
# compute_centroid
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeCentroid:
    def test_output_is_l2_normalized(self):
        """Centroid must be a unit vector (L2 norm = 1.0)."""
        vecs = [_random_unit_vector() for _ in range(5)]
        centroid = compute_centroid(vecs)
        norm = float(np.linalg.norm(centroid))
        assert abs(norm - 1.0) < 1e-5, f"Centroid L2 norm should be 1.0, got {norm}"

    def test_single_vector_returns_itself(self):
        """Single vector centroid is that vector (normalized)."""
        v = _random_unit_vector()
        centroid = compute_centroid([v])

        # Should be essentially the same vector
        sim = float(np.dot(centroid, v))
        assert sim > 0.9999, f"Single-vector centroid should match input, cosine={sim}"


# ---------------------------------------------------------------------------
# _compute_blended_similarity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeBlendedSimilarity:
    def test_cosine_only_when_no_minhash(self):
        """All entity_minhash=None -- falls back to pure cosine similarity."""
        base = _random_unit_vector()
        rows = [
            _make_row("a", _perturb(base, 0.02), minhash=None),
            _make_row("b", _perturb(base, 0.02), minhash=None),
            _make_row("c", _perturb(base, 0.02), minhash=None),
        ]

        sim_matrix = _compute_blended_similarity(rows)

        # Verify shape
        assert sim_matrix.shape == (3, 3)
        # Diagonal should be ~1.0 (self-similarity)
        for i in range(3):
            assert sim_matrix[i, i] > 0.99, (
                f"Self-similarity should be ~1.0, got {sim_matrix[i, i]}"
            )
        # Off-diagonal should be high (tight cluster from same base)
        assert sim_matrix[0, 1] > 0.80, "Tight cluster items should have high cosine"

    def test_blend_with_minhash(self):
        """Items with minhash get blended similarity, not pure cosine."""
        base = _random_unit_vector()
        # Two items with identical minhash (jaccard=1.0) and similar embeddings
        shared_minhash = list(range(128))
        rows = [
            _make_row("a", _perturb(base, 0.02), minhash=shared_minhash),
            _make_row("b", _perturb(base, 0.02), minhash=shared_minhash),
        ]

        with patch("anveshak.analyst.clustering.settings") as mock_settings:
            mock_settings.entity_blend_weight = 0.3
            sim_matrix = _compute_blended_similarity(rows)

        # With identical minhash (jaccard=1.0) and high cosine,
        # blended should be >= pure cosine
        assert sim_matrix[0, 1] > 0.90

    def test_partial_minhash_falls_back_to_cosine(self):
        """Only 1 item has minhash (<2 total) -- falls back to cosine-only."""
        base = _random_unit_vector()
        rows = [
            _make_row("a", _perturb(base, 0.02), minhash=[1, 2, 3]),
            _make_row("b", _perturb(base, 0.02), minhash=None),
            _make_row("c", _perturb(base, 0.02), minhash=None),
        ]

        with patch("anveshak.analyst.clustering.settings") as mock_settings:
            mock_settings.entity_blend_weight = 0.3

            blended = _compute_blended_similarity(rows)

        # With only 1 minhash, code falls back to cosine-only
        # Compute pure cosine for comparison
        matrix = np.vstack([r.vector for r in rows]).astype(np.float64)
        cosine = matrix @ matrix.T
        np.clip(cosine, -1.0, 1.0, out=cosine)

        np.testing.assert_allclose(
            blended,
            cosine,
            atol=1e-10,
            err_msg="With <2 minhashes, blended should equal pure cosine",
        )


# ---------------------------------------------------------------------------
# run_clustering -- orchestrator integration (mocked DB)
# ---------------------------------------------------------------------------

_CLUST_MOD = "anveshak.analyst.clustering"


@pytest.mark.unit
class TestRunClustering:
    @pytest.mark.asyncio
    async def test_empty_items_returns_empty(self):
        """No unclustered items -- returns empty list immediately."""
        pool = AsyncMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_CLUST_MOD}.load_unclustered_embeddings", return_value=[]),
            patch(f"{_CLUST_MOD}.load_cluster_centroids") as mock_centroids,
        ):
            from anveshak.analyst.clustering import run_clustering

            result = await run_clustering("topic-1", pool)

        assert result == []
        # Should not even check centroids when there are no items
        mock_centroids.assert_not_called()

    @pytest.mark.asyncio
    async def test_incremental_vs_fresh_path(self):
        """With existing centroids: items go through incremental assignment.
        Without: they go through full Leiden.
        """
        base = _random_unit_vector()
        new_items = [
            _make_row("item-1", _perturb(base, 0.02)),
            _make_row("item-2", _perturb(base, 0.02)),
        ]
        existing_centroids = [
            _make_centroid("cluster-existing", base),
        ]

        pool = AsyncMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_CLUST_MOD}.load_unclustered_embeddings", return_value=new_items),
            patch(f"{_CLUST_MOD}.load_cluster_centroids", return_value=existing_centroids),
            patch(f"{_CLUST_MOD}.assign_to_nearest_cluster") as mock_assign,
            patch(f"{_CLUST_MOD}.update_cluster_with_assignments", return_value=3) as mock_update,
            patch(f"{_CLUST_MOD}._leiden_and_persist", return_value=[]) as mock_leiden,
        ):
            # Mock assign to put all items into existing cluster
            mock_assign.return_value = ({"cluster-existing": new_items}, [])

            from anveshak.analyst.clustering import run_clustering

            result = await run_clustering("topic-1", pool)

        # Incremental path taken
        mock_assign.assert_called_once()
        mock_update.assert_called_once()
        # No unassigned items, so Leiden should NOT be called
        mock_leiden.assert_not_called()
        assert "cluster-existing" in result

    @pytest.mark.asyncio
    async def test_fresh_topic_uses_leiden(self):
        """No existing centroids -- full Leiden path."""
        new_items = [
            _make_row("item-1", _random_unit_vector()),
            _make_row("item-2", _random_unit_vector()),
        ]

        pool = AsyncMock()
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        acq = AsyncMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        with (
            patch(f"{_CLUST_MOD}.load_unclustered_embeddings", return_value=new_items),
            patch(f"{_CLUST_MOD}.load_cluster_centroids", return_value=[]),  # no existing
            patch(f"{_CLUST_MOD}.assign_to_nearest_cluster") as mock_assign,
            patch(
                f"{_CLUST_MOD}._leiden_and_persist", return_value=["new-cluster-1"]
            ) as mock_leiden,
        ):
            from anveshak.analyst.clustering import run_clustering

            result = await run_clustering("topic-1", pool)

        # Fresh path: Leiden called, incremental assignment NOT called
        mock_assign.assert_not_called()
        mock_leiden.assert_called_once()
        assert result == ["new-cluster-1"]
