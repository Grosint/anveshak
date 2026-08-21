"""Download all vision ML models to /app/models volume on first startup.

Run as: python -m anveshak.vision.download_models

Downloads:
  - YOLO object detection model (.pt weight file)
  - CLIP zero-shot classifier (HuggingFace, cached to HF_HOME)
  - Facetorch face deepfake detector (real HF model → ONNX export)
  - EfficientNet general deepfake detector (real HF model → ONNX export)

Idempotent — skips downloads if models already exist.
Used by the vision-init container in compose.yml.
"""

from __future__ import annotations

import sys
from pathlib import Path

import structlog

from .settings import settings

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# YOLO
# ---------------------------------------------------------------------------


def _download_yolo(model_dir: Path) -> None:
    """Download YOLO .pt weight file to model_dir/yolo/.

    Downloads directly from GitHub releases to avoid importing ultralytics
    (which pulls in torchvision and causes version conflicts in init containers).
    """
    import urllib.request

    model_file = settings.yolo_model_file()
    target = model_dir / "yolo" / model_file

    if target.exists():
        log.info("download_models.yolo_already_exists", model=model_file, path=str(target))
        return

    log.info("download_models.yolo_downloading", model=model_file)
    target.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://github.com/ultralytics/assets/releases/download/v8.2.0/{model_file}"
    # scheme and host are the literal https://github.com prefix above
    urllib.request.urlretrieve(url, str(target))  # nosec B310
    log.info(
        "download_models.yolo_done",
        model=model_file,
        path=str(target),
        size_mb=f"{target.stat().st_size / 1024 / 1024:.1f}",
    )


# ---------------------------------------------------------------------------
# CLIP
# ---------------------------------------------------------------------------


def _download_clip() -> None:
    """Download CLIP model to HF_HOME (set via env var in compose)."""
    model_name = settings.clip_model_name

    log.info("download_models.clip_downloading", model=model_name)
    from transformers import CLIPModel, CLIPProcessor

    # sovereign deployment; init container pre-caches models, no runtime HuggingFace download in production
    CLIPProcessor.from_pretrained(model_name)  # nosec B615
    # sovereign deployment; init container pre-caches models, no runtime HuggingFace download in production
    CLIPModel.from_pretrained(model_name)  # nosec B615
    log.info("download_models.clip_done", model=model_name)


# ---------------------------------------------------------------------------
# Facetorch ONNX — real HuggingFace model
# ---------------------------------------------------------------------------


def _download_facetorch_onnx(model_dir: Path) -> None:
    """Download face deepfake model from HuggingFace and export to ONNX.

    Model: settings.facetorch_hf_model (default: prithivMLmods/Deep-Fake-Detector-v2-Model)
    Output: [1, 2] logits (real vs fake) — softmax → index FAKE_INDEX = fake prob
    """
    out_path = model_dir / settings.facetorch_model_path

    if out_path.exists():
        log.info("download_models.facetorch_already_exists", path=str(out_path))
        return

    hf_model = settings.facetorch_hf_model
    log.info("download_models.facetorch_downloading", hf_model=hf_model)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # optimum is a container-only dependency, absent from the host venv.
    from optimum.onnxruntime import (  # pyright: ignore[reportMissingImports]
        ORTModelForImageClassification,
    )

    try:
        ort_model = ORTModelForImageClassification.from_pretrained(
            hf_model,
            export=True,
        )
        ort_model.save_pretrained(str(out_path.parent))

        # optimum saves as model.onnx — rename to match settings path
        exported = out_path.parent / "model.onnx"
        if exported.exists() and exported != out_path:
            exported.rename(out_path)
    except Exception:
        # Remove partial file so idempotent check doesn't skip on next run
        if out_path.exists():
            out_path.unlink()
        raise

    log.info(
        "download_models.facetorch_done",
        hf_model=hf_model,
        path=str(out_path),
        size_mb=f"{out_path.stat().st_size / 1024 / 1024:.1f}",
    )


# ---------------------------------------------------------------------------
# EfficientNet ONNX — real HuggingFace model
# ---------------------------------------------------------------------------


def _download_efficientnet_onnx(model_dir: Path) -> None:
    """Download non-face deepfake model from HuggingFace and export to ONNX.

    Model: settings.efficientnet_hf_model (default: umm-maybe/AI-image-detector)
    Output: [1, 2] logits (real vs fake) — softmax → index FAKE_INDEX = fake prob
    """
    out_path = model_dir / settings.efficientnet_model_path

    if out_path.exists():
        log.info("download_models.efficientnet_already_exists", path=str(out_path))
        return

    hf_model = settings.efficientnet_hf_model
    log.info("download_models.efficientnet_downloading", hf_model=hf_model)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # optimum is a container-only dependency, absent from the host venv.
    from optimum.onnxruntime import (  # pyright: ignore[reportMissingImports]
        ORTModelForImageClassification,
    )

    try:
        ort_model = ORTModelForImageClassification.from_pretrained(
            hf_model,
            export=True,
        )
        ort_model.save_pretrained(str(out_path.parent))

        # optimum saves as model.onnx — rename to match settings path
        exported = out_path.parent / "model.onnx"
        if exported.exists() and exported != out_path:
            exported.rename(out_path)
    except Exception:
        # Remove partial file so idempotent check doesn't skip on next run
        if out_path.exists():
            out_path.unlink()
        raise

    log.info(
        "download_models.efficientnet_done",
        hf_model=hf_model,
        path=str(out_path),
        size_mb=f"{out_path.stat().st_size / 1024 / 1024:.1f}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    model_dir = settings.model_dir
    log.info("download_models.start", model_dir=str(model_dir))

    # 1. YOLO object detection
    _download_yolo(model_dir)

    # 2. CLIP zero-shot classification
    _download_clip()

    # 3. Facetorch face deepfake (real HF model → ONNX)
    _download_facetorch_onnx(model_dir)

    # 4. EfficientNet general deepfake (real HF model → ONNX)
    _download_efficientnet_onnx(model_dir)

    log.info("download_models.complete")


if __name__ == "__main__":
    main()
    sys.exit(0)
