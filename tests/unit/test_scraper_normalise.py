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
