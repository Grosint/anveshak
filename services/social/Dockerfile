# Anveshak Social intelligence service
# Telegram / Twitter / Instagram collectors — port 8002
# Build context: project root (../../ from compose.yml)
#
# Multi-stage build: builder (compile C extensions) → runtime (slim final image).

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

WORKDIR /workspace/services/social
COPY services/social/pyproject.toml .
COPY services/social/anveshak/ anveshak/
RUN uv pip install --system .

# ===== Stage 2: runtime — no gcc, no build artifacts =====
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + SDK source from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /workspace/sdk /workspace/sdk

# Copy service source
COPY --from=builder /workspace/services/social /workspace/services/social
WORKDIR /workspace/services/social

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak
USER anveshak

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8002/health || exit 1

CMD ["python", "-m", "anveshak.social.main"]
