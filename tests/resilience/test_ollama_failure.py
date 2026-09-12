"""Resilience test - report generation when Ollama is unreachable.

Verifies graceful failure: clear error, no hang, no unhandled exception.
Marked @pytest.mark.resilience - runs nightly only, not in CI.

call_ollama routes through the SDK provider (`anveshak.llm.generate`, ADR 0002)
rather than driving httpx itself, so the provider call is the seam these tests
patch. Patching httpx inside the reporter's llm module tested a collaborator it
stopped having.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.resilience, pytest.mark.asyncio]


async def test_report_generation_fails_gracefully_on_ollama_timeout():
    """An unreachable provider raises, so the job records the error rather than hanging."""
    try:
        from anveshak.reporter.llm import call_ollama
    except ImportError:
        pytest.skip("Reporter module not importable")

    import httpx

    with patch("anveshak.reporter.llm.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await call_ollama("test prompt", "qwen2:7b", "http://localhost:11434", 30)


async def test_report_generation_fails_gracefully_on_malformed_json():
    """A provider returning non-JSON hands back the raw string, and never crashes here.

    Validation is the caller's job: rule 9 puts every response through a
    Pydantic model before storage, and call_ollama is below that line.
    """
    try:
        from anveshak.reporter.llm import call_ollama
    except ImportError:
        pytest.skip("Reporter module not importable")

    with patch("anveshak.reporter.llm.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = "not valid json {{{"

        result = await call_ollama("test prompt", "qwen2:7b", "http://localhost:11434", 30)
        assert result == "not valid json {{{"
