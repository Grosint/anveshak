"""LLM calling and output validation for the reporter service.

AGENTS.md rules enforced:
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
from anveshak.models.base import Labels
from pydantic import BaseModel, ConfigDict

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Output schema — what we expect the LLM to return
# ---------------------------------------------------------------------------


class LegalSectionRef(BaseModel):
    """One applicable legal provision mapped to a finding."""

    model_config = ConfigDict(strict=True)

    act: str  # BNS | IT Act | UAPA | PMLA | NDPS
    section: str  # e.g. "318", "66C"
    description: str  # Short title of the provision
    evidence_ref: str  # Which source/finding supports this mapping
    labels: Labels


class LegalMapping(BaseModel):
    """Maps a key finding to applicable legal provisions."""

    model_config = ConfigDict(strict=True)

    finding: str
    sections: list[LegalSectionRef]
    labels: Labels


class LensEvaluation(BaseModel):
    """One perspective in the three-lens evaluation framework."""

    model_config = ConfigDict(strict=True)

    perspective: str  # "Brigadier" | "NIA Chief" | "R&AW Chief"
    threat_assessment: str
    priority_actions: list[str]
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL
    labels: Labels


class ThreeLensAnnexure(BaseModel):
    """Three-lens evaluation: Brigadier, NIA Chief, R&AW Chief perspectives."""

    model_config = ConfigDict(strict=True)

    evaluations: list[LensEvaluation]
    labels: Labels


class ReportContent(BaseModel):
    """Pydantic model for validated LLM output.

    AGENTS.md rule 9: NEVER store or display raw LLM output.
    AGENTS.md rule 2: labels is MANDATORY and NEVER Optional.
    """

    model_config = ConfigDict(strict=True)

    executive_summary: str
    key_findings: list[str]
    recommendations: list[str]
    confidence_level: float
    source_citations: list[str]
    labels: Labels  # MANDATORY — AGENTS.md rule 2
    # Legal mapping — populated when include_legal_mapping=True in prompt
    legal_sections: list[dict[str, Any]] = []
    # Three-lens evaluation — populated when include_three_lens=True in prompt
    three_lens: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```", re.IGNORECASE)


def _extract_json_from_text(text: str) -> str:
    """Strip markdown code fences and return raw JSON string.

    Uses balanced-brace matching that respects JSON string escaping,
    so } characters inside string values don't prematurely end extraction.
    """
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    # Balanced brace extraction — respects string escaping
    start = text.find("{")
    if start == -1:
        return text.strip()
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    # Fallback: no balanced match found
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
    AGENTS.md rule 10: host must be internal Docker network.
    """
    payload = {"model": model, "prompt": prompt, "stream": False}
    async with httpx.AsyncClient(timeout=float(timeout)) as client:
        response = await client.post(f"{host}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
    return data.get("response", "")


# ---------------------------------------------------------------------------
# Source Assessment Brief — Phase 2 output model
# ---------------------------------------------------------------------------


class AssessmentCitation(BaseModel):
    """A factual claim with specific content_item_id references."""

    model_config = ConfigDict(strict=True)

    claim: str
    content_item_ids: list[str]
    labels: Labels


class SourceAssessmentBrief(BaseModel):
    """Validated LLM output for source assessment.

    Every claim MUST cite specific content_item_ids.
    AGENTS.md rule 9: never store raw LLM output.
    AGENTS.md rule 2: labels is MANDATORY.
    """

    model_config = ConfigDict(strict=True)

    source_characterization: str  # 2-3 sentences: what this source is
    posting_behavior: str  # posting patterns, frequency, timing
    key_themes: list[str]  # top 5 themes this source covers
    narrative_role: str  # originator | amplifier | aggregator
    intelligence_value: str  # HIGH | MEDIUM | LOW with justification
    risk_indicators: list[str]  # red flags (disinfo, coordination, etc.)
    cited_claims: list[AssessmentCitation]
    confidence_level: float  # 0.0–1.0
    labels: Labels


def parse_assessment_response(raw: str) -> SourceAssessmentBrief:
    """Parse and validate raw LLM string into SourceAssessmentBrief.

    Raises ValueError / ValidationError on failure.
    """
    cleaned = _extract_json_from_text(raw)
    data: dict[str, Any] = json.loads(cleaned)
    return SourceAssessmentBrief(**data)


async def call_ollama_for_assessment(
    prompt: str,
    settings: Any,
    max_retries: int,
) -> SourceAssessmentBrief | None:
    """Attempt assessment brief generation with retries.

    Same pattern as call_ollama_with_retry but uses SourceAssessmentBrief schema.
    """
    retry_prompt = prompt
    for attempt in range(1, max_retries + 1):
        try:
            raw = await call_ollama(
                prompt=retry_prompt,
                model=settings.ollama_model,
                host=settings.ollama_host,
                timeout=settings.ollama_report_timeout_s,
            )
            result = parse_assessment_response(raw)
            log.info("reporter.assessment_llm_success", attempt=attempt)
            return result
        except Exception as exc:
            log.warning(
                "reporter.assessment_llm_failed",
                attempt=attempt,
                max_retries=max_retries,
                error=str(exc),
            )
            retry_prompt = (
                prompt + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                "No preamble, no markdown, no explanation."
            )

    log.error("reporter.assessment_llm_all_retries_failed", max_retries=max_retries)
    return None


# ---------------------------------------------------------------------------
# BLUF (Bottom Line Up Front) — minimal v2 model
# ---------------------------------------------------------------------------


class BlufContent(BaseModel):
    """Minimal LLM output for data-driven reports.

    Only a 2-3 sentence BLUF paragraph + confidence. Everything else is SQL.
    AGENTS.md rule 2: labels is MANDATORY.
    AGENTS.md rule 9: validated before storage.
    """

    model_config = ConfigDict(strict=True)

    bluf: str
    confidence_level: float
    labels: Labels


def parse_bluf_response(raw: str) -> BlufContent:
    """Parse and validate raw LLM string into BlufContent.

    Raises:
        ValueError: if the string cannot be decoded as JSON.
        pydantic.ValidationError: if the JSON does not match BlufContent schema.
    """
    cleaned = _extract_json_from_text(raw)
    try:
        data: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from LLM: {exc}") from exc
    return BlufContent(**data)


async def call_ollama_for_bluf(
    prompt: str,
    settings: Any,
    max_retries: int,
) -> BlufContent | None:
    """Attempt BLUF generation with retries.

    Same pattern as call_ollama_with_retry but uses BlufContent schema (much simpler).
    Returns None if all retries are exhausted.
    """
    retry_prompt = prompt
    for attempt in range(1, max_retries + 1):
        try:
            raw = await call_ollama(
                prompt=retry_prompt,
                model=settings.ollama_model,
                host=settings.ollama_host,
                timeout=settings.ollama_report_timeout_s,
            )
            result = parse_bluf_response(raw)
            log.info("reporter.bluf_llm_success", attempt=attempt)
            return result
        except Exception as exc:
            log.warning(
                "reporter.bluf_llm_failed",
                attempt=attempt,
                max_retries=max_retries,
                error=str(exc),
            )
            retry_prompt = (
                prompt + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                "No preamble, no markdown, no explanation."
            )

    log.error("reporter.bluf_llm_all_retries_failed", max_retries=max_retries)
    return None


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
                model=settings.ollama_model,
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
                prompt + "\n\nIMPORTANT: Respond with ONLY the JSON object. "
                "No preamble, no markdown, no explanation."
            )

    log.error("reporter.llm_all_retries_failed", max_retries=max_retries)
    return None
