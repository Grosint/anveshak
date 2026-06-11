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
    "URL_DOMAIN": "Domains",
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
            f"{it['identifier_value']} ({it['source_count']} sources)"
            for it in items
        )
        lines.append(f"{label}: {entries}")

    return "\n".join(lines)


# Recommended actions per template category/name
_TEMPLATE_ACTIONS: dict[str, list[str]] = {
    "mule_recruitment": [
        "Freeze identified bank accounts and UPI IDs under PMLA Section 17",
        "Request CDR (Call Detail Records) for associated phone numbers",
        "File STR (Suspicious Transaction Report) with FIU-IND",
    ],
    "investment_fraud": [
        "Report identified accounts to SEBI for investigation under PFUTP Regulations",
        "Block fraudulent UPI IDs via NPCI dispute mechanism",
        "Issue investor advisory for identified schemes",
    ],
    "maas": [
        "Freeze mule accounts identified in the network",
        "Coordinate with banks for KYC details of account holders",
        "File FIR under BNS 318 (cheating) and PMLA Section 3",
    ],
    "digital_arrest": [
        "Block identified phone numbers via DoT (Department of Telecom)",
        "Report impersonation accounts to platform operators",
        "Issue public advisory about digital arrest scam pattern",
    ],
    "job_fraud": [
        "Block identified recruitment portals/URLs",
        "Report fraudulent company registrations to MCA",
        "Request CDR for associated phone numbers",
    ],
    "pump_and_dump": [
        "Report manipulated securities to SEBI surveillance division",
        "Flag identified social media accounts for coordinated promotion",
        "Request trading data for identified accounts from exchanges",
    ],
    "fake_research_report": [
        "Report fraudulent research reports to SEBI",
        "Request takedown of hosting domains",
        "Issue advisory to registered market intermediaries",
    ],
    "drug_sale": [
        "Request CDR and IP logs for identified phone numbers and handles",
        "Coordinate with NCB for controlled delivery operations",
        "File case under NDPS Act Sections 20, 22, 25",
    ],
    "drug_delivery_recruitment": [
        "Identify and freeze payment channels (UPI, crypto wallets)",
        "Request subscriber details for identified Telegram handles",
        "Coordinate with local police for recruitment hub surveillance",
    ],
    "fake_sim_sale": [
        "Report identified SIM sellers to DoT for TRAI compliance action",
        "Block identified phone numbers used for SIM activation",
        "File FIR under IT Act 66C (identity theft)",
    ],
    "crypto_cashout": [
        "Report identified crypto wallet addresses to exchanges for freezing",
        "Trace blockchain transactions for identified wallets",
        "Coordinate with ED (Enforcement Directorate) for PMLA investigation",
    ],
}


def build_recommended_actions(template_matches: list[dict[str, Any]]) -> list[str]:
    """Generate recommended actions based on matched scam templates.

    Returns a flat list of actionable recommendations derived from template-specific
    action mappings. Includes legal section references from matched templates.
    """
    if not template_matches:
        return []

    actions: list[str] = []
    seen: set[str] = set()

    for match in template_matches:
        name = match.get("template_name", "")
        template_actions = _TEMPLATE_ACTIONS.get(name, [])
        for action in template_actions:
            if action not in seen:
                seen.add(action)
                actions.append(action)

        # Add legal section reference if available
        legal = match.get("legal_sections") or []
        if legal and isinstance(legal, list):
            legal_str = ", ".join(legal)
            ref = f"Applicable legal provisions for {match.get('template_display', name)}: {legal_str}"
            if ref not in seen:
                seen.add(ref)
                actions.append(ref)

    return actions
