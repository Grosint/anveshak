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
    "zh": "zho_Hans",  # Chinese Simplified
    "zh-cn": "zho_Hans",
    "zh-tw": "zho_Hant",
    "hi": "hin_Deva",  # Hindi
    "ar": "arb_Arab",  # Arabic
    "ur": "urd_Arab",  # Urdu
    "ru": "rus_Cyrl",  # Russian
    "bn": "ben_Beng",  # Bengali
    "te": "tel_Telu",  # Telugu
    "ta": "tam_Taml",  # Tamil
    "or": "ory_Orya",  # Odia
    "ml": "mal_Mlym",  # Malayalam
}

_NLLB_TGT_CODE = "eng_Latn"  # English (Latin script) — always the target

# Module-level cache — model loaded once at first use (lazy).
_pipeline = None


def _get_pipeline():
    """Lazy-load the NLLB translation pipeline."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    import torch
    from transformers import pipeline as hf_pipeline

    # Bound torch to its configured thread budget BEFORE the model is built.
    # Left unset, torch grabs os.cpu_count() threads per op and WorkerSettings
    # runs several analyse jobs at once, so every core is oversubscribed and
    # each translation gets slower the more of them are in flight.
    torch.set_num_threads(settings.torch_num_threads)
    torch.set_num_interop_threads(settings.torch_num_threads)

    log.info(
        "translation.loading_model",
        model=settings.translation_model,
        torch_threads=settings.torch_num_threads,
    )
    _pipeline = hf_pipeline(
        "translation",
        model=settings.translation_model,
        device=-1,  # -1 = CPU; override via TRANSLATION_DEVICE in future
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

    # Truncate to max chars to avoid OOM on very long articles. This is a
    # first-pass character budget only; it does NOT bound the token count, so
    # the token clamp below is what actually protects the model.
    if len(text) > settings.translation_max_chars:
        text = text[: settings.translation_max_chars]
        log.debug(
            "translation.text_truncated",
            max_chars=settings.translation_max_chars,
            lang=src_lang,
        )

    try:
        pipe = _get_pipeline()

        # Clamp on TOKENS, not characters. Dense scripts (Devanagari, Arabic,
        # CJK) tokenise to far more tokens per character than Latin, so a text
        # inside the character budget can still overrun the model's position
        # limit. Overrunning it does not raise: generation just never
        # terminates and pins the CPU indefinitely.
        tokenizer = pipe.tokenizer
        if tokenizer is None:
            # Fail closed. The clamp below is the only thing standing between a
            # dense-script input and the non-terminating generation that wedged
            # the analyst worker for 40 minutes. Translating without it is worse
            # than not translating.
            log.warning(
                "translation.no_tokenizer",
                lang=src_lang,
                model=settings.translation_model,
                reason="pipeline exposes no tokenizer, cannot clamp input tokens",
            )
            return None

        tokenizer.src_lang = nllb_src
        # transformers types __call__ as returning Encoding, which declares
        # neither __len__ nor __getitem__. At runtime it is a BatchEncoding,
        # which is a dict. The annotation is what len() and the slice below need.
        token_ids: list[int] = tokenizer(text, add_special_tokens=False)[  # pyright: ignore[reportIndexIssue, reportAssignmentType]
            "input_ids"
        ]
        if len(token_ids) > settings.translation_max_input_tokens:
            text = tokenizer.decode(
                token_ids[: settings.translation_max_input_tokens],
                skip_special_tokens=True,
            )
            log.info(
                "translation.tokens_truncated",
                lang=src_lang,
                src_tokens=len(token_ids),
                max_input_tokens=settings.translation_max_input_tokens,
            )

        result = pipe(
            text,
            src_lang=nllb_src,
            tgt_lang=_NLLB_TGT_CODE,
            truncation=True,
            max_length=settings.translation_max_tokens,
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
