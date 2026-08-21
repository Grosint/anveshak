"""Sentiment analysis using VADER (Valence Aware Dictionary and sEntiment Reasoner).

VADER is rule-based, pure Python, ~1MB memory — ideal for CPU-only deployments.
Returns compound score in [-1.0, 1.0]:
  -1.0 = strongly negative
   0.0 = neutral
  +1.0 = strongly positive

No GPU needed. No hardware.md entry required.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

# Lazy-loaded singleton — VADER loaded on first call
_analyzer = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _analyzer = SentimentIntensityAnalyzer()
        log.info("sentiment.vader_loaded")
    return _analyzer


@dataclass
class SentimentResult:
    compound: float  # -1.0 to 1.0 overall
    positive: float  # 0.0 to 1.0
    negative: float  # 0.0 to 1.0
    neutral: float  # 0.0 to 1.0


def analyse_sentiment(text: str) -> SentimentResult:
    """Compute VADER sentiment scores for the given text.

    Works best on English text — should be called on work_text
    (post-translation) in the analyst pipeline.
    """
    if not text or len(text.strip()) < 10:
        return SentimentResult(compound=0.0, positive=0.0, negative=0.0, neutral=1.0)

    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)

    return SentimentResult(
        compound=scores["compound"],
        positive=scores["pos"],
        negative=scores["neg"],
        neutral=scores["neu"],
    )
