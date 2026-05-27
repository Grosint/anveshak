"""Unit tests for LLM source type suggestions (Level 4)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


VALID_LLM_RESPONSE = json.dumps({
    "suggestions": [
        {
            "platform": "telegram",
            "description": "Myanmar military channels",
            "search_terms": ["tatmadaw", "myanmar military"],
            "reasoning": "Topic covers India-Myanmar border",
        },
        {
            "platform": "web",
            "description": "ASEAN defence outlets",
            "search_terms": ["asean defence", "southeast asia military"],
            "reasoning": "Regional defence coverage",
        },
    ]
})

MALFORMED_LLM_RESPONSE = "Here are my suggestions: telegram channels about Myanmar"

JSON_WITH_FENCES = f"```json\n{VALID_LLM_RESPONSE}\n```"


# ---------------------------------------------------------------------------
# LLM suggestion parsing
# ---------------------------------------------------------------------------

def test_parse_llm_suggestions_valid():
    """parse_llm_suggestions extracts structured suggestions from valid JSON."""
    from anveshak.analyst.llm_discovery import parse_llm_suggestions

    result = parse_llm_suggestions(VALID_LLM_RESPONSE)
    assert result is not None
    assert len(result) == 2
    assert result[0].platform == "telegram"
    assert result[0].search_terms == ["tatmadaw", "myanmar military"]


def test_parse_llm_suggestions_strips_fences():
    """parse_llm_suggestions handles JSON wrapped in markdown fences."""
    from anveshak.analyst.llm_discovery import parse_llm_suggestions

    result = parse_llm_suggestions(JSON_WITH_FENCES)
    assert result is not None
    assert len(result) == 2


def test_parse_llm_suggestions_returns_none_on_malformed():
    """parse_llm_suggestions returns None on non-JSON response."""
    from anveshak.analyst.llm_discovery import parse_llm_suggestions

    result = parse_llm_suggestions(MALFORMED_LLM_RESPONSE)
    assert result is None


def test_parse_llm_suggestions_returns_none_on_empty():
    """parse_llm_suggestions returns None on empty string."""
    from anveshak.analyst.llm_discovery import parse_llm_suggestions

    result = parse_llm_suggestions("")
    assert result is None


# ---------------------------------------------------------------------------
# LLM suggestion job
# ---------------------------------------------------------------------------

async def test_suggest_source_types_calls_ollama():
    """suggest_source_types enqueues Ollama call and upserts results."""
    from anveshak.analyst.llm_discovery import suggest_source_types

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock topic fetch
    mock_conn.fetchrow = AsyncMock(return_value={
        "name": "India-Myanmar Border",
        "keywords": ["myanmar", "border", "infrastructure"],
    })
    # Mock existing sources
    mock_conn.fetch = AsyncMock(return_value=[
        {"url_or_handle": "https://existing.com", "platform": "web"},
    ])
    mock_conn.execute = AsyncMock()

    with patch("anveshak.analyst.llm_discovery.call_ollama") as mock_ollama:
        mock_ollama.return_value = VALID_LLM_RESPONSE
        count = await suggest_source_types(mock_pool, "topic-1")

    assert count == 2
    mock_ollama.assert_called_once()
    assert mock_conn.execute.call_count == 2


async def test_suggest_source_types_handles_ollama_failure():
    """suggest_source_types returns 0 on Ollama failure."""
    from anveshak.analyst.llm_discovery import suggest_source_types

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_conn.fetchrow = AsyncMock(return_value={
        "name": "Test Topic",
        "keywords": ["test"],
    })
    mock_conn.fetch = AsyncMock(return_value=[])

    with patch("anveshak.analyst.llm_discovery.call_ollama") as mock_ollama:
        mock_ollama.return_value = MALFORMED_LLM_RESPONSE
        count = await suggest_source_types(mock_pool, "topic-1")

    assert count == 0
