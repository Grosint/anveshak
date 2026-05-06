"""Download ML models to HF_HOME volume on first startup.

Run as: python -m anveshak.analyst.download_models

Downloads:
  - sentence-transformers embedding model (~22 MB)
  - NLLB translation model (~2.4 GB)

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

    # 1. Sentence-transformers embedding model
    log.info("download_models.embedding", model=settings.embedding_model)
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.embedding_model)
    log.info("download_models.embedding_done")

    # 2. NLLB translation model (only if translation is enabled)
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
