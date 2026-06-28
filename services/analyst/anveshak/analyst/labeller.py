"""Ollama-powered cluster label generation (Phase 2, criteria 2.6–2.8).

All LLM calls are async. Output is validated through ClusterLabel(BaseModel)
before storage. If Ollama fails or returns invalid JSON, a fallback label
derived from structured context is used — label is NEVER NULL.

v2: Enriched prompt with structured context (entity table, platform breakdown,
topic name, scam templates, identifier counts). Diplomatic sensitivity guard.

Label staleness detection (Phase 5 — P3):
  - compute_item_hash: SHA-256 of sorted content_item_ids
  - check_label_staleness: compare stored hash vs current composition
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field

import asyncpg
import httpx
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL — module-level constants
# ---------------------------------------------------------------------------

SQL_CLUSTER_LABEL_CONTEXT = """
WITH sample_texts AS (
    SELECT COALESCE(ci.translated_text, ci.clean_text) AS text,
           ci.labels AS item_labels
    FROM content_items ci
    WHERE ci.narrative_cluster_id = $1
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY ci.captured_at DESC
    LIMIT 10
),
top_entities AS (
    SELECT ee.entity_type, ee.entity_text, COUNT(*) AS cnt
    FROM extracted_entities ee
    JOIN content_items ci ON ci.id = ee.content_item_id
    WHERE ci.narrative_cluster_id = $1
      AND ee.entity_type IN ('GPE', 'ORG', 'PERSON', 'EVENT')
    GROUP BY ee.entity_type, ee.entity_text
    ORDER BY cnt DESC
    LIMIT 10
),
platform_summary AS (
    SELECT s.platform, s.name AS source_name,
           COUNT(ci.id) AS item_count,
           MIN(ci.captured_at) AS earliest,
           MAX(ci.captured_at) AS latest
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.narrative_cluster_id = $1
    GROUP BY s.platform, s.name
    ORDER BY item_count DESC
),
topic_info AS (
    SELECT t.name AS topic_name,
           array_to_string(t.keywords, ', ') AS topic_keywords
    FROM topics t
    JOIN narrative_clusters nc ON nc.topic_id = t.id
    WHERE nc.id = $1
)
SELECT 'texts' AS section, text AS val1, NULL AS val2, NULL AS val3,
       item_labels::text AS val4, NULL::bigint AS val5,
       NULL::timestamptz AS val6, NULL::timestamptz AS val7
FROM sample_texts
UNION ALL
SELECT 'entity', entity_type, entity_text, NULL, NULL, cnt, NULL, NULL
FROM top_entities
UNION ALL
SELECT 'platform', platform, source_name, NULL, NULL, item_count, earliest, latest
FROM platform_summary
UNION ALL
SELECT 'topic', topic_name, topic_keywords, NULL, NULL, NULL, NULL, NULL
FROM topic_info
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

# Keep old SQL constants for backward compat (used by regeneration script)
SQL_CLUSTER_SAMPLE_TEXTS = """
    SELECT ci.clean_text, ee.entity_text
    FROM content_items ci
    LEFT JOIN extracted_entities ee ON ee.content_item_id = ci.id
    WHERE ci.narrative_cluster_id = $1
      AND COALESCE(ci.content_quality, 'good') != 'low_quality'
    ORDER BY ci.captured_at DESC
    LIMIT 10
"""

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


# ---------------------------------------------------------------------------
# Pydantic output model (criteria 2.7 — LLM output validated before storage)
# ---------------------------------------------------------------------------

class ClusterLabel(BaseModel):
    model_config = ConfigDict(strict=True)

    label: str
    summary: str = ""
    confidence: float  # 0.0–1.0
    labels: dict = {}  # CLAUDE.md rule 2 — mandatory on all models


# ---------------------------------------------------------------------------
# Structured context from CTE query
# ---------------------------------------------------------------------------

@dataclass
class ClusterContext:
    """Parsed structured context for cluster label generation."""

    texts: list[str] = field(default_factory=list)
    entities: list[tuple[str, str, int]] = field(default_factory=list)  # (type, text, count)
    platforms: list[tuple[str, str, int]] = field(default_factory=list)  # (platform, name, count)
    platform_earliest: dict[str, str] = field(default_factory=dict)
    platform_latest: dict[str, str] = field(default_factory=dict)
    topic_name: str = ""
    topic_keywords: str = ""
    scam_templates: list[str] = field(default_factory=list)
    identifier_counts: dict[str, int] = field(default_factory=dict)


def parse_context_rows(rows: list[dict]) -> ClusterContext:
    """Parse CTE UNION ALL rows into structured ClusterContext."""
    ctx = ClusterContext()
    template_set: set[str] = set()
    id_counter: Counter[str] = Counter()

    for row in rows:
        section = row["section"]

        if section == "texts":
            text = row["val1"]
            if text:
                ctx.texts.append(text)
            # Extract scam_template and identifiers from labels JSONB
            labels_raw = row.get("val4")
            if labels_raw:
                try:
                    labels = json.loads(labels_raw) if isinstance(labels_raw, str) else labels_raw
                    if isinstance(labels, dict):
                        tmpl = labels.get("scam_template")
                        if tmpl:
                            template_set.add(tmpl)
                        idents = labels.get("identifiers")
                        if isinstance(idents, dict):
                            for id_type, values in idents.items():
                                if isinstance(values, list):
                                    id_counter[id_type] += len(values)
                except (json.JSONDecodeError, TypeError):
                    pass

        elif section == "entity":
            entity_type = row["val1"] or ""
            entity_text = row["val2"] or ""
            cnt = row["val5"] or 0
            if entity_type and entity_text:
                ctx.entities.append((entity_type, entity_text, int(cnt)))

        elif section == "platform":
            platform = row["val1"] or ""
            source_name = row["val2"] or ""
            item_count = row["val5"] or 0
            if platform:
                ctx.platforms.append((platform, source_name, int(item_count)))
                earliest = row.get("val6")
                latest = row.get("val7")
                if earliest:
                    ctx.platform_earliest[platform] = str(earliest)
                if latest:
                    ctx.platform_latest[platform] = str(latest)

        elif section == "topic":
            ctx.topic_name = row["val1"] or ""
            ctx.topic_keywords = row["val2"] or ""

    ctx.scam_templates = sorted(template_set)
    ctx.identifier_counts = dict(id_counter)
    return ctx


# ---------------------------------------------------------------------------
# Prompt builder (v2 — enriched with structured context)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an intelligence analyst writing for law enforcement decision-makers.\n"
    "Analyse the provided intelligence context and produce:\n"
    "1. A short label (5–12 words) capturing the ACTIVITY or NARRATIVE.\n"
    "2. An executive summary (2–3 sentences).\n\n"
    "RULES:\n"
    "- Label describes WHAT IS HAPPENING, not just WHO or WHERE.\n"
    "- Only use facts present in the provided context.\n"
    "- NEVER speculate, attribute motives, or use these words: "
    "'influence operation', 'propaganda', 'disinformation', 'psyop', 'campaign'.\n"
    "- Always produce label and summary in English.\n"
    "- Label must be under 15 words.\n\n"
    "GOOD labels:\n"
    '- "Investment fraud recruitment via Telegram channels"\n'
    '- "Mule account network linked to UPI transactions"\n'
    '- "Drug trafficking discussion mentioning crypto payments"\n\n'
    "BAD labels:\n"
    '- "TGCSB — Telangana — Hyderabad" (just entity names)\n'
    '- "News articles about crime" (too vague)\n'
    '- "Chinese propaganda campaign against India" (attribution language)\n\n'
    "Respond with JSON only:\n"
    '{"label": "<short label>", "summary": "<2-3 sentences>", "confidence": <0-1>}\n'
    "Do not include any other text."
)

_BOUNDARY = "===CONTEXT==="


def build_label_prompt(ctx: ClusterContext) -> str:
    """Build enriched, boundary-wrapped prompt for cluster labelling.

    Includes structured context: topic name, entity table, platform breakdown,
    scam templates, identifier counts, and text excerpts.
    User-controlled text wrapped in boundary markers (security rule).
    """
    parts: list[str] = [_SYSTEM_PROMPT, ""]

    # Topic context
    if ctx.topic_name:
        topic_line = f"Topic: {ctx.topic_name}"
        if ctx.topic_keywords:
            topic_line += f" (keywords: {ctx.topic_keywords})"
        parts.append(topic_line)

    # Entity table
    if ctx.entities:
        entity_lines = [f"  {etype}: {etext} ({cnt} mentions)"
                        for etype, etext, cnt in ctx.entities]
        parts.append("Entities:\n" + "\n".join(entity_lines))

    # Platform breakdown
    if ctx.platforms:
        platform_lines = []
        for platform, source_name, count in ctx.platforms:
            platform_lines.append(f"  {platform.upper()}: {source_name} ({count} items)")
        parts.append("Sources:\n" + "\n".join(platform_lines))

    # Scam templates from Engine C
    if ctx.scam_templates:
        parts.append("Detected patterns: " + ", ".join(ctx.scam_templates))

    # Identifier counts
    if ctx.identifier_counts:
        id_parts = [f"{count} {id_type}" for id_type, count in ctx.identifier_counts.items()]
        parts.append("Identifiers found: " + ", ".join(id_parts))

    # Text excerpts (boundary-wrapped)
    if ctx.texts:
        excerpts = "\n\n".join(t[:500] for t in ctx.texts)[:4000]
        parts.append(f"\n{_BOUNDARY}\n{excerpts}\n{_BOUNDARY}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

async def call_ollama_label(prompt: str) -> str:
    """Async call to Ollama for cluster label generation (criteria 2.6).

    Model and host come from settings — never hardcoded (hardware rule).
    Timeout: 300s for cluster labelling.
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
    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

    # Extract JSON substring if model adds surrounding text
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM output: {raw!r}")
    return ClusterLabel.model_validate(json.loads(cleaned[start:end]))


def fallback_label(
    top_entities: list[str],
    topic_name: str = "",
    scam_templates: list[str] | None = None,
) -> str:
    """Fallback label when Ollama fails — template-driven, never NULL (criteria 2.8).

    Priority: scam template > topic + entities > entities only > unclassified.
    """
    if scam_templates:
        template = scam_templates[0].replace("_", " ").title()
        if topic_name:
            return f"{template}: {topic_name}"
        return template
    if top_entities and topic_name:
        return f"{topic_name}: {', '.join(top_entities[:2])}"
    if top_entities:
        return f"Activity: {', '.join(top_entities[:3])}"
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
      - Item composition changed (hash differs)
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
    return current_hash != stored_hash


# ---------------------------------------------------------------------------
# Top-level orchestrator (called from ARQ job)
# ---------------------------------------------------------------------------

async def generate_label_for_cluster(cluster_id: str, pool: asyncpg.Pool) -> str:
    """Generate and persist a label + executive summary for a narrative cluster.

    Uses enriched CTE query for structured context (v2).
    Returns the label string (either LLM-generated or fallback).
    """
    # Single CTE query for all context
    async with pool.acquire() as conn:
        context_rows = await conn.fetch(SQL_CLUSTER_LABEL_CONTEXT, cluster_id)

    ctx = parse_context_rows([dict(r) for r in context_rows])
    top_entities = [etext for _, etext, _ in ctx.entities[:3]]

    label: str
    summary: str | None = None

    if not ctx.texts:
        label = fallback_label(top_entities, ctx.topic_name, ctx.scam_templates or None)
        log.info("labeller.no_texts_fallback", cluster_id=cluster_id, label=label)
    else:
        prompt = build_label_prompt(ctx)
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
            label = fallback_label(top_entities, ctx.topic_name, ctx.scam_templates or None)
            log.warning(
                "labeller.ollama_http_error",
                cluster_id=cluster_id,
                error=str(exc),
                fallback=label,
            )
        except (ValidationError, ValueError, KeyError) as exc:
            label = fallback_label(top_entities, ctx.topic_name, ctx.scam_templates or None)
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
