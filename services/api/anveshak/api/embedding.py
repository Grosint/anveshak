"""Shared embedding helper — encodes text via analyst service.

Avoids PyTorch dependency in the API image by delegating to the analyst
service's /internal/embed endpoint.
"""
from __future__ import annotations

import httpx
import structlog

from .settings import settings

log = structlog.get_logger(__name__)


async def embed_query(query: str) -> str:
    """Encode a search query to pgvector literal string via analyst service."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.analyst_service_url}/internal/embed",
            json={"texts": [query]},
        )
        resp.raise_for_status()
        vec = resp.json()["embeddings"][0]
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
