"""Unit tests for reporter RAG context assembly.

pytest.mark.unit — no DB, no network, no real embedding model.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


def _make_chunk(url: str, clean_text: str, credibility: float = 80.0) -> dict:
    return {
        "id": "chunk-1",
        "url": url,
        "clean_text": clean_text,
        "credibility_score_at_capture": credibility,
        "source_id": "src-1",
    }


class TestAssembleContext:
    """assemble_context builds prompt context from RAG chunks."""

    def test_empty_chunks_returns_empty_string(self):
        from anveshak.reporter.rag import assemble_context

        result, count, dr = assemble_context([], max_tokens=4000)
        assert result == ""
        assert count == 0

    def test_single_chunk_included(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [_make_chunk("https://example.com/a", "Some intelligence text here.")]
        result, count, dr = assemble_context(chunks, max_tokens=4000)
        assert "Some intelligence text here." in result
        assert "https://example.com/a" in result
        assert count == 1

    def test_truncates_at_max_tokens(self):
        from anveshak.reporter.rag import assemble_context

        # Each chunk ~400 chars → ~100 tokens. max_tokens=150 fits ~1 chunk.
        long_text = "x" * 400
        chunks = [
            _make_chunk("https://a.com/1", long_text),
            _make_chunk("https://a.com/2", long_text),
            _make_chunk("https://a.com/3", long_text),
        ]
        result, count, dr = assemble_context(chunks, max_tokens=150)
        # Only first chunk should fit (400 chars ÷ 4 = 100 tokens, second would exceed 150)
        assert "https://a.com/1" in result
        assert "https://a.com/3" not in result

    def test_chunk_format_contains_source_header(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [_make_chunk("https://news.example.com/article", "Breaking: test event.")]
        result, count, dr = assemble_context(chunks, max_tokens=4000)
        assert "[Source:" in result
        assert "https://news.example.com/article" in result

    def test_multiple_chunks_concatenated(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [
            _make_chunk("https://a.com/1", "First item."),
            _make_chunk("https://a.com/2", "Second item."),
        ]
        result, count, dr = assemble_context(chunks, max_tokens=4000)
        assert "First item." in result
        assert "Second item." in result
        assert count == 2

    def test_zero_max_tokens_returns_empty(self):
        from anveshak.reporter.rag import assemble_context

        chunks = [_make_chunk("https://a.com/1", "Some text here that is long enough.")]
        result, count, dr = assemble_context(chunks, max_tokens=0)
        assert result == ""
        assert count == 0


class TestGenerateQueryEmbedding:
    """generate_query_embedding calls analyst service /internal/embed."""

    @pytest.mark.asyncio
    async def test_returns_list_of_floats(self):
        from anveshak.reporter.rag import generate_query_embedding

        # httpx Response.json() is sync, so use MagicMock for the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3, 0.4]]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("anveshak.reporter.rag.httpx.AsyncClient", return_value=mock_client):
            result = await generate_query_embedding(
                topic_name="test topic",
                keywords=["kw1", "kw2"],
            )

        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_combines_topic_and_keywords(self):
        from anveshak.reporter.rag import generate_query_embedding

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.5] * 384]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("anveshak.reporter.rag.httpx.AsyncClient", return_value=mock_client):
            await generate_query_embedding("UAV incidents", ["drone", "airspace"])

        # Verify the POST payload contains combined text
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "UAV incidents" in payload["texts"][0]
        assert "drone" in payload["texts"][0]
