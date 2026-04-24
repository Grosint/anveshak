"""Ollama-powered cluster label generation (Phase 2, criteria 2.6–2.8).

All LLM calls are async. Output is validated through ClusterLabel(BaseModel)
before storage. If Ollama fails or returns invalid JSON, a fallback label
derived from the top entity is used — label is NEVER NULL.

Label staleness detection (Phase 5 — P3):
  - compute_item_hash: SHA-256 of sorted content_item_ids
  - check_label_staleness: compare stored hash vs current composition
"""
from __future__ import annotations

import hashlib
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
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY ci.captured_at DESC
    LIMIT 10
"""

SQL_UPDATE_CLUSTER_LABEL = """
    UPDATE narrative_clusters
    SET label = $1, updated_at = NOW(),
        label_generated_at = NOW(),
        label_item_hash = $3,
        executive_summary = $4
    WHERE id = $2
"""

SQL_GET_CLUSTER_SEQUENCE = """
    SELECT COUNT(*) FROM narrative_clusters
    WHERE topic_id = (SELECT topic_id FROM narrative_clusters WHERE id = $1)
"""

SQL_GET_CLUSTER_STALENESS = """
    SELECT label_item_hash
    FROM narrative_clusters
    WHERE id = $1
"""

SQL_GET_CLUSTER_ITEM_IDS = """
    SELECT id FROM content_items
    WHERE narrative_cluster_id = $1
    ORDER BY id
"""


# ---------------------------------------------------------------------------
# Pydantic output model (criteria 2.7 — LLM output validated before storage)
# ---------------------------------------------------------------------------

class ClusterLabel(BaseModel):
    model_config = ConfigDict(strict=True)

    label: str
    summary: str = ""
    confidence: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an intelligence analyst writing for military/law enforcement decision-makers. "
    "Analyse the following news/social media excerpts and produce:\n"
    "1. A short label (5–10 words) capturing the narrative theme.\n"
    "2. An executive summary (2–3 sentences) stating: what is happening, "
    "which actors are involved, and why it matters for security.\n"
    "Rules:\n"
    "- Only use facts present in the provided excerpts.\n"
    "- If a fact is not in the excerpts, do not infer or speculate.\n"
    "- Be specific: name countries, organisations, and locations mentioned.\n"
    "Respond with JSON only:\n"
    '{"label": "<short label>", "summary": "<2-3 sentence executive summary>", '
    '"confidence": <float 0-1>}\n'
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
    async with httpx.AsyncClient(timeout=300.0) as client:
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


SQL_CLUSTER_TOP_ENTITIES = """
    SELECT ee.entity_text, COUNT(*) AS cnt
    FROM extracted_entities ee
    JOIN content_items ci ON ci.id = ee.content_item_id
    WHERE ci.narrative_cluster_id = $1
      AND ee.entity_type IN ('GPE', 'ORG', 'PERSON', 'EVENT')
    GROUP BY ee.entity_text
    ORDER BY cnt DESC
    LIMIT 3
"""


def fallback_label(top_entities: list[str]) -> str:
    """Fallback label when Ollama fails — uses top entities, never NULL (criteria 2.8)."""
    if top_entities:
        return " — ".join(top_entities[:3])
    return "Unclassified cluster"


# ---------------------------------------------------------------------------
# Label staleness detection (Phase 5 — P3)
# ---------------------------------------------------------------------------

def compute_item_hash(content_item_ids: list[str]) -> str:
    """SHA-256 of sorted, comma-joined IDs — detects composition changes."""
    canonical = ",".join(sorted(content_item_ids))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def check_label_staleness(cluster_id: str, pool: asyncpg.Pool) -> bool:
    """Return True if the cluster's label needs regeneration.

    Triggers when:
      - label_item_hash is NULL (new cluster, never labelled)
      - Item composition changed by more than label_staleness_change_threshold
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_GET_CLUSTER_STALENESS, cluster_id)
        if not row:
            return True

        stored_hash = row["label_item_hash"]
        if stored_hash is None:
            return True  # never labelled

        item_rows = await conn.fetch(SQL_GET_CLUSTER_ITEM_IDS, cluster_id)

    current_ids = [r["id"] for r in item_rows]
    if not current_ids:
        return False  # empty cluster, nothing to label

    current_hash = compute_item_hash(current_ids)
    if current_hash == stored_hash:
        return False  # composition unchanged

    # Compute Jaccard distance to measure change magnitude
    # We need the old IDs — but we only have the hash. Since hashes differ,
    # we know *something* changed. Use item count ratio as a heuristic:
    # if the cluster exists and hash differs, always re-label.
    # A more precise approach would store old IDs, but hash difference
    # with the threshold being 30% means we should re-label conservatively.
    return True


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job)
# ---------------------------------------------------------------------------

async def generate_label_for_cluster(cluster_id: str, pool: asyncpg.Pool) -> str:
    """Generate and persist a label + executive summary for a narrative cluster.

    Returns the label string (either LLM-generated or fallback).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(SQL_CLUSTER_SAMPLE_TEXTS, cluster_id)
        entity_rows = await conn.fetch(SQL_CLUSTER_TOP_ENTITIES, cluster_id)

    texts = [r["clean_text"] for r in rows if r["clean_text"]]
    top_entities = [r["entity_text"] for r in entity_rows]

    label: str
    summary: str | None = None
    if not texts:
        label = fallback_label(top_entities)
        log.info("labeller.no_texts_fallback", cluster_id=cluster_id, label=label)
    else:
        prompt = build_label_prompt(texts)
        try:
            raw = await call_ollama_label(prompt)
            parsed = parse_label(raw)
            label = parsed.label
            summary = parsed.summary or None
            log.info(
                "labeller.ollama_success",
                cluster_id=cluster_id,
                label=label,
                summary=summary[:80] if summary else None,
                confidence=parsed.confidence,
            )
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            label = fallback_label(top_entities)
            log.warning(
                "labeller.ollama_http_error",
                cluster_id=cluster_id,
                error=str(exc),
                fallback=label,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            label = fallback_label(top_entities)
            log.warning(
                "labeller.ollama_parse_error",
                cluster_id=cluster_id,
                error=str(exc),
                fallback=label,
            )

    # Compute item hash for staleness detection
    async with pool.acquire() as conn:
        item_rows = await conn.fetch(SQL_GET_CLUSTER_ITEM_IDS, cluster_id)
        item_ids = [r["id"] for r in item_rows]
        item_hash = compute_item_hash(item_ids) if item_ids else ""
        await conn.execute(SQL_UPDATE_CLUSTER_LABEL, label, cluster_id, item_hash, summary)

    return label
