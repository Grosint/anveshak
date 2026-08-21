"""Engine C — Scam Template Library (Step 2).

Match content against known fraud/info-op/narco patterns using
keyword overlap + identifier validation + embedding similarity.

Pure functions — no DB, no I/O. Safe to unit-test without infrastructure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScamTemplate:
    """Definition of a scam/info-op/narco template."""

    name: str
    display: str
    category: str  # fraud | info_op | narco | custom
    keywords: list[str]
    min_keyword_hits: int
    expected_identifiers: list[str]  # identifier types expected in matching content
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    reference_embedding: list[float] | None
    legal_sections: list[str]


@dataclass(frozen=True)
class TemplateMatch:
    """Result of matching content against a template."""

    template_name: str
    template_display: str
    confidence: float
    matched_keywords: list[str]
    matched_identifier_types: list[str]
    legal_sections: list[str]
    severity: str


# ---------------------------------------------------------------------------
# Confidence weights
# ---------------------------------------------------------------------------

_KW_WEIGHT = 0.6
_ID_WEIGHT = 0.4
_CONFIDENCE_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------


def match_templates(
    content_keywords: set[str],
    identifier_types: set[str],
    content_embedding: list[float] | None,
    templates: list[ScamTemplate],
) -> TemplateMatch | None:
    """Match content against active templates. Return highest-confidence match.

    Args:
        content_keywords: Keywords extracted from content (lowercased by caller).
        identifier_types: Set of identifier type strings found in content.
        content_embedding: L2-normalized embedding vector, or None.
        templates: Active templates to match against.

    Returns:
        Highest-confidence TemplateMatch with confidence >= 0.5, or None.
    """
    if not templates or not content_keywords:
        return None

    content_kw_lower = {kw.lower() for kw in content_keywords}
    best: TemplateMatch | None = None

    for t in templates:
        template_kw_lower = [kw.lower() for kw in t.keywords]
        matched_kw = [kw for kw in template_kw_lower if kw in content_kw_lower]

        if len(matched_kw) < t.min_keyword_hits:
            continue

        keyword_score = len(matched_kw) / len(t.keywords) if t.keywords else 0.0

        # Identifier match: fraction of expected identifiers found
        if t.expected_identifiers:
            matched_ids = [i for i in t.expected_identifiers if i in identifier_types]
            identifier_score = len(matched_ids) / len(t.expected_identifiers)
        else:
            matched_ids = []
            identifier_score = 1.0  # no penalty when no identifiers expected

        kw_id_confidence = _KW_WEIGHT * keyword_score + _ID_WEIGHT * identifier_score

        # Embedding similarity
        embedding_score = 0.0
        if content_embedding is not None and t.reference_embedding is not None:
            embedding_score = _cosine_similarity(content_embedding, t.reference_embedding)

        confidence = max(kw_id_confidence, embedding_score)

        if confidence < _CONFIDENCE_THRESHOLD:
            continue

        match = TemplateMatch(
            template_name=t.name,
            template_display=t.display,
            confidence=confidence,
            matched_keywords=matched_kw,
            matched_identifier_types=matched_ids,
            legal_sections=t.legal_sections,
            severity=t.severity,
        )

        if best is None or confidence > best.confidence:
            best = match

    return best


# ---------------------------------------------------------------------------
# 11 built-in templates
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: list[ScamTemplate] = [
    ScamTemplate(
        name="investment_fraud",
        display="Investment Fraud",
        category="fraud",
        keywords=[
            "invest",
            "guaranteed",
            "returns",
            "profit",
            "double",
            "money",
            "daily",
            "monthly",
            "scheme",
            "fixed return",
            "100%",
            "no risk",
            "minimum investment",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "UPI", "CRYPTO_BTC", "CRYPTO_ETH"],
        severity="CRITICAL",
        reference_embedding=None,
        legal_sections=["SEBI (PFUTP) Regulations", "IPC 420", "SEBI Act Section 12A"],
    ),
    ScamTemplate(
        name="mule_recruitment",
        display="Mule Account Recruitment",
        category="fraud",
        keywords=[
            "bank",
            "account",
            "commission",
            "per transaction",
            "easy money",
            "salary",
            "income",
            "rent your account",
            "lend account",
            "no risk",
            "just provide",
            "earn daily",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "TELEGRAM_HANDLE", "UPI"],
        severity="CRITICAL",
        reference_embedding=None,
        legal_sections=["PMLA Section 3", "PMLA Section 4", "IPC 420"],
    ),
    ScamTemplate(
        name="maas",
        display="Mule-as-a-Service",
        category="fraud",
        keywords=[
            "account",
            "rent",
            "bank account",
            "monthly",
            "payment",
            "kyc",
            "documents",
            "aadhaar",
            "pan card",
            "passbook",
            "provide details",
            "bulk accounts",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "UPI", "PAN"],
        severity="CRITICAL",
        reference_embedding=None,
        legal_sections=["PMLA Section 3", "PMLA Section 4", "IT Act 66D"],
    ),
    ScamTemplate(
        name="digital_arrest",
        display="Digital Arrest Scam",
        category="fraud",
        keywords=[
            "police",
            "arrest",
            "warrant",
            "case",
            "legal",
            "pay",
            "fine",
            "cybercrime",
            "narcotics",
            "parcel",
            "customs",
            "court",
            "immediate",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["IPC 419", "IPC 420", "IT Act 66C", "IT Act 66D"],
    ),
    ScamTemplate(
        name="job_fraud",
        display="Job Fraud",
        category="fraud",
        keywords=[
            "job",
            "work from home",
            "salary",
            "hiring",
            "vacancy",
            "apply",
            "registration fee",
            "earn",
            "part time",
            "data entry",
            "typing job",
            "guaranteed placement",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "UPI", "EMAIL"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["IPC 420", "IT Act 66D"],
    ),
    ScamTemplate(
        name="pump_and_dump",
        display="Pump and Dump",
        category="fraud",
        keywords=[
            "stock",
            "buy",
            "target",
            "multibagger",
            "tip",
            "profit",
            "guaranteed",
            "insider",
            "breakout",
            "100%",
            "double",
            "short term",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "TELEGRAM_HANDLE"],
        severity="CRITICAL",
        reference_embedding=None,
        legal_sections=[
            "SEBI (PFUTP) Regulations",
            "SEBI Act Section 12A",
            "IPC 420",
        ],
    ),
    ScamTemplate(
        name="fake_research_report",
        display="Fake Research Report",
        category="fraud",
        keywords=[
            "research",
            "report",
            "analyst",
            "target price",
            "buy",
            "strong buy",
            "recommendation",
            "sebi registered",
            "advisory",
            "premium",
            "tips",
        ],
        min_keyword_hits=3,
        expected_identifiers=["TELEGRAM_HANDLE", "PHONE_IN"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=[
            "SEBI (Investment Advisers) Regulations",
            "SEBI (Research Analysts) Regulations",
        ],
    ),
    ScamTemplate(
        name="drug_sale",
        display="Drug Sale",
        category="narco",
        keywords=[
            "maal",
            "stuff",
            "delivery",
            "gram",
            "pure",
            "quality",
            "available",
            "hash",
            "weed",
            "md",
            "lsd",
            "cocaine",
            "heroin",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "TELEGRAM_HANDLE", "CRYPTO_TRC20"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["NDPS Act Section 20", "NDPS Act Section 22", "NDPS Act Section 25"],
    ),
    ScamTemplate(
        name="drug_delivery_recruitment",
        display="Drug Delivery Recruitment",
        category="narco",
        keywords=[
            "delivery",
            "driver",
            "parcel",
            "pickup",
            "drop",
            "payment",
            "cash",
            "courier",
            "package",
            "transport",
            "no questions",
            "discreet",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "TELEGRAM_HANDLE"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["NDPS Act Section 25", "NDPS Act Section 29"],
    ),
    ScamTemplate(
        name="fake_sim_sale",
        display="Fake SIM Sale",
        category="fraud",
        keywords=[
            "sim",
            "sim card",
            "pre-activated",
            "bulk",
            "no kyc",
            "available",
            "whatsapp",
            "telegram",
            "ready to use",
            "anonymous",
            "unregistered",
        ],
        min_keyword_hits=3,
        expected_identifiers=["PHONE_IN", "TELEGRAM_HANDLE"],
        severity="MEDIUM",
        reference_embedding=None,
        legal_sections=["Indian Telegraph Act Section 20", "IT Act 66D"],
    ),
    ScamTemplate(
        name="crypto_cashout",
        display="Crypto Cashout",
        category="fraud",
        keywords=[
            "usdt",
            "cash",
            "convert",
            "rate",
            "exchange",
            "crypto",
            "withdraw",
            "p2p",
            "otc",
            "tether",
            "bitcoin",
            "hawala",
        ],
        min_keyword_hits=3,
        expected_identifiers=["CRYPTO_TRC20", "CRYPTO_ETH", "TELEGRAM_HANDLE", "UPI"],
        severity="HIGH",
        reference_embedding=None,
        legal_sections=["PMLA Section 3", "FEMA Section 3", "IT Act 66D"],
    ),
]
