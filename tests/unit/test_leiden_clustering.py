"""Unit tests for Leiden-based narrative clustering.

Tests verify the find_narrative_clusters() function directly with
synthetic EmbeddingRow data — no database required.

Scenarios:
  1. Single narrative, small batch (6 items) — the HDBSCAN failure case
  3. Bridge article with entity overlap (16 items)
  4. Chaining risk — Leiden breaks weak chains (5 items)
  6. Sparse topic (3 items)
  7. All articles different — no clusters form (20 items)
"""
from __future__ import annotations

import numpy as np
import pytest

from anveshak.analyst.clustering import (
    EmbeddingRow,
    find_narrative_clusters,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def _make_narrative_base(seed: int, dim: int = 384) -> np.ndarray:
    """Deterministic diverse base vector for a narrative."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float64)
    return vec / np.linalg.norm(vec)


def _make_article(
    base: np.ndarray, rng: np.random.RandomState, noise: float = 0.03,
) -> np.ndarray:
    """Perturb base to simulate an article embedding (cosine sim ~0.85-0.95)."""
    perturbed = base + rng.uniform(-noise, noise, size=len(base))
    return (perturbed / np.linalg.norm(perturbed)).astype(np.float32)


def _make_minhash(
    base_hashes: list[int],
    rng: np.random.RandomState,
    overlap: float = 0.7,
    num_perm: int = 128,
) -> list[int]:
    """Simulate entity minhash with controlled overlap to base."""
    result = list(base_hashes)
    n_change = int(num_perm * (1.0 - overlap))
    indices = rng.choice(num_perm, size=n_change, replace=False)
    for idx in indices:
        result[idx] = int(rng.randint(0, 2**31))
    return result


def _make_rows(
    base: np.ndarray,
    count: int,
    platform: str,
    rng: np.random.RandomState,
    base_hashes: list[int] | None = None,
    entity_overlap: float = 0.7,
) -> list[EmbeddingRow]:
    """Generate EmbeddingRows for one narrative on one platform."""
    rows = []
    for i in range(count):
        vec = _make_article(base, rng)
        minhash = _make_minhash(base_hashes, rng, entity_overlap) if base_hashes else None
        rows.append(EmbeddingRow(
            content_item_id=f"{platform}-{rng.randint(0, 2**31)}",
            vector=vec,
            platform=platform,
            entity_minhash=minhash,
        ))
    return rows


# ---------------------------------------------------------------------------
# Scenario 1: Single narrative, small batch (6 articles, 3 platforms)
# ---------------------------------------------------------------------------


class TestSingleNarrativeSmallBatch:
    """The exact case that broke HDBSCAN — 6 items, 1 narrative, 3 platforms."""

    def test_all_items_cluster_together(self):
        rng = np.random.RandomState(42)
        base = _make_narrative_base(seed=101)

        rows: list[EmbeddingRow] = []
        for platform in ["telegram", "reddit", "web"]:
            rows.extend(_make_rows(base, 2, platform, rng))

        assert len(rows) == 6
        groups, _edge_count = find_narrative_clusters(rows)

        assert len(groups) == 1, f"Expected 1 cluster, got {len(groups)}"
        cluster_indices = list(groups.values())[0]
        assert len(cluster_indices) == 6, f"Expected all 6 items in cluster, got {len(cluster_indices)}"

    def test_platforms_are_diverse(self):
        rng = np.random.RandomState(42)
        base = _make_narrative_base(seed=101)

        rows: list[EmbeddingRow] = []
        for platform in ["telegram", "reddit", "web"]:
            rows.extend(_make_rows(base, 2, platform, rng))

        groups, _edge_count = find_narrative_clusters(rows)
        cluster_indices = list(groups.values())[0]
        platforms = {rows[i].platform for i in cluster_indices}
        assert platforms == {"telegram", "reddit", "web"}


# ---------------------------------------------------------------------------
# Scenario 3: Bridge article with entity overlap
# ---------------------------------------------------------------------------


class TestBridgeArticleEntityOverlap:
    """16 items: 7 narrative A + 7 narrative B + 1 bridge + 1 unrelated."""

    def _build_data(self):
        rng = np.random.RandomState(99)
        base_a = _make_narrative_base(seed=2001)
        base_b = _make_narrative_base(seed=2002)
        base_unrelated = _make_narrative_base(seed=2099)

        hashes_a = [int(rng.randint(0, 2**31)) for _ in range(128)]
        hashes_b = [int(rng.randint(0, 2**31)) for _ in range(128)]

        rows: list[EmbeddingRow] = []
        # 7 items narrative A (across platforms) — low noise for tight clusters
        for platform in ["telegram", "reddit", "web"]:
            rows.extend(_make_rows(base_a, 2, platform, rng, hashes_a, entity_overlap=0.7))
        rows.extend(_make_rows(base_a, 1, "bluesky", rng, hashes_a, entity_overlap=0.7))

        # 7 items narrative B
        for platform in ["telegram", "reddit", "web"]:
            rows.extend(_make_rows(base_b, 2, platform, rng, hashes_b, entity_overlap=0.7))
        rows.extend(_make_rows(base_b, 1, "bluesky", rng, hashes_b, entity_overlap=0.7))

        # Bridge article: slightly closer to A than B so it has a clear primary
        bridge_vec = 0.55 * base_a + 0.45 * base_b
        bridge_vec = (bridge_vec / np.linalg.norm(bridge_vec)).astype(np.float32)
        # 50% overlap with each narrative's entities
        bridge_hash = list(hashes_a[:64]) + list(hashes_b[64:])
        rows.append(EmbeddingRow(
            content_item_id="bridge-article",
            vector=bridge_vec,
            platform="web",
            entity_minhash=bridge_hash,
        ))

        # Unrelated article
        unrelated_vec = _make_article(base_unrelated, rng)
        rows.append(EmbeddingRow(
            content_item_id="unrelated",
            vector=unrelated_vec,
            platform="web",
            entity_minhash=None,
        ))

        return rows

    def test_two_narratives_stay_separate(self):
        rows = self._build_data()
        groups, _edge_count = find_narrative_clusters(rows)

        # Should have 2 main clusters (narratives A and B)
        # Bridge joins one, unrelated is singleton (discarded)
        assert len(groups) >= 2, f"Expected at least 2 clusters, got {len(groups)}"

    def test_bridge_does_not_merge_narratives(self):
        rows = self._build_data()
        groups, _edge_count = find_narrative_clusters(rows)

        # No single cluster should contain items from both narratives
        # Narrative A items are indices 0-6, narrative B items are 7-13
        narrative_a_ids = {rows[i].content_item_id for i in range(7)}
        narrative_b_ids = {rows[i].content_item_id for i in range(7, 14)}

        for label, indices in groups.items():
            cluster_ids = {rows[i].content_item_id for i in indices}
            a_count = len(cluster_ids & narrative_a_ids)
            b_count = len(cluster_ids & narrative_b_ids)
            # A cluster shouldn't have significant items from both narratives
            assert not (a_count >= 3 and b_count >= 3), (
                f"Cluster {label} merged narratives: {a_count} from A, {b_count} from B"
            )


# ---------------------------------------------------------------------------
# Scenario 4: Chaining risk
# ---------------------------------------------------------------------------


class TestChainingRisk:
    """5 articles forming a similarity chain: A1-A2-A3-A4-A5.

    A1~A2 and A2~A3 are above threshold, but A1~A3 is below.
    Connected components would chain them all. Leiden should break the chain.
    """

    def test_leiden_breaks_chain(self):
        """Build a chain: A1-A2-A3-A4-A5 where adjacent pairs are above
        threshold but endpoints (A1, A5) are dissimilar.

        We add support items around each endpoint to give Leiden enough
        structure to identify separate communities.
        """
        rng = np.random.RandomState(42)
        base_1 = _make_narrative_base(seed=3001)
        base_5 = _make_narrative_base(seed=3003)

        # A3 is midpoint — bridges both sides
        a3_vec = 0.5 * base_1 + 0.5 * base_5
        a3_vec = (a3_vec / np.linalg.norm(a3_vec)).astype(np.float64)

        # A2 bridges base_1 and A3
        a2_vec = 0.85 * base_1 + 0.15 * a3_vec
        a2_vec = (a2_vec / np.linalg.norm(a2_vec)).astype(np.float32)

        # A4 bridges A3 and base_5
        a4_vec = 0.15 * a3_vec + 0.85 * base_5
        a4_vec = (a4_vec / np.linalg.norm(a4_vec)).astype(np.float32)

        # Add support items to form proper communities around endpoints
        rows = [
            EmbeddingRow("A1", base_1.astype(np.float32), "web", None),
            EmbeddingRow("A1b", _make_article(base_1, rng, noise=0.02), "telegram", None),
            EmbeddingRow("A1c", _make_article(base_1, rng, noise=0.02), "reddit", None),
            EmbeddingRow("A2", a2_vec, "web", None),
            EmbeddingRow("A3", a3_vec.astype(np.float32), "web", None),
            EmbeddingRow("A4", a4_vec, "web", None),
            EmbeddingRow("A5", base_5.astype(np.float32), "web", None),
            EmbeddingRow("A5b", _make_article(base_5, rng, noise=0.02), "telegram", None),
            EmbeddingRow("A5c", _make_article(base_5, rng, noise=0.02), "reddit", None),
        ]

        # Verify endpoints are dissimilar
        sim_1_5 = float(np.dot(base_1, base_5))
        assert sim_1_5 < 0.3, f"A1~A5 should be low, got {sim_1_5:.3f}"

        groups, _edge_count = find_narrative_clusters(rows)

        # A1 and A5 should NOT be in the same cluster
        if groups:
            for label, indices in groups.items():
                ids_in_cluster = {rows[i].content_item_id for i in indices}
                assert not ({"A1", "A5"} <= ids_in_cluster), (
                    f"Leiden failed: A1 and A5 in same cluster {ids_in_cluster}"
                )


# ---------------------------------------------------------------------------
# Scenario 6: Sparse topic (3 articles)
# ---------------------------------------------------------------------------


class TestSparseTopic:
    """3 similar articles from 2 platforms — should form 1 small cluster."""

    def test_small_cluster_forms(self):
        rng = np.random.RandomState(42)
        base = _make_narrative_base(seed=601)

        rows = (
            _make_rows(base, 2, "telegram", rng)
            + _make_rows(base, 1, "web", rng)
        )

        groups, _edge_count = find_narrative_clusters(rows)
        assert len(groups) == 1, f"Expected 1 cluster from 3 similar items, got {len(groups)}"
        assert len(list(groups.values())[0]) == 3


# ---------------------------------------------------------------------------
# Scenario 7: All articles different — no clusters
# ---------------------------------------------------------------------------


class TestAllDifferentNoClusters:
    """20 unrelated articles with unique base vectors — 0 clusters expected."""

    def test_no_clusters_formed(self):
        rows: list[EmbeddingRow] = []
        for i in range(20):
            base = _make_narrative_base(seed=7000 + i)
            rows.append(EmbeddingRow(
                content_item_id=f"unrelated-{i}",
                vector=base.astype(np.float32),
                platform="web",
                entity_minhash=None,
            ))

        # Verify pairwise similarities are low
        vecs = np.vstack([r.vector for r in rows]).astype(np.float64)
        sim = vecs @ vecs.T
        np.fill_diagonal(sim, 0)
        assert sim.max() < 0.5, f"Max pairwise sim too high: {sim.max():.3f}"

        groups, _edge_count = find_narrative_clusters(rows)
        assert len(groups) == 0, f"Expected 0 clusters, got {len(groups)}"
