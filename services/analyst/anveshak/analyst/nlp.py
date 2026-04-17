"""spaCy NLP pipeline — language detection, NER, entity parsing (criteria 1.11–1.14, 1.17).

Models are loaded ONCE via load_models() at service startup, not per-request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# Module-level model registry — populated by load_models() at startup (criteria 1.17).
_MODELS: dict[str, "spacy.Language"] = {}  # noqa: F821

# Texts shorter than this are too ambiguous for langdetect — default to 'en'.
_MIN_LANGDETECT_LEN = 30


def load_models() -> None:
    """Load all configured spaCy models. Must be called ONCE at service startup."""
    import spacy

    global _MODELS
    for lang, model_name in [
        ("en", settings.spacy_en_model),
        ("ru", settings.spacy_ru_model),
        ("zh", settings.spacy_zh_model),
    ]:
        try:
            _MODELS[lang] = spacy.load(model_name)
            log.info("nlp.model_loaded", lang=lang, model=model_name)
        except OSError as exc:
            log.error("nlp.model_load_failed", lang=lang, model=model_name, error=str(exc))


import re

_RE_URL = re.compile(r"https?://\S+")
_RE_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_RE_MARKDOWN_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _strip_noise(text: str) -> str:
    """Remove URLs and markdown syntax that confuse language detection."""
    text = _RE_MARKDOWN_IMG.sub("", text)
    text = _RE_MARKDOWN_LINK.sub(r"\1", text)
    text = _RE_URL.sub("", text)
    return text


def detect_language(text: str) -> str:
    """Detect language of text. Returns ISO 639-1 code.

    Criteria 1.12: routes to en/ru/zh.
    Criteria 1.13: unknown language (not in loaded models) → 'en' fallback + warning.
    """
    cleaned = _strip_noise(text)
    if len(cleaned.strip()) < _MIN_LANGDETECT_LEN:
        return "en"
    try:
        from langdetect import detect, LangDetectException
        lang = detect(cleaned)
    except Exception:
        return "en"

    # Normalise zh-cn/zh-tw to zh
    if lang.startswith("zh"):
        lang = "zh"

    if lang not in _MODELS:
        log.warning("nlp.unsupported_language", detected=lang, fallback="en")
        return "en"
    return lang


def _get_nlp(lang: str):
    """Return spaCy model for language, falling back to English."""
    if lang not in _MODELS:
        return _MODELS.get("en")
    return _MODELS[lang]


@dataclass
class EntityDTO:
    """Lightweight DTO for NER output — no DB dependency."""
    entity_type: str    # PERSON | ORG | LOCATION | FACILITY | DATE | EVENT | …
    entity_text: str
    confidence: float   # spaCy v3 doesn't expose per-span confidence; always 1.0
    language: str


def parse_entities(text: str, lang: str) -> list[EntityDTO]:
    """Run spaCy NER on text and return extracted entities (criteria 1.14, 1.32).

    Pure function — no DB, no I/O. Safe to unit-test without infrastructure.
    """
    nlp = _get_nlp(lang)
    if nlp is None:
        log.error("nlp.no_model_available", lang=lang)
        return []
    doc = nlp(text)
    return [
        EntityDTO(
            entity_type=ent.label_,
            entity_text=ent.text,
            confidence=1.0,
            language=lang,
        )
        for ent in doc.ents
    ]
