"""NLLB-200 translation module — sovereign, offline, CPU-capable.

Translates non-English article text to English before NLP/embedding.
This ensures:
  - pgvector cosine similarity works in a single English semantic space
  - extracted entities are in English (readable by IAF analysts)
  - LLM prompts always receive English context regardless of source language

Supported source languages (currently active):
  zh  → Chinese (Simplified)  — zho_Hans
  hi  → Hindi                 — hin_Deva
  ar  → Arabic                — arb_Arab
  ur  → Urdu                  — urd_Arab
  ru  → Russian               — rus_Cyrl
  bn  → Bengali               — ben_Beng
  te  → Telugu                — tel_Telu
  ta  → Tamil                 — tam_Taml
  or  → Odia                  — ory_Orya
  ml  → Malayalam             — mal_Mlym

Model: facebook/nllb-200-distilled-600M (~2.4GB, CPU-capable)
GPU upgrade: facebook/nllb-200-1.3B or facebook/nllb-200-3.3B — see hardware.md
"""
from __future__ import annotations

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# NLLB-200 language codes for supported source languages.
# Keys are ISO 639-1 codes (from langdetect); values are NLLB flores-200 codes.
_NLLB_SRC_CODES: dict[str, str] = {
    "zh": "zho_Hans",   # Chinese Simplified
    "zh-cn": "zho_Hans",
    "zh-tw": "zho_Hant",
    "hi": "hin_Deva",   # Hindi
    "ar": "arb_Arab",   # Arabic
    "ur": "urd_Arab",   # Urdu
    "ru": "rus_Cyrl",   # Russian
    "bn": "ben_Beng",   # Bengali
    "te": "tel_Telu",   # Telugu
    "ta": "tam_Taml",   # Tamil
    "or": "ory_Orya",   # Odia
    "ml": "mal_Mlym",   # Malayalam
}

_NLLB_TGT_CODE = "eng_Latn"   # English (Latin script) — always the target

# Module-level cache — model loaded once at first use (lazy).
_pipeline = None


def _get_pipeline():
    """Lazy-load the NLLB translation pipeline."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from transformers import pipeline as hf_pipeline

    log.info(
        "translation.loading_model",
        model=settings.translation_model,
    )
    _pipeline = hf_pipeline(
        "translation",
        model=settings.translation_model,
        device=-1,                  # -1 = CPU; override via TRANSLATION_DEVICE in future
        max_length=settings.translation_max_tokens,
    )
    log.info("translation.model_loaded", model=settings.translation_model)
    return _pipeline


def needs_translation(lang: str) -> bool:
    """Return True if this language code requires translation to English."""
    return lang in _NLLB_SRC_CODES


def translate_to_english(text: str, src_lang: str) -> str | None:
    """Translate text from src_lang to English.

    Returns the translated string, or None if translation fails.
    Caller should fall back to clean_text on None.

    Args:
        text:     Source text (any supported language).
        src_lang: ISO 639-1 code from langdetect (e.g. "zh", "hi").

    Returns:
        English translation string, or None on failure.
    """
    nllb_src = _NLLB_SRC_CODES.get(src_lang)
    if nllb_src is None:
        log.warning(
            "translation.unsupported_language",
            lang=src_lang,
            fallback="skip_translation",
        )
        return None

    # Truncate to max chars to avoid OOM on very long articles.
    if len(text) > settings.translation_max_chars:
        text = text[: settings.translation_max_chars]
        log.debug(
            "translation.text_truncated",
            max_chars=settings.translation_max_chars,
            lang=src_lang,
        )

    try:
        pipe = _get_pipeline()
        result = pipe(
            text,
            src_lang=nllb_src,
            tgt_lang=_NLLB_TGT_CODE,
        )
        translated: str = result[0]["translation_text"]
        log.info(
            "translation.success",
            src_lang=src_lang,
            src_chars=len(text),
            tgt_chars=len(translated),
            model=settings.translation_model,
        )
        return translated

    except Exception as exc:
        log.error(
            "translation.failed",
            lang=src_lang,
            model=settings.translation_model,
            error=str(exc)[:200],
        )
        return None
