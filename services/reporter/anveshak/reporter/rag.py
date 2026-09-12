"""RAG (Retrieval-Augmented Generation) helpers for the reporter service.

Responsibilities:
- Generate a query embedding from topic name + keywords (via analyst service).
- Assemble a prompt context string from retrieved chunks, truncated to max_tokens.

Embeddings are served by the analyst-scheduler /internal/embed endpoint,
avoiding a PyTorch dependency in the reporter image.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from .audience import (
    DEFAULT_AUDIENCE,
    LEGAL_ATTRIBUTED,
    LEGAL_OMITTED,
    AudienceArg,
    ReportAudience,
    concrete_audience,
)
from .settings import settings

log = structlog.get_logger(__name__)


async def generate_query_embedding(
    topic_name: str,
    keywords: list[str],
) -> list[float]:
    """Encode topic_name + keywords into a single query vector via analyst service.

    The combined query text is: "<topic_name> <keyword1> <keyword2> ..."
    This gives pgvector something meaningful to rank chunks against.
    """
    query_text = " ".join([topic_name] + keywords)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.analyst_service_url}/internal/embed",
            json={"texts": [query_text]},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]


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


# ---------------------------------------------------------------------------
# Identifier context assembly (Engine C Step 9)
# ---------------------------------------------------------------------------

# Human-readable type labels
_TYPE_LABELS: dict[str, str] = {
    "PHONE_IN": "Phones",
    "UPI": "UPI IDs",
    "EMAIL": "Emails",
    "CRYPTO_BTC": "Crypto (BTC)",
    "CRYPTO_ETH": "Crypto (ETH)",
    "CRYPTO_TRC20": "Crypto (TRC-20)",
    "TELEGRAM_HANDLE": "Telegram Handles",
    "INSTAGRAM_HANDLE": "Instagram Handles",
    "FACEBOOK_HANDLE": "Facebook Handles",
    "X_HANDLE": "X/Twitter Handles",
    "URL_DOMAIN": "URLs",
    "GSTIN": "GSTINs",
    "UDYAM": "Udyam IDs",
    "PAN": "PAN Numbers",
    "IFSC": "IFSC Codes",
    "BANK_ACCOUNT": "Bank Accounts",
    "SEBI_REG": "SEBI Registrations",
}


def assemble_identifier_context(identifiers: list[dict[str, Any]]) -> str:
    """Format identifier data into a text block for LLM prompt injection.

    Groups identifiers by type with source counts so the LLM can reference
    them in findings and recommendations.
    """
    if not identifiers:
        return ""

    lines = ["IDENTIFIED INDICATORS IN THIS TOPIC:"]
    # Group by type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for ident in identifiers:
        itype = ident["identifier_type"]
        by_type.setdefault(itype, []).append(ident)

    for itype, items in by_type.items():
        label = _TYPE_LABELS.get(itype, itype)
        entries = ", ".join(
            f"{it['identifier_value']} ({it['source_count']} sources)" for it in items
        )
        lines.append(f"{label}: {entries}")

    return "\n".join(lines)


# The actions block is the only report section whose heading the audience
# names, so a reader of the stored markdown cannot find it by heading text.
# This marker labels it, the way "<!-- report-v2 -->" labels the format.
# Without it a report that carries no actions leaves the next section,
# citations or methodology, sitting where the actions block would have been,
# and a parser working by position renders those bullets as the report's
# recommended actions.
ACTIONS_MARKER = "<!-- recommended-actions -->"


# Recommended actions per matched template, per audience (#57)
#
# The action sets themselves live in a versioned file the customer owns, keyed
# by audience and then by template. See audience.py for why, and
# infra/configs/audiences/report_actions.yaml for the sets.


def build_recommended_actions(
    template_matches: list[dict[str, Any]],
    audience: AudienceArg = DEFAULT_AUDIENCE,
) -> list[str]:
    """Generate recommended actions for the audience the report is addressed to.

    Returns a flat list of actions drawn from the audience's action set for
    each matched template, followed by that template's legal provisions when
    the audience can act on them.

    A caller that passes no audience gets the configured default, which ships
    as the prosecution set, so it reads as it did before audiences existed. An
    explicit None is an audience that resolved to nothing, and produces no
    actions. An audience with no action set for a matched template contributes
    nothing for that template and logs the reason, rather than falling back to
    another audience's set.
    """
    if not template_matches:
        return []

    resolved = concrete_audience(audience)
    if resolved is None:
        log.warning(
            "reporter.actions_skipped",
            reason="no report audience resolved, so no action set applies",
            templates=[m.get("template_name", "") for m in template_matches],
        )
        return []

    actions: list[str] = []
    seen: set[str] = set()

    for match in template_matches:
        name = match.get("template_name", "")
        template_actions = resolved.template_actions.get(name)
        if template_actions is None:
            log.info(
                "reporter.template_actions_absent",
                audience=resolved.id,
                template=name,
                reason="this audience has no action set for this template",
            )
            template_actions = ()
        for action in template_actions:
            if action not in seen:
                seen.add(action)
                actions.append(action)

        ref = format_legal_provisions(match, resolved)
        if ref and ref not in seen:
            seen.add(ref)
            actions.append(ref)

    return actions


def format_legal_provisions(
    match: dict[str, Any],
    audience: ReportAudience,
) -> str:
    """Render one matched template's legal provisions for this audience.

    Returns "" when the match carries no provisions, or when the audience
    cannot act on them and the configuration omits them. An audience that
    cannot act on them but is shown them gets them attributed to the agency
    that would, so an assessment never reads as a charge sheet.
    """
    legal = match.get("legal_sections") or []
    if not legal or not isinstance(legal, list):
        return ""
    if audience.legal_provisions == LEGAL_OMITTED:
        return ""

    display = match.get("template_display") or match.get("template_name", "")
    legal_str = ", ".join(legal)
    if audience.legal_provisions == LEGAL_ATTRIBUTED:
        return f"Legal provisions another agency would proceed under for {display}: {legal_str}"
    return f"Applicable legal provisions for {display}: {legal_str}"
