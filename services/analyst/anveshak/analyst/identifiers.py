"""Engine C — Identifier Extraction (Step 1).

Extract actionable identifiers from content text using regex + context validation.
Called from analyse_content ARQ job AFTER spaCy NER. Works on clean_text
(post-translation English).

Pure functions — no DB, no I/O. Safe to unit-test without infrastructure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentifierMatch:
    """Single extracted identifier."""

    identifier_type: str
    raw_value: str
    normalized_value: str
    confidence: float


# ---------------------------------------------------------------------------
# UPI bank suffixes (used to distinguish UPI from EMAIL)
# ---------------------------------------------------------------------------

UPI_BANK_SUFFIXES = frozenset({
    "ybl", "paytm", "okaxis", "oksbi", "ibl", "upi", "axl",
    "icici", "apl", "barodampay", "okhdfcbank", "okicici",
    "jupiteraxis", "freecharge", "phonepe", "gpay", "postbank",
    "sbi", "kotak", "indus", "federal",
})

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# PHONE_IN: Indian mobile — +91/0 prefix optional, digits 6-9 start, 10 digits
# Allow spaces, dashes, dots between digit groups
_RE_PHONE_IN = re.compile(
    r"""
    (?<!\d)                       # not preceded by digit
    (?:\+91[\s.-]?|0)?            # optional +91 or 0 prefix
    ([6-9]\d[\s.-]?\d{3}[\s.-]?\d{4,5})  # 10 digits with optional separators
    (?!\d)                        # not followed by digit
    """,
    re.VERBOSE,
)

# UPI: user@bank where bank is a known UPI suffix
_RE_UPI = re.compile(
    r"([a-zA-Z0-9._-]+@(?:" + "|".join(UPI_BANK_SUFFIXES) + r"))\b",
    re.IGNORECASE,
)

# EMAIL: standard email with TLD (min 2 chars after last dot)
_RE_EMAIL = re.compile(
    r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b",
)

# CRYPTO_BTC: Legacy (1/3) or bech32 (bc1) addresses
_RE_CRYPTO_BTC = re.compile(
    r"\b((?:bc1)[a-zA-HJ-NP-Za-km-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"
)

# CRYPTO_ETH: 0x + exactly 40 hex chars
_RE_CRYPTO_ETH = re.compile(
    r"\b(0x[a-fA-F0-9]{40})\b"
)

# CRYPTO_TRC20: T + exactly 33 alphanumeric chars
_RE_CRYPTO_TRC20 = re.compile(
    r"\b(T[a-zA-Z0-9]{33})\b"
)

# SOCIAL HANDLES: @letter followed by 4-31 more alphanumeric/underscore chars
_RE_SOCIAL_HANDLE = re.compile(
    r"(?<!\w)@([a-zA-Z][a-zA-Z0-9_]{4,31})(?!\w)"
)

# Phone context words — boost confidence when near phone number
_PHONE_CONTEXT_WORDS = frozenset({
    "call", "whatsapp", "phone", "mobile", "contact", "dial", "reach",
    "sms", "text", "msg", "telegram", "signal", "number", "helpline",
})


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_phone(raw: str) -> str:
    """Strip to 10 digits."""
    digits = re.sub(r"\D", "", raw)
    # If starts with 91 and has 12 digits, strip country code
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    # If starts with 0 and has 11 digits, strip trunk prefix
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def _has_phone_context(text: str, match_start: int, window: int = 60) -> bool:
    """Check if phone number is near context words."""
    start = max(0, match_start - window)
    end = min(len(text), match_start + window)
    snippet = text[start:end].lower()
    return any(w in snippet for w in _PHONE_CONTEXT_WORDS)


def _has_prefix(text: str, match_start: int) -> bool:
    """Check if phone match is preceded by +91 or standalone 0 trunk prefix."""
    prefix_region = text[max(0, match_start - 5):match_start].strip()
    if "+91" in prefix_region:
        return True
    # Standalone 0 trunk prefix: "0" preceded by non-digit or start of region
    if prefix_region.endswith("0"):
        before_zero = prefix_region[:-1].rstrip()
        return not before_zero or not before_zero[-1].isdigit()
    return False


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_identifiers(text: str, platform: str = "") -> list[IdentifierMatch]:
    """Extract actionable identifiers from text.

    Args:
        text: Clean text (post-translation English).
        platform: Source platform hint (e.g. "telegram", "instagram").
            Used for handle disambiguation and confidence adjustment.

    Returns:
        List of IdentifierMatch, deduplicated by (type, normalized_value).
    """
    if not text or not text.strip():
        return []

    results: list[IdentifierMatch] = []
    seen: set[tuple[str, str]] = set()  # (type, normalized_value)

    def _add(id_type: str, raw: str, normalized: str, confidence: float) -> None:
        key = (id_type, normalized)
        if key not in seen:
            seen.add(key)
            results.append(IdentifierMatch(
                identifier_type=id_type,
                raw_value=raw,
                normalized_value=normalized,
                confidence=confidence,
            ))

    # --- UPI (before EMAIL to mark UPI domains) ---
    upi_normalized: set[str] = set()
    for m in _RE_UPI.finditer(text):
        raw = m.group(1)
        norm = raw.lower()
        upi_normalized.add(norm)
        _add("UPI", raw, norm, 1.0)

    # --- EMAIL (exclude UPI matches) ---
    for m in _RE_EMAIL.finditer(text):
        raw = m.group(1)
        norm = raw.lower()
        # Skip if this is a UPI ID
        if norm in upi_normalized:
            continue
        # Also check if the domain part is a UPI bank suffix
        domain = norm.split("@", 1)[1] if "@" in norm else ""
        if domain in UPI_BANK_SUFFIXES:
            continue
        _add("EMAIL", raw, norm, 1.0)

    # --- PHONE_IN ---
    for m in _RE_PHONE_IN.finditer(text):
        raw = m.group(0)
        digits = _normalize_phone(raw)
        if len(digits) != 10:
            continue
        if digits[0] not in "6789":
            continue
        # Confidence based on context
        has_prefix = _has_prefix(text, m.start())
        has_context = _has_phone_context(text, m.start())
        if has_prefix:
            confidence = 0.95
        elif has_context:
            confidence = 0.85
        else:
            confidence = 0.6
        _add("PHONE_IN", raw, digits, confidence)

    # --- CRYPTO_BTC ---
    for m in _RE_CRYPTO_BTC.finditer(text):
        raw = m.group(1)
        _add("CRYPTO_BTC", raw, raw, 1.0)  # preserve case

    # --- CRYPTO_ETH ---
    for m in _RE_CRYPTO_ETH.finditer(text):
        raw = m.group(1)
        _add("CRYPTO_ETH", raw, raw.lower(), 1.0)

    # --- CRYPTO_TRC20 ---
    for m in _RE_CRYPTO_TRC20.finditer(text):
        raw = m.group(1)
        _add("CRYPTO_TRC20", raw, raw, 0.9)  # preserve case

    # --- SOCIAL HANDLES (@username) ---
    platform_lower = platform.lower() if platform else ""
    for m in _RE_SOCIAL_HANDLE.finditer(text):
        raw_handle = m.group(1)
        norm = raw_handle.lower()

        if platform_lower == "instagram":
            confidence = 0.9
            _add("INSTAGRAM_HANDLE", f"@{raw_handle}", norm, confidence)
        else:
            confidence = 0.9 if platform_lower == "telegram" else 0.7
            _add("TELEGRAM_HANDLE", f"@{raw_handle}", norm, confidence)

    return results
