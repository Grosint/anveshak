# Anveshak Social intelligence service
# Telegram / Twitter / Instagram collectors — port 8002
# Build context: project root (../../ from compose.yml)

FROM python:3.12-slim AS base

# --------------------------------------------------------------------------
# System deps
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
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
# Service source + dependencies
# --------------------------------------------------------------------------
WORKDIR /workspace/services/social
COPY services/social/pyproject.toml .
COPY services/social/anveshak/ anveshak/
RUN uv pip install --system .

# --------------------------------------------------------------------------
# Non-root user
# --------------------------------------------------------------------------
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak
USER anveshak

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8002/health || exit 1

CMD ["python", "-m", "anveshak.social.main"]
