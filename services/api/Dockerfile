# Anveshak API service
# FastAPI application — port 8000
# Build context: project root (../../ from compose.yml)
#
# Multi-stage build: builder (compile C extensions) → runtime (slim final image).
# sentence-transformers removed — search embeddings are served by analyst service.

# ===== Stage 1: builder — compile C extensions, install wheels =====
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml /workspace/pyproject.toml
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

WORKDIR /workspace/services/api
COPY services/api/pyproject.toml .
COPY services/api/anveshak/ anveshak/
RUN uv pip install --system .

# ===== Stage 2: runtime — no gcc, no build artifacts =====
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

# Copy service source + migrations
COPY --from=builder /workspace/services/api /workspace/services/api
WORKDIR /workspace/services/api
COPY services/api/migrations/ migrations/
COPY services/api/alembic.ini alembic.ini

# Geocoder custom locations (Indian states, defence locations, localities)
COPY infra/configs/geocoder/custom_locations.json /workspace/infra/configs/geocoder/custom_locations.json

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak
USER anveshak

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "anveshak.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]
