"""Download / export ONNX deepfake detection models into /app/models.

Models:
  - facetorch/face_deepfake.onnx  — real HF model (prithivMLmods/Deep-Fake-Detector-v2-Model)
  - efficientnet/deepfake_b0.onnx — real HF model (umm-maybe/AI-image-detector)

Usage:
  python scripts/download_models.py [--model-dir /app/models]

Downloads real pre-trained weights from HuggingFace and exports to ONNX.
Idempotent — skips if model files already exist.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Default HF model repos — same as services/vision/anveshak/vision/settings.py
DEFAULT_FACETORCH_HF_MODEL = "prithivMLmods/Deep-Fake-Detector-v2-Model"
DEFAULT_EFFICIENTNET_HF_MODEL = "umm-maybe/AI-image-detector"


def _download_facetorch_onnx(model_dir: Path, hf_model: str) -> Path:
    """Download face deepfake model from HuggingFace and export to ONNX."""
    from optimum.onnxruntime import ORTModelForImageClassification

    out_path = model_dir / "facetorch" / "face_deepfake.onnx"
    if out_path.exists():
        print(f"  facetorch already exists: {out_path}")
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {hf_model} ...")

    ort_model = ORTModelForImageClassification.from_pretrained(
        hf_model,
        export=True,
    )
    ort_model.save_pretrained(str(out_path.parent))

    exported = out_path.parent / "model.onnx"
    if exported.exists() and exported != out_path:
        exported.rename(out_path)

    print(f"  facetorch/face_deepfake.onnx  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return out_path


def _download_efficientnet_onnx(model_dir: Path, hf_model: str) -> Path:
    """Download non-face deepfake model from HuggingFace and export to ONNX."""
    from optimum.onnxruntime import ORTModelForImageClassification

    out_path = model_dir / "efficientnet" / "deepfake_b0.onnx"
    if out_path.exists():
        print(f"  efficientnet already exists: {out_path}")
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {hf_model} ...")

    ort_model = ORTModelForImageClassification.from_pretrained(
        hf_model,
        export=True,
    )
    ort_model.save_pretrained(str(out_path.parent))

    exported = out_path.parent / "model.onnx"
    if exported.exists() and exported != out_path:
        exported.rename(out_path)

    print(f"  efficientnet/deepfake_b0.onnx ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download deepfake ONNX models from HuggingFace")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("/app/models"),
        help="Root directory for model files (default: /app/models)",
    )
    parser.add_argument(
        "--facetorch-model",
        default=DEFAULT_FACETORCH_HF_MODEL,
        help=f"HuggingFace repo for face deepfake model (default: {DEFAULT_FACETORCH_HF_MODEL})",
    )
    parser.add_argument(
        "--efficientnet-model",
        default=DEFAULT_EFFICIENTNET_HF_MODEL,
        help=f"HuggingFace repo for non-face deepfake model (default: {DEFAULT_EFFICIENTNET_HF_MODEL})",
    )
    args = parser.parse_args()

    print(f"Model directory: {args.model_dir}")
    print("Downloading real HuggingFace models and exporting to ONNX...")

    _download_facetorch_onnx(args.model_dir, args.facetorch_model)
    _download_efficientnet_onnx(args.model_dir, args.efficientnet_model)

    print("Done. Both deepfake models ready.")


if __name__ == "__main__":
    main()
