"""Download ML models to HF_HOME volume on first startup.

Run as: python -m anveshak.analyst.download_models

Downloads:
  - sentence-transformers embedding model (~22 MB)
  - NLLB translation model (~2.4 GB)

Verifies:
  - spaCy English model (baked into image via Dockerfile)

Skips downloads if models are already present in HF_HOME.
Used by the analyst-init container in compose.yml.
"""

from __future__ import annotations

import sys

import structlog

from .settings import settings

log = structlog.get_logger(__name__)


def main() -> None:
    log.info("download_models.start", hf_home=settings.embedding_model)

    # 1. spaCy NLP models — baked into image via Dockerfile.
    #    Verify they're loadable and log status.
    import spacy

    try:
        spacy.load(settings.spacy_en_model)
        log.info("download_models.spacy_ok", model=settings.spacy_en_model)
    except OSError:
        log.error(
            "download_models.spacy_missing",
            model=settings.spacy_en_model,
            hint="Model should be baked into image via Dockerfile ARG",
        )

    # 2. Sentence-transformers embedding model
    log.info("download_models.embedding", model=settings.embedding_model)
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.embedding_model)
    log.info("download_models.embedding_done")

    # 3. NLLB translation model (only if translation is enabled)
    if settings.translation_enabled:
        log.info("download_models.translation", model=settings.translation_model)
        from transformers import pipeline

        pipeline("translation", model=settings.translation_model, device=-1)
        log.info("download_models.translation_done")
    else:
        log.info("download_models.translation_skipped", reason="disabled")

    log.info("download_models.complete")


if __name__ == "__main__":
    main()
    sys.exit(0)
