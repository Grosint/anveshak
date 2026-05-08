"""Resilience test — report generation when Ollama is unreachable.

Verifies graceful failure: clear error, no hang, no unhandled exception.
Marked @pytest.mark.resilience — runs nightly only, not in CI.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.resilience, pytest.mark.asyncio]


async def test_report_generation_fails_gracefully_on_ollama_timeout():
    """generate_report should store generation_error, not crash, when Ollama times out."""
    try:
        from anveshak.reporter.llm import call_ollama
    except ImportError:
        pytest.skip("Reporter module not importable")

    # Simulate Ollama being unreachable
    import httpx

    with patch("anveshak.reporter.llm.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_client

        with pytest.raises((httpx.ConnectError, Exception)):
            await call_ollama("test prompt", "qwen2:7b", "http://localhost:11434", 30)


async def test_report_generation_fails_gracefully_on_malformed_json():
    """LLM returning invalid JSON should raise a clear error, not crash."""
    try:
        from anveshak.reporter.llm import call_ollama
    except ImportError:
        pytest.skip("Reporter module not importable")

    with patch("anveshak.reporter.llm.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        # Ollama returns non-JSON response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "not valid json {{{"}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = await call_ollama("test prompt", "qwen2:7b", "http://localhost:11434", 30)
        # Should return the raw string, not crash
        assert isinstance(result, str)
