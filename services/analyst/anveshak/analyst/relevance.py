"""Topic relevance scoring — filter irrelevant content before clustering.

Computes cosine similarity between a content item's embedding and the topic's
query embedding (topic name + keywords). Items below the threshold are excluded
from clustering but remain in the DB for auditability.

Reuses the same pattern as backfill.py — encode topic keywords, dot-product
against content embeddings. Both vectors are L2-normalized by encode_text(),
so cosine similarity = dot product.
"""
from __future__ import annotations

import numpy as np

from .embeddings import encode_text
from .settings import settings


def build_topic_query_text(name: str, keywords: list[str]) -> str:
    """Combine topic name + keywords into a single query string for embedding.

    Same logic as backfill._build_query_text — inlined to avoid circular import.
    """
    parts = [name] + list(keywords)
    return " ".join(parts)


def build_topic_query_embedding(name: str, keywords: list[str]) -> list[float]:
    """Encode topic name + keywords into a single embedding vector."""
    query_text = build_topic_query_text(name, keywords)
    return encode_text(query_text)


def compute_topic_relevance(
    content_embedding: list[float],
    topic_query_embedding: list[float],
) -> float:
    """Cosine similarity between content embedding and topic query embedding.

    Both vectors are L2-normalized by encode_text(), so cosine similarity
    equals the dot product. Returns float in [-1.0, 1.0]; practically
    [0.0, 1.0] for same-language text.
    """
    a = np.asarray(content_embedding, dtype=np.float32)
    b = np.asarray(topic_query_embedding, dtype=np.float32)
    return float(np.dot(a, b))


def resolve_threshold(per_topic: float | None) -> float:
    """Return per-topic override if set, else global default from settings."""
    if per_topic is not None:
        return per_topic
    return settings.topic_relevance_threshold
