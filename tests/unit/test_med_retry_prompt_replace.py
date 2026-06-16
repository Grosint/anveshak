"""Unit tests for reporter retry prompt — MED-16.

Retry suffix must replace (not append) on each attempt to prevent
3x bloat after 3 retries.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

VALID_LLM_RESPONSE = {
    "executive_summary": "Test summary.",
    "key_findings": ["Finding 1"],
    "recommendations": ["Rec 1"],
    "confidence_level": 0.8,
    "source_citations": ["https://example.com"],
    "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"},
}


class TestRetryPromptReplace:

    @pytest.mark.asyncio
    async def test_retry_prompt_does_not_grow(self):
        """After N retries, prompt length must not exceed original + one suffix."""
        from anveshak.reporter.llm import call_ollama_with_retry

        settings = MagicMock()
        settings.ollama_model = "test"
        settings.ollama_host = "http://localhost:11434"
        settings.ollama_report_timeout_s = 30

        prompts_seen: list[str] = []

        async def capture_prompt(prompt, model, host, timeout):
            prompts_seen.append(prompt)
            if len(prompts_seen) < 3:
                return "not json"
            return json.dumps(VALID_LLM_RESPONSE)

        with patch("anveshak.reporter.llm.call_ollama", side_effect=capture_prompt):
            await call_ollama_with_retry("original prompt", settings, max_retries=3)

        # Prompts 2 and 3 must be same length (replace, not append)
        assert len(prompts_seen) == 3
        assert len(prompts_seen[1]) == len(prompts_seen[2]), (
            f"Retry prompts grew: attempt 2={len(prompts_seen[1])}, "
            f"attempt 3={len(prompts_seen[2])}. Must replace suffix, not append."
        )

    @pytest.mark.asyncio
    async def test_first_attempt_uses_original_prompt(self):
        """First attempt must use the original prompt without any suffix."""
        from anveshak.reporter.llm import call_ollama_with_retry

        settings = MagicMock()
        settings.ollama_model = "test"
        settings.ollama_host = "http://localhost:11434"
        settings.ollama_report_timeout_s = 30

        prompts_seen: list[str] = []

        async def capture_prompt(prompt, model, host, timeout):
            prompts_seen.append(prompt)
            return json.dumps(VALID_LLM_RESPONSE)

        with patch("anveshak.reporter.llm.call_ollama", side_effect=capture_prompt):
            await call_ollama_with_retry("original prompt", settings, max_retries=3)

        assert prompts_seen[0] == "original prompt"
