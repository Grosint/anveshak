"""Content quality gate — filters boilerplate/nav text before embedding.

Prevents junk content from entering the embedding → clustering → signal
pipeline, which avoids false-positive signals from navigation menus,
cookie banners, and repetitive boilerplate.

Every check here is script-neutral. The length gate counts words rather than
characters, because a character floor is a volume proxy that only holds for
Latin script and silently rejected compact Hindi that an English equivalent
cleared. The word counter lives in anveshak.text, shared with the scraper's
gate so the two cannot drift apart.

All thresholds are configurable via environment variables (see settings.py).
"""

from __future__ import annotations

import string

import structlog
from anveshak.text import extract_words

from .settings import settings

log = structlog.get_logger(__name__)

_PUNCTUATION_SET = set(string.punctuation + "·|—–»«►▸›‹•")


def is_quality_content(text: str) -> tuple[bool, str]:
    """Return (passed, gate) indicating whether text passes quality checks.

    passed: True if content is good for embedding, False if rejected.
    gate: which check determined the outcome - 'too_short', 'unique_ratio',
          'punctuation', or 'passed'.

    Checks:
      1. Minimum word count (default 8) - one gate on volume, not two
      2. Unique word ratio — catches repeated nav menus
      3. Punctuation ratio — catches link-heavy / separator-heavy text
    """
    stripped = text.strip()

    # Check 1: minimum content volume, measured in words so that every script
    # is held to the same standard.
    words = extract_words(stripped)
    # Wordless input is rejected structurally, not via the configurable floor,
    # so that CONTENT_MIN_WORDS=0 degrades the gate rather than raising
    # ZeroDivisionError on the ratios below and failing the whole ARQ job.
    if not words:
        return (False, "too_short")
    if len(words) < settings.content_min_words:
        return (False, "too_short")

    # Check 2: unique word ratio (catches "Business Tech Lifestyle Business Tech Lifestyle...")
    unique_ratio = len(set(words)) / len(words)
    if unique_ratio < settings.content_min_unique_word_ratio:
        return (False, "unique_ratio")

    # Check 3: punctuation / symbol ratio
    punct_count = sum(1 for c in stripped if c in _PUNCTUATION_SET)
    punct_ratio = punct_count / len(stripped)
    if punct_ratio > settings.content_max_punctuation_ratio:
        return (False, "punctuation")

    return (True, "passed")
