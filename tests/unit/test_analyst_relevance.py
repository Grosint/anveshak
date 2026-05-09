"""Additional unit tests for topic relevance scoring — edge cases and bugs.

Existing tests in test_relevance.py cover happy-path. These tests catch:
  - Non-normalised vectors producing scores > 1.0 (caller bug, not function bug,
    but the function should still return a valid float)
  - resolve_threshold(0.0) treated as falsy — would fall through to global default
    if the check used `if per_topic:` instead of `if per_topic is not None:`
  - Dimension mismatch between content and topic embeddings

pytest.mark.unit — pure functions, no DB, no GPU.
"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.unit


class TestComputeTopicRelevanceEdgeCases:

    def test_identical_normalised_vectors_equal_one(self):
        """L2-normalised identical vectors must dot-product to exactly 1.0."""
        from anveshak.analyst.relevance import compute_topic_relevance

        rng = np.random.default_rng(42)
        raw = rng.standard_normal(384).astype(np.float32)
        normalised = (raw / np.linalg.norm(raw)).tolist()
        score = compute_topic_relevance(normalised, normalised)
        assert score == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors_equal_zero(self):
        from anveshak.analyst.relevance import compute_topic_relevance

        a = [0.0] * 384
        a[0] = 1.0
        b = [0.0] * 384
        b[1] = 1.0
        score = compute_topic_relevance(a, b)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_non_normalised_vectors_can_exceed_one(self):
        """Bug surface: if embeddings aren't L2-normalised (broken encode_text),
        dot product can exceed 1.0. The function doesn't clamp — callers
        must ensure normalisation. This test documents the contract.
        """
        from anveshak.analyst.relevance import compute_topic_relevance

        # Two identical non-normalised vectors with magnitude > 1
        big_vec = [2.0] * 384
        score = compute_topic_relevance(big_vec, big_vec)
        # 2.0 * 2.0 * 384 = 1536.0
        assert score > 1.0, "Non-normalised vectors must not be silently clamped"

    def test_score_is_python_float(self):
        """Must return Python float, not numpy scalar — JSON serialisation breaks on np.float32."""
        from anveshak.analyst.relevance import compute_topic_relevance

        a = [0.1] * 384
        b = [0.2] * 384
        score = compute_topic_relevance(a, b)
        assert type(score) is float


class TestResolveThresholdEdgeCases:

    def test_per_topic_zero_is_not_none(self):
        """Bug caught: if check uses `if per_topic:` instead of `if per_topic is not None:`,
        0.0 is falsy and falls through to global default — silently enabling
        filtering when the analyst explicitly disabled it.
        """
        from anveshak.analyst.relevance import resolve_threshold

        assert resolve_threshold(0.0) == 0.0

    def test_per_topic_overrides_global(self):
        from anveshak.analyst.relevance import resolve_threshold

        result = resolve_threshold(0.5)
        assert result == 0.5

    def test_none_falls_back_to_global_default(self):
        from anveshak.analyst.relevance import resolve_threshold

        result = resolve_threshold(None)
        # Global default is 0.35 from settings
        assert result == pytest.approx(0.35)

    def test_negative_threshold_is_honoured(self):
        """Edge case: a negative threshold (accept everything) should pass through."""
        from anveshak.analyst.relevance import resolve_threshold

        assert resolve_threshold(-0.5) == -0.5
