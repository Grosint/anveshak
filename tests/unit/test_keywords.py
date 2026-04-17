"""Unit tests for YAKE keyword extraction.

Tests:
  - Extracts relevant keywords from intelligence text
  - Returns KeywordResult list
  - Respects max_keywords limit
  - Short/empty text → empty list
  - Keywords are non-empty strings
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

SAMPLE_TEXT = """
Indian Navy conducted a joint maritime exercise with the French Navy in the
Arabian Sea. The exercise included anti-submarine warfare drills, surface
gunnery practice, and maritime patrol aircraft coordination. The bilateral
cooperation aims to strengthen freedom of navigation in the Indian Ocean
region.
"""


class TestExtractKeywords:

    def test_extracts_relevant_keywords(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords(SAMPLE_TEXT)
        assert len(results) > 0
        kw_texts = [r.keyword.lower() for r in results]
        # Should find at least one maritime/navy related keyword
        assert any("navy" in kw or "maritime" in kw or "exercise" in kw for kw in kw_texts)

    def test_returns_keyword_result_type(self):
        from anveshak.analyst.keywords import extract_keywords, KeywordResult

        results = extract_keywords(SAMPLE_TEXT)
        assert all(isinstance(r, KeywordResult) for r in results)

    def test_respects_max_keywords(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords(SAMPLE_TEXT, max_keywords=3)
        assert len(results) <= 3

    def test_empty_text_returns_empty(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords("")
        assert results == []

    def test_short_text_returns_empty(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords("Hi there")
        assert results == []

    def test_keywords_are_non_empty_strings(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords(SAMPLE_TEXT)
        for r in results:
            assert isinstance(r.keyword, str)
            assert len(r.keyword) > 0

    def test_scores_are_floats(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords(SAMPLE_TEXT)
        for r in results:
            assert isinstance(r.score, float)

    def test_sorted_by_relevance(self):
        from anveshak.analyst.keywords import extract_keywords

        results = extract_keywords(SAMPLE_TEXT)
        if len(results) >= 2:
            # YAKE: lower score = more relevant
            scores = [r.score for r in results]
            assert scores == sorted(scores)
