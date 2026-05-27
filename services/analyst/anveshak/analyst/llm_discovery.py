"""LLM-powered source type suggestions (Level 4).

Uses local Ollama to suggest source types based on topic context.
All LLM calls are async (CLAUDE.md rule 5), localhost only (rule 10),
and output is Pydantic-validated (rule 9).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import httpx
import structlog
from pydantic import ValidationError

from anveshak.models.catalog import SourceSuggestion
from anveshak.models.base import Labels

from .settings import settings

log = structlog.get_logger(__name__)

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

SQL_GET_TOPIC = "SELECT name, keywords FROM topics WHERE id = $1"

SQL_EXISTING_SOURCES = """
    SELECT url_or_handle, platform FROM sources
    WHERE is_active = TRUE
    AND id IN (SELECT source_id FROM topic_sources WHERE topic_id = $1)
"""

SQL_UPSERT_DISCOVERED_LLM = """
    INSERT INTO discovered_sources
        (id, topic_id, domain_or_handle, platform, discovery_method,
         citation_count, confidence_score, evidence, status,
         created_at, updated_at, labels)
    VALUES ($1, $2, $3, $4, 'llm_suggestion', 1, $5, $6, 'pending', $7, $7, $8)
    ON CONFLICT (topic_id, domain_or_handle, discovery_method)
    DO UPDATE SET
        confidence_score = EXCLUDED.confidence_score,
        evidence = EXCLUDED.evidence,
        updated_at = EXCLUDED.updated_at
"""

SUGGESTION_PROMPT = """You are an OSINT source discovery assistant.

Given the following topic being monitored, suggest types of sources that would be valuable to monitor.

Topic: {topic_name}
Keywords: {keywords}
Currently monitored platforms: {platforms}

Respond ONLY with valid JSON in this exact format (no preamble, no explanation):
{{
  "suggestions": [
    {{
      "platform": "telegram|web|reddit|bluesky|rss|twitter",
      "description": "brief description of the source type",
      "search_terms": ["term1", "term2"],
      "reasoning": "why this source type would be valuable"
    }}
  ]
}}

Rules:
- Do NOT invent specific URLs or channel names
- Suggest source TYPES, not specific sources
- Maximum 5 suggestions
- Focus on platforms not already monitored
"""


def _strip_json_fences(text: str) -> str:
    """Remove markdown JSON fences from LLM output."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_llm_suggestions(raw_response: str) -> list[SourceSuggestion] | None:
    """Parse and validate LLM response into SourceSuggestion models.

    Returns None if response is malformed or fails validation.
    """
    if not raw_response or not raw_response.strip():
        return None

    text = _strip_json_fences(raw_response)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("llm_discovery.json_parse_error", response_preview=text[:100])
        return None

    suggestions_data = data.get("suggestions", [])
    if not isinstance(suggestions_data, list):
        return None

    results = []
    for item in suggestions_data:
        try:
            ss = SourceSuggestion(
                platform=item["platform"],
                description=item["description"],
                search_terms=item["search_terms"],
                reasoning=item["reasoning"],
                labels=Labels(),
            )
            results.append(ss)
        except (KeyError, ValueError, ValidationError) as exc:
            log.warning("llm_discovery.validation_error", error=str(exc))
            continue

    return results if results else None


async def call_ollama(prompt: str) -> str:
    """Call local Ollama for LLM inference (CLAUDE.md rule 10: localhost only)."""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{settings.ollama_host}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2048},
            },
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def suggest_source_types_job(ctx: dict, topic_id: str) -> int:
    """ARQ job wrapper — dispatches suggest_source_types via worker."""
    pool: asyncpg.Pool = ctx["db_pool"]
    return await suggest_source_types(pool, topic_id)


async def suggest_source_types(
    pool: asyncpg.Pool,
    topic_id: str,
) -> int:
    """Generate LLM-powered source type suggestions for a topic.

    Calls local Ollama with topic context, validates output through Pydantic,
    and stores in discovered_sources with discovery_method='llm_suggestion'.
    """
    async with pool.acquire() as conn:
        topic = await conn.fetchrow(SQL_GET_TOPIC, topic_id)
        if not topic:
            log.warning("llm_discovery.topic_not_found", topic_id=topic_id)
            return 0

        # Get existing source platforms for this topic
        source_rows = await conn.fetch(SQL_EXISTING_SOURCES, topic_id)
        platforms = list({r["platform"] for r in source_rows})

        # Build prompt
        prompt = SUGGESTION_PROMPT.format(
            topic_name=topic["name"],
            keywords=", ".join(topic["keywords"] or []),
            platforms=", ".join(platforms) if platforms else "none",
        )

        # Call LLM
        try:
            raw_response = await call_ollama(prompt)
        except Exception as exc:
            log.error("llm_discovery.ollama_error", error=str(exc))
            return 0

        # Parse and validate
        suggestions = parse_llm_suggestions(raw_response)
        if not suggestions:
            log.warning("llm_discovery.parse_failed", topic_id=topic_id)
            return 0

        # Upsert into discovered_sources
        now = datetime.now(UTC)
        count = 0
        for ss in suggestions:
            domain_handle = f"llm:{ss.platform}:{ss.description[:50]}"
            evidence = {
                "search_terms": ss.search_terms,
                "reasoning": ss.reasoning,
                "description": ss.description,
            }

            await conn.execute(
                SQL_UPSERT_DISCOVERED_LLM,
                str(uuid.uuid4()),
                topic_id,
                domain_handle,
                ss.platform,
                0.5,  # LLM suggestions get moderate confidence
                json.dumps(evidence),
                now,
                LABELS_JSON,
            )
            count += 1

        log.info(
            "llm_discovery.complete",
            topic_id=topic_id,
            suggestions=count,
        )
        return count
