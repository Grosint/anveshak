# Anveshak Vision service
# Image/video analysis: YOLO, CLIP, deepfake detection, EXIF, pHash — port 8003
# Build context: project root (../../ from compose.yml)
#
# Multi-stage build: builder (compile C extensions + torch) → runtime (slim).
# ML models (YOLO, CLIP, deepfake ONNX) are downloaded by the vision-init
# container into the vision_models volume — NOT baked into the image.
# GPU usage: pass VISION_DEVICE=cuda via environment (compose.vision.yml).
# The image itself is CUDA-agnostic; onnxruntime selects the provider at runtime.

# ===== Stage 1: builder — compile C extensions, install torch + wheels =====
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

WORKDIR /workspace/services/vision
COPY services/vision/pyproject.toml .
COPY services/vision/anveshak/ anveshak/
# Install torch + torchvision CPU-only FIRST so uv doesn't pull CUDA wheels.
# onnxscript is needed for ONNX model export in vision-init.
RUN uv pip install --system \
        torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install --system . onnxscript

# ===== Stage 2: runtime — OpenCV + ffmpeg, no build tools =====
FROM python:3.12-slim AS runtime

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    # OpenCV runtime
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    # ffmpeg — video keyframe extraction
    ffmpeg \
    # libmagic for file-type detection
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + SDK source from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /workspace/sdk /workspace/sdk

# Copy service source
COPY --from=builder /workspace/services/vision /workspace/services/vision
WORKDIR /workspace/services/vision

# Model directories — all ML models are downloaded by vision-init container
# into the vision_models volume. These dirs ensure mount points exist.
RUN mkdir -p /app/models/yolo \
             /app/models/facetorch \
             /app/models/efficientnet \
             /app/media

VOLUME ["/app/models", "/app/media"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /app/models /app/media
USER anveshak

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -sf http://localhost:8003/health || exit 1

CMD ["python", "-m", "anveshak.vision.main"]
