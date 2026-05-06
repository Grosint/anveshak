# Anveshak Reporter service
# PDF / DOCX intelligence report generation — port 8005
# Build context: project root (../../ from compose.yml)
#
# Multi-stage build: builder (compile C extensions) → runtime (slim + WeasyPrint).
# sentence-transformers removed — RAG embeddings are served by analyst service.
# WeasyPrint requires a suite of system libraries for PDF rendering.

# ===== Stage 1: builder — compile C extensions, install wheels =====
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml /workspace/pyproject.toml
COPY sdk/ /workspace/sdk/
RUN uv pip install --system /workspace/sdk/

WORKDIR /workspace/services/reporter
COPY services/reporter/pyproject.toml .
COPY services/reporter/anveshak/ anveshak/
RUN uv pip install --system .

# ===== Stage 2: runtime — WeasyPrint rendering stack, no build tools =====
FROM python:3.12-slim AS runtime

# Runtime system deps — WeasyPrint PDF rendering chain (unavoidable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    # WeasyPrint: Cairo + Pango + GDK-Pixbuf rendering stack
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    # Font rendering
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Runtime libs for lxml
    libxml2 \
    libxslt1.1 \
    libssl3 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Copy installed Python packages + SDK source from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /workspace/sdk /workspace/sdk

# Copy service source + templates
COPY --from=builder /workspace/services/reporter /workspace/services/reporter
WORKDIR /workspace/services/reporter
COPY services/reporter/templates/ templates/

# Output directory (volume-mounted in compose)
RUN mkdir -p /app/reports

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /app/reports
USER anveshak

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8005/health || exit 1

CMD ["python", "-m", "anveshak.reporter.main"]
