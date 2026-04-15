# Anveshak Scraper service
# Headless browser web collection — port 8001
# Build context: project root (../../ from compose.yml)

FROM python:3.12-slim AS base

# --------------------------------------------------------------------------
# System deps — Playwright requires a full browser dependency chain
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    # Playwright / Chromium system libraries
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------
# uv
# --------------------------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# --------------------------------------------------------------------------
# Workspace setup — install SDK first, then service
# --------------------------------------------------------------------------
COPY pyproject.toml /workspace/pyproject.toml
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

# --------------------------------------------------------------------------
# Service source + dependencies
# --------------------------------------------------------------------------
WORKDIR /workspace/services/scraper
COPY services/scraper/pyproject.toml .
COPY services/scraper/anveshak/ anveshak/
RUN uv pip install --system .

# --------------------------------------------------------------------------
# Install Chromium browser (pinned via Playwright version)
# --------------------------------------------------------------------------
RUN python -m playwright install chromium --with-deps

# --------------------------------------------------------------------------
# Non-root user
# --------------------------------------------------------------------------
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /ms-playwright 2>/dev/null || true
USER anveshak

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -sf http://localhost:8001/health || exit 1

CMD ["python", "-m", "anveshak.scraper.main"]
