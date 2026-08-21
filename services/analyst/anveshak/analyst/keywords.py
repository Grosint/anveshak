"""Keyword extraction using YAKE (Yet Another Keyword Extractor).

YAKE is unsupervised, language-independent, lightweight, pure Python.
No GPU needed. No hardware.md entry required.

Extracts key phrases ranked by relevance score (lower = more relevant).
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass
class KeywordResult:
    keyword: str
    score: float  # lower = more relevant (YAKE convention)


def extract_keywords(
    text: str,
    language: str = "en",
    max_keywords: int = 10,
    max_ngram_size: int = 3,
) -> list[KeywordResult]:
    """Extract top keywords/phrases from text using YAKE.

    Args:
        text: Input text (should be English — post-translation work_text).
        language: ISO 639-1 language code.
        max_keywords: Maximum number of keywords to return.
        max_ngram_size: Maximum n-gram size for keyword phrases.

    Returns:
        List of KeywordResult sorted by relevance (most relevant first).
    """
    if not text or len(text.strip()) < 20:
        return []

    import yake

    extractor = yake.KeywordExtractor(
        lan=language,
        n=max_ngram_size,
        top=max_keywords,
        dedupLim=0.7,  # deduplication threshold
        windowsSize=1,
    )

    raw_keywords = extractor.extract_keywords(text)

    return [KeywordResult(keyword=kw, score=round(score, 6)) for kw, score in raw_keywords]
