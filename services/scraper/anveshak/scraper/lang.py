"""Language detection for scraper — lightweight wrapper around langdetect.

Same algorithm as analyst/nlp.py:detect_language() but without spaCy dependency.
langdetect is already a scraper dependency (pyproject.toml).
"""
from __future__ import annotations

import re

import structlog

log = structlog.get_logger(__name__)

_MIN_LANGDETECT_LEN = 30
_RE_URL = re.compile(r"https?://\S+")


def detect_language(text: str) -> str:
    """Detect language of text. Returns ISO 639-1 code.

    Returns 'en' for short texts or on detection failure.
    """
    cleaned = _RE_URL.sub("", text)
    if len(cleaned.strip()) < _MIN_LANGDETECT_LEN:
        return "en"
    try:
        from langdetect import detect
        lang = detect(cleaned)
    except Exception:
        return "en"

    if lang.startswith("zh"):
        lang = "zh"

    return lang
