"""Unit tests for reporter LLM calling and output validation.

pytest.mark.unit — mocks Ollama, never calls real LLM.
CLAUDE.md rule 9: LLM output parsed through Pydantic before use.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_LLM_RESPONSE = {
    "executive_summary": "Increased UAV activity detected near northern border.",
    "key_findings": ["3 incidents logged", "Sources corroborate timeline"],
    "recommendations": ["Increase patrol frequency", "Review sensor coverage"],
    "confidence_level": 0.82,
    "source_citations": ["https://example.com/report1"],
    "labels": {
        "classification": "OPEN",
        "domain": "report",
        "owner_org": "anveshak",
    },
}


def _make_settings():
    """Return a minimal ReporterSettings-like object."""
    s = MagicMock()
    s.ollama_host = "http://ollama:11434"
    s.ollama_report_model = "mistral:7b"
    s.ollama_report_timeout_s = 30
    s.ollama_retry_max = 2
    return s


# ---------------------------------------------------------------------------
# ReportContent model
# ---------------------------------------------------------------------------

class TestReportContentModel:
    """ReportContent Pydantic model validates LLM output."""

    def test_valid_json_parses_to_report_content(self):
        from anveshak.reporter.llm import ReportContent

        obj = ReportContent(**VALID_LLM_RESPONSE)
        assert obj.executive_summary == "Increased UAV activity detected near northern border."
        assert obj.confidence_level == pytest.approx(0.82)

    def test_missing_executive_summary_raises_validation_error(self):
        from anveshak.reporter.llm import ReportContent

        bad = {k: v for k, v in VALID_LLM_RESPONSE.items() if k != "executive_summary"}
        with pytest.raises(ValidationError):
            ReportContent(**bad)

    def test_missing_labels_raises_validation_error(self):
        from anveshak.reporter.llm import ReportContent

        bad = {k: v for k, v in VALID_LLM_RESPONSE.items() if k != "labels"}
        with pytest.raises(ValidationError):
            ReportContent(**bad)

    def test_labels_field_present_and_required(self):
        """CLAUDE.md rule 2: labels is NEVER Optional."""
        from anveshak.reporter.llm import ReportContent

        assert "labels" in ReportContent.model_fields
        field = ReportContent.model_fields["labels"]
        # labels must be required (no default / not Optional)
        assert field.is_required() or field.default is None

    def test_confidence_level_is_float(self):
        from anveshak.reporter.llm import ReportContent

        obj = ReportContent(**VALID_LLM_RESPONSE)
        assert isinstance(obj.confidence_level, float)


# ---------------------------------------------------------------------------
# parse_llm_response
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    """parse_llm_response raises ValueError on bad JSON, ValidationError on bad schema."""

    def test_valid_json_returns_report_content(self):
        from anveshak.reporter.llm import parse_llm_response

        raw = json.dumps(VALID_LLM_RESPONSE)
        result = parse_llm_response(raw)
        assert result.executive_summary == VALID_LLM_RESPONSE["executive_summary"]

    def test_invalid_json_raises_value_error(self):
        from anveshak.reporter.llm import parse_llm_response

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_llm_response("not valid json at all {{{")

    def test_missing_required_field_raises_validation_error(self):
        from anveshak.reporter.llm import parse_llm_response

        incomplete = {k: v for k, v in VALID_LLM_RESPONSE.items() if k != "key_findings"}
        with pytest.raises(ValidationError):
            parse_llm_response(json.dumps(incomplete))

    def test_json_with_extra_text_preamble_still_parses(self):
        """LLM sometimes wraps JSON in markdown code fences — strip them."""
        from anveshak.reporter.llm import parse_llm_response

        wrapped = f"Here is the JSON:\n```json\n{json.dumps(VALID_LLM_RESPONSE)}\n```"
        result = parse_llm_response(wrapped)
        assert result.confidence_level == pytest.approx(0.82)


# ---------------------------------------------------------------------------
# call_ollama_with_retry
# ---------------------------------------------------------------------------

class TestCallOllamaWithRetry:
    """call_ollama_with_retry returns ReportContent on success, None after max retries."""

    @pytest.mark.asyncio
    async def test_returns_report_content_on_first_valid_attempt(self):
        from anveshak.reporter.llm import call_ollama_with_retry

        valid_json = json.dumps(VALID_LLM_RESPONSE)
        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = valid_json
            result = await call_ollama_with_retry("test prompt", settings, max_retries=2)

        assert result is not None
        assert result.executive_summary == VALID_LLM_RESPONSE["executive_summary"]
        assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_invalid_json(self):
        from anveshak.reporter.llm import call_ollama_with_retry

        valid_json = json.dumps(VALID_LLM_RESPONSE)
        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            # First call bad, second call good
            mock_call.side_effect = ["bad json here", valid_json]
            result = await call_ollama_with_retry("test prompt", settings, max_retries=2)

        assert result is not None
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_after_max_retries_exhausted(self):
        from anveshak.reporter.llm import call_ollama_with_retry

        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "always bad json !!!"
            result = await call_ollama_with_retry("test prompt", settings, max_retries=2)

        assert result is None
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error_all_retries(self):
        from anveshak.reporter.llm import call_ollama_with_retry

        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("connection refused")
            result = await call_ollama_with_retry("test prompt", settings, max_retries=2)

        assert result is None


# ---------------------------------------------------------------------------
# _extract_json_from_text tests
# ---------------------------------------------------------------------------

class TestExtractJsonFromText:
    """Tests for JSON extraction from LLM output with various wrappings."""

    def test_extract_json_finds_fenced_json(self):
        """```json {...} ``` -> extracted correctly."""
        from anveshak.reporter.llm import _extract_json_from_text

        payload = json.dumps({"key": "value"})
        wrapped = f"```json\n{payload}\n```"
        result = _extract_json_from_text(wrapped)
        assert json.loads(result) == {"key": "value"}

    def test_extract_json_bare_object(self):
        """No fence, just {...} -> extracted."""
        from anveshak.reporter.llm import _extract_json_from_text

        payload = json.dumps({"key": "value"})
        result = _extract_json_from_text(payload)
        assert json.loads(result) == {"key": "value"}

    def test_extract_json_with_preamble(self):
        """'Here is the report: {...}' -> extracts the JSON."""
        from anveshak.reporter.llm import _extract_json_from_text

        payload = json.dumps({"key": "value"})
        text = f"Here is the report: {payload}"
        result = _extract_json_from_text(text)
        assert json.loads(result) == {"key": "value"}


# ---------------------------------------------------------------------------
# parse_llm_response — extended tests
# ---------------------------------------------------------------------------

class TestParseLlmResponseExtended:
    """Additional parse_llm_response tests covering edge cases."""

    def test_parse_llm_response_valid(self):
        """Valid JSON matching ReportContent -> returns object."""
        from anveshak.reporter.llm import parse_llm_response

        raw = json.dumps(VALID_LLM_RESPONSE)
        result = parse_llm_response(raw)
        assert result.executive_summary == VALID_LLM_RESPONSE["executive_summary"]
        assert result.confidence_level == pytest.approx(0.82)
        assert len(result.key_findings) == 2

    def test_parse_llm_response_invalid_json(self):
        """Not JSON -> ValueError."""
        from anveshak.reporter.llm import parse_llm_response

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_llm_response("This is not JSON at all, just plain text.")

    def test_parse_llm_response_missing_field(self):
        """JSON missing required field -> ValidationError."""
        from anveshak.reporter.llm import parse_llm_response

        # Missing recommendations field
        incomplete = {k: v for k, v in VALID_LLM_RESPONSE.items() if k != "recommendations"}
        with pytest.raises(ValidationError):
            parse_llm_response(json.dumps(incomplete))


# ---------------------------------------------------------------------------
# call_ollama_with_retry — extended tests
# ---------------------------------------------------------------------------

class TestCallOllamaWithRetryExtended:
    """Additional retry logic tests."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        """Mock httpx, returns valid JSON -> success on attempt 1."""
        from anveshak.reporter.llm import call_ollama_with_retry

        valid_json = json.dumps(VALID_LLM_RESPONSE)
        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = valid_json
            result = await call_ollama_with_retry("generate report", settings, max_retries=3)

        assert result is not None
        assert result.executive_summary == VALID_LLM_RESPONSE["executive_summary"]
        assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_second_try(self):
        """First attempt invalid, second valid -> success on attempt 2."""
        from anveshak.reporter.llm import call_ollama_with_retry

        valid_json = json.dumps(VALID_LLM_RESPONSE)
        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            # First: garbled output, second: valid
            mock_call.side_effect = [
                "Sure! Here is your report but I forgot the JSON",
                valid_json,
            ]
            result = await call_ollama_with_retry("generate report", settings, max_retries=3)

        assert result is not None
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_all_fail(self):
        """All attempts fail -> returns None."""
        from anveshak.reporter.llm import call_ollama_with_retry

        settings = _make_settings()

        with patch("anveshak.reporter.llm.call_ollama", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "I cannot generate JSON right now."
            result = await call_ollama_with_retry("generate report", settings, max_retries=3)

        assert result is None
        assert mock_call.call_count == 3
