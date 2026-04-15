"""RAG (Retrieval-Augmented Generation) helpers for the reporter service.

Responsibilities:
- Lazy-load and cache the sentence-transformer embedding model.
- Generate a query embedding from topic name + keywords.
- Assemble a prompt context string from retrieved chunks, truncated to max_tokens.
"""
from __future__ import annotations

from typing import Any

import structlog
from sentence_transformers import SentenceTransformer

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache — loaded once per process
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict[str, SentenceTransformer] = {}


def get_embedding_model(model_name: str) -> SentenceTransformer:
    """Return a cached SentenceTransformer instance for *model_name*."""
    if model_name not in _MODEL_CACHE:
        log.info("rag.loading_embedding_model", model_name=model_name)
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
        log.info("rag.embedding_model_loaded", model_name=model_name)
    return _MODEL_CACHE[model_name]


def generate_query_embedding(
    topic_name: str,
    keywords: list[str],
    model_name: str,
) -> list[float]:
    """Encode topic_name + keywords into a single query vector.

    The combined query text is: "<topic_name> <keyword1> <keyword2> ..."
    This gives pgvector something meaningful to rank chunks against.
    """
    query_text = " ".join([topic_name] + keywords)
    model = get_embedding_model(model_name)
    vector = model.encode(query_text)
    return [float(v) for v in vector]


def assemble_context(
    chunks: list[dict[str, Any]],
    max_tokens: int,
) -> str:
    """Build prompt context from RAG chunks, stopping at max_tokens.

    Token estimate: len(text) // 4  (rough 1 token ≈ 4 chars heuristic).

    Each chunk is formatted as:
        [Source: <url>]
        <clean_text>

    Chunks are included in order (already ranked by similarity from the DB query).
    Returns empty string when chunks is empty or max_tokens is 0.
    """
    if not chunks or max_tokens <= 0:
        return ""

    parts: list[str] = []
    token_count = 0

    for chunk in chunks:
        url = chunk.get("url", "unknown")
        text = chunk.get("clean_text", "")
        formatted = f"[Source: {url}]\n{text}\n\n"
        chunk_tokens = len(formatted) // 4

        if token_count + chunk_tokens > max_tokens:
            break

        parts.append(formatted)
        token_count += chunk_tokens

    return "".join(parts)
