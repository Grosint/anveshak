# Anveshak Vision service
# Image/video analysis: YOLO, CLIP, deepfake detection, EXIF, pHash — port 8003
# Build context: project root (../../ from compose.yml)
#
# GPU usage: pass VISION_DEVICE=cuda via environment (compose.vision.yml)
# The image itself is CUDA-agnostic; onnxruntime selects the provider at runtime.

FROM python:3.12-slim AS base

# --------------------------------------------------------------------------
# System deps
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    # OpenCV runtime
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    # ffmpeg — video keyframe extraction (criteria 4.20)
    ffmpeg \
    # libmagic for file-type detection
    libmagic1 \
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
# Dependencies (heavy — torch, transformers, ultralytics, onnxruntime)
# Separate layer to maximise cache reuse.
# --------------------------------------------------------------------------
WORKDIR /workspace/services/vision
COPY services/vision/pyproject.toml .
COPY services/vision/anveshak/ anveshak/
# Install torch CPU-only FIRST so uv doesn't pull CUDA wheels (nvidia-cudnn-cu13).
# On GPU machines, override via VISION_DEVICE=cuda and swap to onnxruntime-gpu at runtime —
# no image rebuild needed since onnxruntime selects the EP at import time.
RUN uv pip install --system \
        torch \
        --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install --system .

# --------------------------------------------------------------------------
# Pre-download YOLO nano model (avoids runtime internet access)
# Model stored at /app/models/yolo/yolov8n.pt
# Change YOLO_MODEL_SIZE env var to use a different size — no code change.
# --------------------------------------------------------------------------
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    && mkdir -p /app/models/yolo \
    && mv /root/.config/Ultralytics/yolov8n.pt /app/models/yolo/ 2>/dev/null || true

# --------------------------------------------------------------------------
# Model directories
# facetorch/efficientnet ONNX models are volume-mounted (too large for image)
# --------------------------------------------------------------------------
RUN mkdir -p /app/models/facetorch \
             /app/models/efficientnet \
             /app/media

VOLUME ["/app/models", "/app/media"]

# --------------------------------------------------------------------------
# Non-root user
# --------------------------------------------------------------------------
RUN addgroup --system anveshak && adduser --system --ingroup anveshak anveshak \
    && chown -R anveshak:anveshak /app/models /app/media
USER anveshak

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -sf http://localhost:8003/health || exit 1

CMD ["python", "-m", "anveshak.vision.main"]
