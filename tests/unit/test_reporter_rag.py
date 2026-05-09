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


class TestRAGCredibilityFiltering:
    """Verify credibility_min parameter is threaded to fetch_rag_chunks."""

    @pytest.mark.asyncio
    async def test_credibility_min_passed_to_fetch_rag_chunks(self):
        """generate_report passes report's credibility_min_filter to fetch_rag_chunks."""
        from anveshak.reporter.worker import generate_report

        report = {
            "id": "report-1",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            "credibility_min_filter": 60.0,  # custom threshold
        }
        topic = {"id": "topic-1", "name": "Test", "keywords": ["test"]}
        chunks = [{"id": "c1", "source_id": "s1", "clean_text": "text", "url": "https://x.com"}]
        rc = MagicMock()
        rc.executive_summary = "Summary"
        rc.key_findings = ["F1"]
        rc.recommendations = ["R1"]
        rc.source_citations = ["https://x.com"]
        rc.confidence_level = 0.9

        ctx = {"db": AsyncMock(), "settings": MagicMock(
            rag_top_k=10, rag_max_context_tokens=4000,
            ollama_model="test", ollama_host="http://ollama:11434",
            ollama_report_timeout_s=30, ollama_retry_max=2,
        )}

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("anveshak.reporter.worker.assemble_context") as mock_ctx, \
             patch("anveshak.reporter.worker.render_prompt") as mock_prompt, \
             patch("anveshak.reporter.worker.call_ollama_with_retry", new_callable=AsyncMock) as mock_llm, \
             patch("anveshak.reporter.worker.geocode_locations") as mock_geo, \
             patch("anveshak.reporter.worker.build_geojson") as mock_geojson, \
             patch("anveshak.reporter.worker.extract_locations_from_text") as mock_extract:
            mock_db.fetch_report = AsyncMock(return_value=report)
            mock_db.fetch_topic = AsyncMock(return_value=topic)
            mock_db.fetch_rag_chunks = AsyncMock(return_value=chunks)
            mock_db.fetch_sources_for_snapshot = AsyncMock(return_value={})
            mock_db.fetch_topic_location_entities = AsyncMock(return_value=[])
            mock_db.set_report_generated = AsyncMock(return_value=True)
            mock_db.update_job_status = AsyncMock()
            mock_embed.return_value = [0.1] * 384
            mock_ctx.return_value = ("context", 1, "2026-01-01")
            mock_prompt.return_value = "prompt"
            mock_llm.return_value = rc
            mock_geo.return_value = []
            mock_geojson.return_value = {"type": "FeatureCollection", "features": []}
            mock_extract.return_value = []

            await generate_report(ctx, "report-1")

            # Verify credibility_min=60.0 was passed to fetch_rag_chunks
            # Args: (pool, topic_id, query_embedding, credibility_min, top_k)
            mock_db.fetch_rag_chunks.assert_awaited_once()
            call_args = mock_db.fetch_rag_chunks.call_args
            cred_arg = call_args[0][3]
            assert cred_arg == 60.0, f"Expected credibility_min=60.0, got {cred_arg}"

    @pytest.mark.asyncio
    async def test_default_credibility_min_is_30(self):
        """When report row has no credibility_min_filter, default is 30.0."""
        from anveshak.reporter.worker import generate_report

        report = {
            "id": "report-2",
            "topic_id": "topic-1",
            "report_type": "intelligence_brief",
            # credibility_min_filter not set — should default to 30.0
        }
        topic = {"id": "topic-1", "name": "Test", "keywords": []}

        ctx = {"db": AsyncMock(), "settings": MagicMock(
            rag_top_k=10, rag_max_context_tokens=4000,
            ollama_model="test", ollama_host="http://o:11434",
            ollama_report_timeout_s=30, ollama_retry_max=2,
        )}

        with patch("anveshak.reporter.worker.db") as mock_db, \
             patch("anveshak.reporter.worker.generate_query_embedding", new_callable=AsyncMock) as mock_embed:
            mock_db.fetch_report = AsyncMock(return_value=report)
            mock_db.fetch_topic = AsyncMock(return_value=topic)
            mock_db.fetch_rag_chunks = AsyncMock(return_value=[])  # empty → will return early
            mock_db.set_report_failed = AsyncMock()
            mock_embed.return_value = [0.1] * 384

            await generate_report(ctx, "report-2")

            # Verify credibility_min=30.0 (default) was passed
            # Args: (pool, topic_id, query_embedding, credibility_min, top_k)
            call_args = mock_db.fetch_rag_chunks.call_args
            cred_arg = call_args[0][3]
            assert cred_arg == 30.0, f"Expected default 30.0, got {cred_arg}"


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
