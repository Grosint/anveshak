"""Unit tests for topic relevance scoring (Phase: Topic Relevance Gate).

pytest.mark.unit — pure functions, no DB, no GPU, no Ollama.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest


class TestComputeTopicRelevance:
    """compute_topic_relevance: cosine similarity via dot product."""

    def test_identical_vectors_score_one(self):
        from anveshak.analyst.relevance import compute_topic_relevance

        vec = [0.0] * 384
        vec[0] = 1.0  # unit vector along axis 0
        score = compute_topic_relevance(vec, vec)
        assert score == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vectors_score_zero(self):
        from anveshak.analyst.relevance import compute_topic_relevance

        a = [0.0] * 384
        a[0] = 1.0
        b = [0.0] * 384
        b[1] = 1.0
        score = compute_topic_relevance(a, b)
        assert score == pytest.approx(0.0, abs=1e-5)

    def test_opposite_vectors_score_negative(self):
        from anveshak.analyst.relevance import compute_topic_relevance

        a = [0.0] * 384
        a[0] = 1.0
        b = [0.0] * 384
        b[0] = -1.0
        score = compute_topic_relevance(a, b)
        assert score == pytest.approx(-1.0, abs=1e-5)

    def test_returns_float(self):
        from anveshak.analyst.relevance import compute_topic_relevance

        a = np.random.randn(384).tolist()
        b = np.random.randn(384).tolist()
        score = compute_topic_relevance(a, b)
        assert isinstance(score, float)


class TestResolveThreshold:
    """resolve_threshold: per-topic override vs global fallback."""

    def test_uses_per_topic_when_set(self):
        from anveshak.analyst.relevance import resolve_threshold

        assert resolve_threshold(0.50) == 0.50

    def test_falls_back_to_global_when_none(self):
        from anveshak.analyst.relevance import resolve_threshold

        # Global default is 0.35 (from settings, calibrated from real data)
        result = resolve_threshold(None)
        assert result == pytest.approx(0.35)

    def test_per_topic_zero_is_valid(self):
        """A per-topic threshold of 0.0 should be honoured (disable filtering)."""
        from anveshak.analyst.relevance import resolve_threshold

        assert resolve_threshold(0.0) == 0.0


class TestBuildTopicQueryText:
    """build_topic_query_text: joins name + keywords."""

    def test_joins_name_and_keywords(self):
        from anveshak.analyst.relevance import build_topic_query_text

        result = build_topic_query_text("China PLA", ["border", "military"])
        assert result == "China PLA border military"

    def test_empty_keywords(self):
        from anveshak.analyst.relevance import build_topic_query_text

        result = build_topic_query_text("China PLA", [])
        assert result == "China PLA"

    def test_single_keyword(self):
        from anveshak.analyst.relevance import build_topic_query_text

        result = build_topic_query_text("Topic", ["keyword"])
        assert result == "Topic keyword"


class TestBuildTopicQueryEmbedding:
    """build_topic_query_embedding: calls encode_text with joined text."""

    @patch("anveshak.analyst.relevance.encode_text")
    def test_calls_encode_text_with_joined_text(self, mock_encode):
        from anveshak.analyst.relevance import build_topic_query_embedding

        mock_encode.return_value = [0.1] * 384
        result = build_topic_query_embedding("China PLA", ["border", "military"])

        mock_encode.assert_called_once_with("China PLA border military")
        assert result == [0.1] * 384
