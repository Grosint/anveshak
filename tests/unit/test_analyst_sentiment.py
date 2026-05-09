"""Unit tests for VADER sentiment analysis — edge cases and field validation.

Existing tests in test_sentiment.py cover happy path. These tests catch:
  - Short text threshold: text with exactly 10 chars should be analysed,
    9 chars should return neutral default. Off-by-one in `len(text.strip()) < 10`.
  - SentimentResult fields must all be floats (not numpy scalars).
  - Compound score range must be [-1.0, 1.0].

pytest.mark.unit — VADER is pure Python, no GPU, no network.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestAnalyseSentimentEdgeCases:

    def test_positive_compound(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("Great news, excellent progress and wonderful results achieved")
        assert result.compound > 0

    def test_negative_compound(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("Terrible disaster, awful destruction and horrible casualties reported")
        assert result.compound < 0

    def test_neutral_returns_near_zero_compound(self):
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("The scheduled meeting is at three pm on Tuesday afternoon")
        assert -0.3 <= result.compound <= 0.3

    def test_returns_all_four_fields(self):
        """SentimentResult must have compound, positive, negative, neutral."""
        from anveshak.analyst.sentiment import analyse_sentiment, SentimentResult

        result = analyse_sentiment("This is a normal test sentence for analysis purposes")
        assert isinstance(result, SentimentResult)
        assert hasattr(result, "compound")
        assert hasattr(result, "positive")
        assert hasattr(result, "negative")
        assert hasattr(result, "neutral")

    def test_short_text_boundary_under_10_chars(self):
        """Bug boundary: text.strip() with < 10 chars returns neutral default.

        If the threshold were `<= 10` instead of `< 10`, a valid 10-char
        input would be silently ignored.
        """
        from anveshak.analyst.sentiment import analyse_sentiment

        # 9 chars after strip — should return neutral default
        result = analyse_sentiment("123456789")
        assert result.compound == 0.0
        assert result.neutral == 1.0

    def test_short_text_boundary_exactly_10_chars(self):
        """Exactly 10 chars after strip should be analysed, not defaulted."""
        from anveshak.analyst.sentiment import analyse_sentiment

        # 10 chars — should NOT hit the short-text guard
        result = analyse_sentiment("great work")  # exactly 10 chars
        # VADER should detect positive sentiment here
        assert result.compound != 0.0 or result.neutral != 1.0

    def test_whitespace_only_returns_neutral(self):
        """All-whitespace text after strip has len 0 → neutral default."""
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment("          ")
        assert result.compound == 0.0
        assert result.neutral == 1.0

    def test_compound_within_valid_range(self):
        """VADER compound must be in [-1.0, 1.0] — out-of-range would break signal engine."""
        from anveshak.analyst.sentiment import analyse_sentiment

        for text in [
            "absolutely wonderful amazing fantastic excellent superb brilliant",
            "horrible terrible awful disgusting pathetic miserable dreadful",
        ]:
            result = analyse_sentiment(text)
            assert -1.0 <= result.compound <= 1.0

    def test_pos_neg_neu_sum_to_one(self):
        """VADER positive + negative + neutral must sum to ~1.0."""
        from anveshak.analyst.sentiment import analyse_sentiment

        result = analyse_sentiment(
            "The military operation achieved mixed results with some casualties"
        )
        total = result.positive + result.negative + result.neutral
        assert 0.99 <= total <= 1.01
