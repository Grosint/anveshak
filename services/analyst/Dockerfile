# Anveshak Analyst service
# NER, entity resolution, embedding, LLM-backed reasoning — port 8004
# Build context: project root (../../ from compose.yml)

FROM python:3.12-slim AS base

# --------------------------------------------------------------------------
# System deps
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------
# uv
# --------------------------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------
# Workspace setup — install SDK first, then service
# --------------------------------------------------------------------------
COPY pyproject.toml /workspace/pyproject.toml
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

# --------------------------------------------------------------------------
# Dependencies (spaCy + transformers — heavy layer, cache aggressively)
# --------------------------------------------------------------------------
WORKDIR /workspace/services/analyst
COPY services/analyst/pyproject.toml .
COPY services/analyst/anveshak/ anveshak/
RUN uv pip install --system .

# --------------------------------------------------------------------------
# Download spaCy models at build time so the container is self-contained.
# All three language models are required for multilingual NER (en/ru/zh).
# Override individual models via build args for GPU upgrades — see hardware.md.
# --------------------------------------------------------------------------
ARG SPACY_EN_MODEL=en_core_web_md
ARG SPACY_RU_MODEL=ru_core_news_md
ARG SPACY_ZH_MODEL=zh_core_web_md
RUN python -m spacy download ${SPACY_EN_MODEL} \
 && python -m spacy download ${SPACY_RU_MODEL} \
 && python -m spacy download ${SPACY_ZH_MODEL}

# --------------------------------------------------------------------------
# Pre-download sentence-transformers + NLLB translation model at build time.
# HF_HOME is set to /app/models so the non-root user can read it.
# NLLB-200 (~2.4GB) translates zh/hi/ar/ur → English before NLP/embedding.
# Upgrade: set TRANSLATION_MODEL=facebook/nllb-200-1.3B on GPU hardware.
# --------------------------------------------------------------------------
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG TRANSLATION_MODEL=facebook/nllb-200-distilled-600M
ENV HF_HOME=/app/models
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"
RUN python -c "from transformers import pipeline; pipeline('translation', model='${TRANSLATION_MODEL}', device=-1)"

# --------------------------------------------------------------------------
# Non-root user
# --------------------------------------------------------------------------
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /app/models
USER anveshak

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8004/health || exit 1

CMD ["python", "-m", "anveshak.analyst.main"]
