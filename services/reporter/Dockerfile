# Anveshak Reporter service
# PDF / DOCX intelligence report generation — port 8005
# Build context: project root (../../ from compose.yml)
#
# WeasyPrint requires a suite of system libraries for PDF rendering.
# The apt-get layer is large but unavoidable; it is separated for cache reuse.

FROM python:3.12-slim AS base

# --------------------------------------------------------------------------
# System deps — WeasyPrint PDF rendering chain
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    # WeasyPrint: Cairo + Pango + GDK-Pixbuf rendering stack
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Font rendering
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # libssl for WeasyPrint HTTPS fetches (embedded resources in HTML templates)
    libssl-dev \
    # python-docx needs lxml C extensions
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

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
# Dependencies
# --------------------------------------------------------------------------
WORKDIR /workspace/services/reporter
COPY services/reporter/pyproject.toml .
COPY services/reporter/anveshak/ anveshak/
RUN uv pip install --system .

# --------------------------------------------------------------------------
# Report templates
# --------------------------------------------------------------------------
COPY services/reporter/templates/ templates/

# --------------------------------------------------------------------------
# Output directory (volume-mounted in compose)
# --------------------------------------------------------------------------
RUN mkdir -p /app/reports

# --------------------------------------------------------------------------
# Non-root user
# --------------------------------------------------------------------------
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /app/reports
USER anveshak

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8005/health || exit 1

CMD ["python", "-m", "anveshak.reporter.main"]
