"""Unit tests for count_independent_sources (Phase 2, criteria 2.32).

pytest.mark.unit — pure function, no DB, no network.
count_independent_sources counts distinct platform strings — this is the
core correctness guarantee for signal_threshold logic.
"""
import pytest

from anveshak.analyst.clustering import count_independent_sources


class TestCountIndependentSources:
    """Criteria 2.5, 2.32: distinct platform count is accurate."""

    def test_single_platform(self):
        platforms = ["web", "web", "web"]
        assert count_independent_sources(platforms) == 1

    def test_two_distinct_platforms(self):
        platforms = ["telegram", "reddit", "telegram", "reddit"]
        assert count_independent_sources(platforms) == 2

    def test_three_distinct_platforms(self):
        platforms = ["telegram", "reddit", "bluesky"]
        assert count_independent_sources(platforms) == 3

    def test_all_platforms_distinct(self):
        platforms = ["telegram", "reddit", "bluesky", "web", "twitter"]
        assert count_independent_sources(platforms) == 5

    def test_empty_list(self):
        assert count_independent_sources([]) == 0

    def test_single_item(self):
        assert count_independent_sources(["telegram"]) == 1

    def test_case_sensitive(self):
        """Platforms are case-sensitive — 'Telegram' != 'telegram'."""
        platforms = ["Telegram", "telegram"]
        assert count_independent_sources(platforms) == 2

    def test_counts_platforms_not_items(self):
        """100 items from 2 platforms → count is 2, not 100."""
        platforms = ["telegram"] * 50 + ["reddit"] * 50
        assert count_independent_sources(platforms) == 2

    def test_telegram_reddit_bluesky_web_triggers_threshold_3(self):
        """Real scenario: 3+ platforms → should satisfy default signal_threshold=3."""
        platforms = ["telegram", "reddit", "bluesky", "reddit", "telegram"]
        isc = count_independent_sources(platforms)
        assert isc >= 3  # default threshold


class TestComputeCentroid:
    """Unit tests for compute_centroid — ensures normalisation and shape correctness."""

    def test_centroid_is_unit_norm(self):
        import numpy as np
        from anveshak.analyst.clustering import compute_centroid

        vecs = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
        ]
        centroid = compute_centroid(vecs)
        norm = float(np.linalg.norm(centroid))
        assert abs(norm - 1.0) < 1e-5, f"Centroid should be unit-norm, got {norm}"

    def test_centroid_shape_matches_input(self):
        import numpy as np
        from anveshak.analyst.clustering import compute_centroid

        dim = 384
        vecs = [np.random.rand(dim).astype(np.float32) for _ in range(5)]
        centroid = compute_centroid(vecs)
        assert centroid.shape == (dim,)

    def test_single_vector_centroid_equals_itself_normalised(self):
        import numpy as np
        from anveshak.analyst.clustering import compute_centroid

        vec = np.array([3.0, 4.0], dtype=np.float32)
        centroid = compute_centroid([vec])
        expected = vec / np.linalg.norm(vec)
        np.testing.assert_allclose(centroid, expected, atol=1e-5)
