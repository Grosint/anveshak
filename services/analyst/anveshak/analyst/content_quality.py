"""Content quality gate — filters boilerplate/nav text before embedding.

Prevents junk content from entering the embedding → clustering → signal
pipeline, which avoids false-positive signals from navigation menus,
cookie banners, and repetitive boilerplate.

All thresholds are configurable via environment variables (see settings.py).
"""
from __future__ import annotations

import re
import string

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

_PUNCTUATION_SET = set(string.punctuation + "·|—–»«►▸›‹•")


def is_quality_content(text: str) -> bool:
    """Return True if text passes quality checks for embedding.

    Checks:
      1. Minimum length (default 100 chars)
      2. Unique word ratio — catches repeated nav menus
      3. Punctuation ratio — catches link-heavy / separator-heavy text
    """
    stripped = text.strip()

    # Check 1: minimum length
    if len(stripped) < settings.content_min_length:
        return False

    # Check 2: unique word ratio (catches "Business Tech Lifestyle Business Tech Lifestyle...")
    # CJK characters are single-char words; Latin/Cyrillic/Arabic/Devanagari require 2+ chars
    words = re.findall(
        r"[a-zA-Z\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]{2,}|[\u4e00-\u9fff\u3400-\u4dbf]",
        stripped.lower(),
    )
    if len(words) < 5:
        return False
    unique_ratio = len(set(words)) / len(words)
    if unique_ratio < settings.content_min_unique_word_ratio:
        return False

    # Check 3: punctuation / symbol ratio
    punct_count = sum(1 for c in stripped if c in _PUNCTUATION_SET)
    punct_ratio = punct_count / len(stripped)
    if punct_ratio > settings.content_max_punctuation_ratio:
        return False

    return True
