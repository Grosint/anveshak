"""Unit tests for scraper text normalisation and content hash (criteria 1.30, 1.31).

pytest.mark.unit — no external dependencies, no DB, no network.
"""
import pytest
from anveshak.scraper.normalise import normalise_text, compute_content_hash


class TestNormaliseText:
    """Criteria 1.30: unit test normalise_text() — pure function."""

    def test_lowercases(self):
        assert normalise_text("Hello WORLD") == "hello world"

    def test_collapses_whitespace(self):
        assert normalise_text("foo   bar\t\nbaz") == "foo bar baz"

    def test_strips_leading_trailing(self):
        assert normalise_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalise_text("") == ""

    def test_already_normalised(self):
        text = "simple text"
        assert normalise_text(text) == text

    def test_mixed_whitespace_types(self):
        assert normalise_text("a\t\t b\n\nc") == "a b c"

    def test_unicode_preserved(self):
        """Hindi/Devanagari text must survive normalisation — not stripped or mangled.

        Bug surface: if normalise_text used ASCII-only regex or encoding,
        multilingual content would silently lose characters, producing
        colliding content_hash values for different articles.
        """
        assert normalise_text("  भारतीय   सेना  ") == "भारतीय सेना"

    def test_newlines_and_tabs_collapsed(self):
        """\\r\\n sequences from Windows sources must collapse to single space."""
        assert normalise_text("line1\r\nline2\r\n\r\nline3") == "line1 line2 line3"

    def test_zero_width_spaces_not_collapsed(self):
        """Bug surface: zero-width spaces (U+200B) are NOT \\s in Python regex.

        Two articles differing only by zero-width spaces would get different
        hashes — defeating deduplication. This test documents the gap.
        """
        text_with_zwsp = "hello\u200bworld"
        result = normalise_text(text_with_zwsp)
        # Zero-width space is NOT whitespace in Python regex, so it survives
        assert "\u200b" in result


class TestComputeContentHash:
    """Criteria 1.31: unit test compute_content_hash() — consistent SHA-256."""

    def test_returns_hex_string(self):
        result = compute_content_hash("hello")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest length

    def test_deterministic(self):
        text = "Anveshak OSINT content item"
        assert compute_content_hash(text) == compute_content_hash(text)

    def test_case_insensitive(self):
        """Same content in different case → same hash (dedup works across case variants)."""
        assert compute_content_hash("Hello World") == compute_content_hash("hello world")

    def test_whitespace_normalised(self):
        """Extra whitespace does not produce a different hash."""
        assert compute_content_hash("foo bar") == compute_content_hash("foo   bar")

    def test_different_content_different_hash(self):
        assert compute_content_hash("content A") != compute_content_hash("content B")

    def test_returns_str_type(self):
        result = compute_content_hash("test")
        assert type(result) is str

    def test_normalises_before_hashing(self):
        """Bug caught: 'HELLO  WORLD' and 'hello world' must produce same hash.

        If compute_content_hash skipped normalise_text and hashed raw input,
        the same article from two sources with different whitespace/casing
        would bypass ON CONFLICT(content_hash) DO NOTHING deduplication.
        """
        assert compute_content_hash("HELLO  WORLD") == compute_content_hash("hello world")

    def test_trailing_whitespace_does_not_affect_hash(self):
        """Trailing whitespace from scraper output must not change hash."""
        assert compute_content_hash("article text") == compute_content_hash("article text   \n")

    def test_all_whitespace_produces_empty_hash(self):
        """All-whitespace input normalises to empty string — must produce consistent hash."""
        h1 = compute_content_hash("   ")
        h2 = compute_content_hash("\t\n")
        assert h1 == h2
        assert len(h1) == 64
