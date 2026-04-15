"""DIREDetector — high-accuracy AI-generation detection via reconstruction error.

Criteria 4.19: VISION_DEEPFAKE_VIDEO_MODEL=dire → this class instantiated.

DIRE (Detecting AI-Generated Images via Reconstruction Error) uses a diffusion
model to reconstruct the input image. Real images reconstruct with lower error
than AI-generated ones.

HARDWARE REQUIREMENT: RTX 3080+ (8GB VRAM). On CPU: ~90s per frame — impractical.
This detector raises NotImplementedError when vision_device=cpu.
See hardware.md for the full upgrade path.
"""
from __future__ import annotations

from .base import DeepfakeDetector
from ..settings import settings


class DIREDetector(DeepfakeDetector):
    """Diffusion-based deepfake detector.

    Accuracy: ~94% on GenImage benchmark (GPU only — see hardware.md).
    Speed:    ~2s per frame on GPU; ~90s on CPU (impractical).

    IMPORTANT: Raises NotImplementedError on cpu device.
    Set VISION_DEEPFAKE_VIDEO_MODEL=efficientnet for CPU deployments.
    """

    def __init__(self, device: str = "cpu") -> None:
        super().__init__(device=device)
        if device == "cpu":
            raise NotImplementedError(
                "DIREDetector requires GPU (RTX 3080+ with 8GB VRAM). "
                "DIRE runs ~90s per frame on CPU — impractical for production. "
                "Set VISION_DEEPFAKE_VIDEO_MODEL=efficientnet for CPU deployments. "
                "See hardware.md for the GPU upgrade path."
            )

    def _load_model(self) -> None:
        # DIRE uses a diffusion model (e.g. DDPM) as the reconstructor.
        # Model loading is deferred to first inference call.
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError(
                "DIREDetector: CUDA not available. "
                "Ensure nvidia-container-toolkit is installed and VISION_DEVICE=cuda."
            )
        # Actual DIRE model loading would go here.
        # Placeholder: raise to prevent silent misconfiguration.
        raise NotImplementedError(
            "DIRE model weights are not yet downloaded. "
            "Run 'make download-dire-models' after GPU hardware is available."
        )

    def _infer(self, image_bytes: bytes) -> float:
        raise NotImplementedError("DIRE requires GPU. See hardware.md.")
