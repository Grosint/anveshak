"""Sentence-transformers embedding encoder (criteria 1.15, 1.18).

Model is loaded ONCE via load_encoder() at service startup, not per-request.
"""
from __future__ import annotations

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# Module-level singleton — set by load_encoder() at startup (criteria 1.18).
_encoder = None


def load_encoder() -> None:
    """Load sentence-transformers model. Must be called ONCE at service startup."""
    global _encoder
    from sentence_transformers import SentenceTransformer

    _encoder = SentenceTransformer(settings.embedding_model)
    log.info(
        "embeddings.model_loaded",
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )


def encode_text(text: str) -> list[float]:
    """Encode text to a normalised embedding vector (criteria 1.15).

    Returns a list of floats of length settings.embedding_dimensions (default 384).
    Raises RuntimeError if load_encoder() was not called at startup.
    """
    if _encoder is None:
        raise RuntimeError(
            "Sentence-transformers encoder not loaded — call load_encoder() at startup"
        )
    vector = _encoder.encode(text, normalize_embeddings=True)
    return vector.tolist()
