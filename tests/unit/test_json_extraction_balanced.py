"""Unit tests for balanced-brace JSON extraction in reporter.

Critical fix: rfind("}") breaks on JSON strings containing } characters.
The extractor must use balanced brace matching that respects string escaping.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


class TestExtractJsonBalancedBraces:
    """_extract_json_from_text must handle } inside JSON string values."""

    def test_simple_json_still_works(self):
        from anveshak.reporter.llm import _extract_json_from_text

        payload = json.dumps({"key": "value"})
        result = _extract_json_from_text(payload)
        assert json.loads(result) == {"key": "value"}

    def test_json_with_brace_in_string_value(self):
        """The critical bug: } inside a string was picked up by rfind."""
        from anveshak.reporter.llm import _extract_json_from_text

        # JSON where a string value contains }
        obj = {"summary": "Attack on building at 14:00}", "score": 0.8}
        raw = json.dumps(obj)
        text = f"Here is the report: {raw} Hope this helps!"
        result = _extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["summary"] == "Attack on building at 14:00}"
        assert parsed["score"] == 0.8

    def test_json_with_nested_braces_in_string(self):
        from anveshak.reporter.llm import _extract_json_from_text

        obj = {"data": "contains {nested} braces", "ok": True}
        raw = json.dumps(obj)
        text = f"Result: {raw}"
        result = _extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["data"] == "contains {nested} braces"

    def test_json_with_escaped_quotes(self):
        from anveshak.reporter.llm import _extract_json_from_text

        obj = {"msg": 'He said "hello}world"', "n": 1}
        raw = json.dumps(obj)
        text = f"Output: {raw}"
        result = _extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["msg"] == 'He said "hello}world"'

    def test_json_with_trailing_text_after_close(self):
        """Extra text after the JSON object must not be included."""
        from anveshak.reporter.llm import _extract_json_from_text

        obj = {"key": "val"}
        raw = json.dumps(obj)
        text = f"Here: {raw} and some trailing text with }} braces"
        result = _extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed == {"key": "val"}

    def test_fenced_json_still_works(self):
        from anveshak.reporter.llm import _extract_json_from_text

        payload = json.dumps({"key": "value"})
        wrapped = f"```json\n{payload}\n```"
        result = _extract_json_from_text(wrapped)
        assert json.loads(result) == {"key": "value"}

    def test_no_json_returns_stripped_text(self):
        from anveshak.reporter.llm import _extract_json_from_text

        result = _extract_json_from_text("no json here at all")
        assert result == "no json here at all"

    def test_json_with_backslash_in_string(self):
        """Escaped backslash before } must not end the object."""
        from anveshak.reporter.llm import _extract_json_from_text

        # {"path": "C:\\Users\\"}  — the \\ before } is an escaped backslash
        obj = {"path": "C:\\Users\\", "ok": True}
        raw = json.dumps(obj)
        text = f"Result: {raw}"
        result = _extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["path"] == "C:\\Users\\"
        assert parsed["ok"] is True
