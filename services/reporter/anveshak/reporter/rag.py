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
) -> tuple[str, int, str]:
    """Build prompt context from RAG chunks, stopping at max_tokens.

    Token estimate: len(text) // 4  (rough 1 token ≈ 4 chars heuristic).

    Each chunk is formatted as:
        [Source: <url> | Credibility: <score> | <date>]
        <clean_text>

    Chunks are included in order (already ranked by similarity from the DB query).
    Returns (context_string, source_count, date_range).
    Returns ("", 0, "") when chunks is empty or max_tokens is 0.
    """
    if not chunks or max_tokens <= 0:
        return "", 0, ""

    parts: list[str] = []
    token_count = 0
    dates: list[str] = []

    for chunk in chunks:
        url = chunk.get("url", "unknown")
        text = chunk.get("clean_text", "")
        cred = chunk.get("credibility_score_at_capture", 50.0)
        captured = chunk.get("captured_at")

        date_str = ""
        if captured is not None:
            try:
                date_str = captured.strftime("%Y-%m-%d")
                dates.append(date_str)
            except (AttributeError, TypeError):
                date_str = str(captured)[:10]
                dates.append(date_str)

        header_parts = [f"Source: {url}"]
        if cred is not None:
            header_parts.append(f"Credibility: {float(cred):.1f}")
        if date_str:
            header_parts.append(date_str)

        header = " | ".join(header_parts)
        formatted = f"[{header}]\n{text}\n\n"
        chunk_tokens = len(formatted) // 4

        if token_count + chunk_tokens > max_tokens:
            break

        parts.append(formatted)
        token_count += chunk_tokens

    source_count = len(parts)
    date_range = ""
    if dates:
        sorted_dates = sorted(set(dates))
        if len(sorted_dates) == 1:
            date_range = sorted_dates[0]
        else:
            date_range = f"{sorted_dates[0]} to {sorted_dates[-1]}"

    return "".join(parts), source_count, date_range
