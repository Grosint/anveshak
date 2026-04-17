"""Ollama-powered cluster label generation (Phase 2, criteria 2.6–2.8).

All LLM calls are async. Output is validated through ClusterLabel(BaseModel)
before storage. If Ollama fails or returns invalid JSON, a fallback label
derived from the top entity is used — label is NEVER NULL.
"""
from __future__ import annotations

import json

import asyncpg
import httpx
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_CLUSTER_SAMPLE_TEXTS = """
    SELECT ci.clean_text, ee.entity_text
    FROM content_items ci
    LEFT JOIN extracted_entities ee ON ee.content_item_id = ci.id
    WHERE ci.narrative_cluster_id = $1
    ORDER BY ci.captured_at DESC
    LIMIT 10
"""

SQL_UPDATE_CLUSTER_LABEL = """
    UPDATE narrative_clusters
    SET label = $1, updated_at = NOW()
    WHERE id = $2
"""

SQL_GET_CLUSTER_SEQUENCE = """
    SELECT COUNT(*) FROM narrative_clusters
    WHERE topic_id = (SELECT topic_id FROM narrative_clusters WHERE id = $1)
"""


# ---------------------------------------------------------------------------
# Pydantic output model (criteria 2.7 — LLM output validated before storage)
# ---------------------------------------------------------------------------

class ClusterLabel(BaseModel):
    model_config = ConfigDict(strict=True)

    label: str
    confidence: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an intelligence analyst. Summarise the common narrative theme of "
    "the following news/social media excerpts in a short label (5–10 words). "
    'Respond with JSON only: {"label": "<short label>", "confidence": <float 0-1>}. '
    "Do not include any other text."
)

_BOUNDARY = "===CONTEXT==="


def build_label_prompt(texts: list[str]) -> str:
    """Build a sanitised, boundary-wrapped prompt for cluster labelling.

    User-controlled text is wrapped in boundary markers — never injected
    directly into the instruction (CLAUDE.md security rule).
    """
    excerpts = "\n\n".join(t[:300] for t in texts if t)[:3000]
    return f"{_SYSTEM_PROMPT}\n\n{_BOUNDARY}\n{excerpts}\n{_BOUNDARY}"


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

async def call_ollama_label(prompt: str) -> str:
    """Async call to Ollama for cluster label generation (criteria 2.6).

    Model and host come from settings — never hardcoded (hardware rule).
    Timeout: 30s for cluster labelling (patterns.md).
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.ollama_host}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": settings.llm_max_tokens},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"]


# ---------------------------------------------------------------------------
# Parser + fallback
# ---------------------------------------------------------------------------

def parse_label(raw: str) -> ClusterLabel:
    """Parse and validate Ollama output through ClusterLabel (criteria 2.7).

    Raises ValidationError if output is malformed.
    """
    # Extract JSON substring if model adds surrounding text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM output: {raw!r}")
    return ClusterLabel.model_validate(json.loads(raw[start:end]))


def fallback_label(cluster_seq: int, top_entity: str | None) -> str:
    """Fallback label when Ollama fails — never NULL (criteria 2.8)."""
    if top_entity:
        return f"Cluster {cluster_seq}: {top_entity}"
    return f"Cluster {cluster_seq}"


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job)
# ---------------------------------------------------------------------------

async def generate_label_for_cluster(cluster_id: str, pool: asyncpg.Pool) -> str:
    """Generate and persist a label for a narrative cluster.

    Returns the label string (either LLM-generated or fallback).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_CLUSTER_SAMPLE_TEXTS, cluster_id)
        seq = await conn.fetchval(SQL_GET_CLUSTER_SEQUENCE, cluster_id) or 1

    texts = [r["clean_text"] for r in rows if r["clean_text"]]
    top_entity = next(
        (r["entity_text"] for r in rows if r["entity_text"]), None
    )

    label: str
    if not texts:
        label = fallback_label(seq, top_entity)
        log.info("labeller.no_texts_fallback", cluster_id=cluster_id, label=label)
    else:
        prompt = build_label_prompt(texts)
        try:
            raw = await call_ollama_label(prompt)
            parsed = parse_label(raw)
            label = parsed.label
            log.info(
                "labeller.ollama_success",
                cluster_id=cluster_id,
                label=label,
                confidence=parsed.confidence,
            )
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            label = fallback_label(seq, top_entity)
            log.warning(
                "labeller.ollama_http_error",
                cluster_id=cluster_id,
                error=str(exc),
                fallback=label,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            label = fallback_label(seq, top_entity)
            log.warning(
                "labeller.ollama_parse_error",
                cluster_id=cluster_id,
                error=str(exc),
                fallback=label,
            )

    async with pool.acquire() as conn:
        await conn.execute(SQL_UPDATE_CLUSTER_LABEL, label, cluster_id)

    return label
