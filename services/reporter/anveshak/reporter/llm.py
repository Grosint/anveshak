"""LLM calling and output validation for the reporter service.

CLAUDE.md rules enforced:
- Rule 5: All LLM calls are async (httpx.AsyncClient).
- Rule 9: LLM output is parsed through Pydantic (ReportContent) before use.
- Rule 10: Ollama only — no cloud LLM.
- Rule 2: ReportContent carries mandatory labels field.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from anveshak.models.base import Labels

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Output schema — what we expect the LLM to return
# ---------------------------------------------------------------------------

class ReportContent(BaseModel):
    """Pydantic model for validated LLM output.

    CLAUDE.md rule 9: NEVER store or display raw LLM output.
    CLAUDE.md rule 2: labels is MANDATORY and NEVER Optional.
    """
    model_config = ConfigDict(strict=True)

    executive_summary: str
    key_findings: list[str]
    recommendations: list[str]
    confidence_level: float
    source_citations: list[str]
    labels: Labels  # MANDATORY — CLAUDE.md rule 2


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.IGNORECASE)


def _extract_json_from_text(text: str) -> str:
    """Strip markdown code fences and return raw JSON string."""
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    # Try to find bare JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def parse_llm_response(raw: str) -> ReportContent:
    """Parse and validate raw LLM string into ReportContent.

    Raises:
        ValueError: if the string cannot be decoded as JSON.
        pydantic.ValidationError: if the JSON does not match ReportContent schema.
    """
    cleaned = _extract_json_from_text(raw)
    try:
        data: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc
    return ReportContent(**data)


# ---------------------------------------------------------------------------
# Ollama HTTP helpers
# ---------------------------------------------------------------------------

async def call_ollama(
    prompt: str,
    model: str,
    host: str,
    timeout: int,
) -> str:
    """POST to Ollama /api/generate and return the response string.

    Uses httpx.AsyncClient — never blocks the event loop.
    CLAUDE.md rule 10: host must be internal Docker network.
    """
    payload = {"model": model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=float(timeout)) as client:
        response = await client.post(f"{host}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
    return data.get("response", "")


async def call_ollama_with_retry(
    prompt: str,
    settings: Any,
    max_retries: int,
) -> ReportContent | None:
    """Attempt LLM generation up to max_retries times.

    On each retry the prompt is made stricter to encourage JSON-only output.
    Returns None if all retries are exhausted without a valid ReportContent.
    """
    retry_prompt = prompt
    for attempt in range(1, max_retries + 1):
        try:
            raw = await call_ollama(
                prompt=retry_prompt,
                model=settings.ollama_report_model,
                host=settings.ollama_host,
                timeout=settings.ollama_report_timeout_s,
            )
            result = parse_llm_response(raw)
            log.info("reporter.llm_success", attempt=attempt)
            return result
        except Exception as exc:
            log.warning(
                "reporter.llm_attempt_failed",
                attempt=attempt,
                max_retries=max_retries,
                error=str(exc),
            )
            # Tighten prompt on retry — instruct strict JSON-only output
            retry_prompt = (
                prompt
                + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                "No preamble, no markdown, no explanation."
            )

    log.error("reporter.llm_all_retries_failed", max_retries=max_retries)
    return None
