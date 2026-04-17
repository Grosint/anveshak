"""Unit tests for VADER sentiment analysis.

Tests:
  - Positive text → positive compound score
  - Negative text → negative compound score
  - Neutral text → near-zero compound
  - Short/empty text → neutral default
  - Returns SentimentResult dataclass
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestAnalyseSentiment:

    def test_positive_text(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment(
            "The joint naval exercise was a great success, strengthening bilateral ties."
        )
        assert result.compound > 0.3
        assert result.positive > 0.0

    def test_negative_text(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment(
            "The attack caused devastating casualties and widespread destruction."
        )
        assert result.compound < -0.3
        assert result.negative > 0.0

    def test_neutral_text(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment(
            "The meeting was held at the designated location on Tuesday afternoon."
        )
        assert -0.3 <= result.compound <= 0.3
        assert result.neutral > 0.5

    def test_empty_text_returns_neutral(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("")
        assert result.compound == 0.0
        assert result.neutral == 1.0

    def test_short_text_returns_neutral(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("Hi")
        assert result.compound == 0.0

    def test_returns_sentiment_result_type(self):
        from anveshak.analyst.sentiment import analyse_sentiment, SentimentResult

        result = analyse_sentiment("This is a normal sentence for testing purposes.")
        assert isinstance(result, SentimentResult)
        assert isinstance(result.compound, float)
        assert isinstance(result.positive, float)

    def test_scores_sum_to_approximately_one(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment(
            "The intelligence report highlighted both threats and opportunities."
        )
        total = result.positive + result.negative + result.neutral
        assert 0.99 <= total <= 1.01
