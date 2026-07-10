# Anveshak Analyst service
# NER, entity resolution, embedding, LLM-backed reasoning — port 8004
# Build context: project root (../../ from compose.yml)
#
# Multi-stage build: builder (compile C extensions) → runtime (slim final image).
# spaCy NLP models are baked into the image at build time.
# Large ML models (NLLB, sentence-transformers) are downloaded at first startup
# into the analyst_models volume via analyst-init container.

# ===== Stage 1: builder — compile C extensions, install wheels =====
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml /workspace/pyproject.toml
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

WORKDIR /workspace/services/analyst
COPY services/analyst/pyproject.toml .
COPY services/analyst/anveshak/ anveshak/
RUN uv pip install --system .

# spaCy NLP models — installed at build time into site-packages.
# Model names are configurable via env vars at runtime (settings.py),
# but defaults are baked in here. See hardware.md for upgrade path.
ARG SPACY_EN_MODEL=en_core_web_md
RUN python -m spacy download ${SPACY_EN_MODEL}

# ===== Stage 2: runtime — no gcc/g++, no build artifacts =====
FROM python:3.12-slim AS runtime

# Runtime-only system deps (libpq for asyncpg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + SDK source from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /workspace/sdk /workspace/sdk

# Copy service source
COPY --from=builder /workspace/services/analyst /workspace/services/analyst

# Geocoder custom locations overlay (shared with reporter service)
COPY infra/configs/geocoder/custom_locations.json /workspace/infra/configs/geocoder/custom_locations.json

WORKDIR /workspace/services/analyst

# Non-root user — created BEFORE model dir so ownership is set in one layer
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && mkdir -p /app/models \
    && chown -R anveshak:anveshak /app/models

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/models

USER anveshak

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8004/health || exit 1

CMD ["python", "-m", "anveshak.analyst.main"]
