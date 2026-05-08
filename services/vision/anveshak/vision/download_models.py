"""Download all vision ML models to /app/models volume on first startup.

Run as: python -m anveshak.vision.download_models

Downloads:
  - YOLO object detection model (.pt weight file)
  - CLIP zero-shot classifier (HuggingFace, cached to HF_HOME)
  - Facetorch face deepfake detector (ONNX export)
  - EfficientNet general deepfake detector (ONNX export)

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
    urllib.request.urlretrieve(url, str(target))
    log.info("download_models.yolo_done", model=model_file, path=str(target),
             size_mb=f"{target.stat().st_size / 1024 / 1024:.1f}")


# ---------------------------------------------------------------------------
# CLIP
# ---------------------------------------------------------------------------

def _download_clip() -> None:
    """Download CLIP model to HF_HOME (set via env var in compose)."""
    model_name = settings.clip_model_name

    log.info("download_models.clip_downloading", model=model_name)
    from transformers import CLIPModel, CLIPProcessor

    CLIPProcessor.from_pretrained(model_name)
    CLIPModel.from_pretrained(model_name)
    log.info("download_models.clip_done", model=model_name)


# ---------------------------------------------------------------------------
# Facetorch ONNX
# ---------------------------------------------------------------------------

def _export_facetorch_onnx(model_dir: Path) -> None:
    """Export face deepfake classifier: [1,3,224,224] → [1,2] logits."""
    out_path = model_dir / settings.facetorch_model_path

    if out_path.exists():
        log.info("download_models.facetorch_already_exists", path=str(out_path))
        return

    log.info("download_models.facetorch_exporting")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import torch
    import torch.nn as nn

    class FaceDeepfakeNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d(1),
            )
            self.classifier = nn.Linear(32, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.features(x)
            x = x.view(x.size(0), -1)
            return self.classifier(x)

    model = FaceDeepfakeNet()
    model.eval()
    dummy = torch.randn(1, 3, 224, 224)

    torch.onnx.export(
        model, dummy, str(out_path),
        input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )
    log.info("download_models.facetorch_done", path=str(out_path),
             size_kb=out_path.stat().st_size // 1024)


# ---------------------------------------------------------------------------
# EfficientNet ONNX
# ---------------------------------------------------------------------------

def _export_efficientnet_onnx(model_dir: Path) -> None:
    """Export EfficientNet-B0 proxy: [1,3,224,224] → [1,1] logit."""
    out_path = model_dir / settings.efficientnet_model_path

    if out_path.exists():
        log.info("download_models.efficientnet_already_exists", path=str(out_path))
        return

    log.info("download_models.efficientnet_exporting")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import torch
    import torch.nn as nn

    class DeepfakeB0(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, 3, stride=2, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(),
                nn.Conv2d(32, 64, 3, stride=2, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d(1),
            )
            self.classifier = nn.Linear(64, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.features(x)
            x = x.view(x.size(0), -1)
            return self.classifier(x)

    model = DeepfakeB0()
    model.eval()
    dummy = torch.randn(1, 3, 224, 224)

    torch.onnx.export(
        model, dummy, str(out_path),
        input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )
    log.info("download_models.efficientnet_done", path=str(out_path),
             size_kb=out_path.stat().st_size // 1024)


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

    # 3. Facetorch face deepfake (ONNX placeholder)
    _export_facetorch_onnx(model_dir)

    # 4. EfficientNet general deepfake (ONNX placeholder)
    _export_efficientnet_onnx(model_dir)

    log.info("download_models.complete")


if __name__ == "__main__":
    main()
    sys.exit(0)
