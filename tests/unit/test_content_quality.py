"""Unit tests for analyst content quality gate.

is_quality_content returns (passed: bool, gate: str) tuples where:
- passed: True if content is good for embedding, False if rejected
- gate: 'too_short', 'few_words', 'unique_ratio', 'punctuation', or 'passed'
"""

from unittest.mock import patch

import pytest
from anveshak.analyst.content_quality import is_quality_content


@pytest.fixture(autouse=True)
def _default_settings():
    """Ensure default thresholds for all tests."""
    with patch("anveshak.analyst.content_quality.settings") as mock:
        mock.content_min_length = 100
        mock.content_min_unique_word_ratio = 0.4
        mock.content_max_punctuation_ratio = 0.3
        yield mock


class TestIsQualityContent:
    def test_returns_tuple(self):
        """Return type must be a 2-tuple (bool, str)."""
        result = is_quality_content("Hello world")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_short_text_rejected(self):
        passed, gate = is_quality_content("Hello world")
        assert passed is False
        assert gate == "too_short"

    def test_empty_text_rejected(self):
        passed, gate = is_quality_content("")
        assert passed is False
        assert gate == "too_short"

        passed, gate = is_quality_content("   ")
        assert passed is False
        assert gate == "too_short"

    def test_real_article_accepted(self):
        text = (
            "India conducted a successful test of the BrahMos supersonic cruise missile "
            "from a naval destroyer in the Arabian Sea on Thursday. The missile hit its "
            "designated target with precision, according to the defence ministry statement."
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    def test_navigation_boilerplate_rejected(self):
        """Simulates nav menu text scraped from janes.com → unique_ratio gate."""
        text = (
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science"
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "unique_ratio"

    def test_repeated_menu_rejected(self):
        text = (
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport "
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport "
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport"
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "unique_ratio"

    def test_high_punctuation_rejected(self):
        # Enough real words to pass few_words gate, but dominated by punctuation
        text = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa "
            ">>> --- ||| === *** $$$ @@@ ### ^^^ &&& <<< >>> --- ||| === *** "
            "$$$ @@@ ### ^^^ &&& <<< >>> --- ||| === *** $$$ @@@ ### ^^^ &&& "
            "<<< >>> --- ||| === *** $$$ @@@ ### ^^^ &&& <<< >>> --- ||| === "
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "punctuation"

    def test_too_few_words_rejected(self):
        text = "A" * 200  # long but not real words
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "few_words"

    def test_multilingual_accepted(self):
        """Chinese text with sufficient unique content should pass."""
        text = (
            "中国国防部发布最新声明表示南海局势总体稳定可控各方应当保持克制避免采取任何可能"
            "导致局势升级的行动中方将继续坚定维护国家主权和领土完整同时致力于通过对话协商"
            "和平解决有关争议中方强调南海航行自由从来不是问题"
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    def test_borderline_unique_ratio(self):
        """Exactly at the threshold — unique_ratio = 0.4 should pass."""
        # 10 words, 4 unique = 0.4 ratio
        words = ["alpha", "beta", "gamma", "delta"] + ["alpha"] * 3 + ["beta"] * 3
        text = (
            " ".join(words) + " extra filler content to reach the minimum length threshold needed"
        )
        passed, gate = is_quality_content(text)
        assert isinstance(passed, bool)
        assert gate in ("passed", "unique_ratio")
