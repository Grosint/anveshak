"""DeepfakeDetector ABC — contract all deepfake detectors must implement.

Criteria 4.12: DeepfakeDetector ABC with .score(image_bytes: bytes) -> float
Criteria 4.14: Score is ALWAYS float 0.0–1.0 — NEVER bool.
Criteria 4.16: CUDAExecutionProvider used when settings.vision_device=cuda — zero code change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class DeepfakeDetector(ABC):
    """Abstract base class for all deepfake detection models.

    All subclasses MUST:
    1. Return float in [0.0, 1.0] from score() — never bool, never None
    2. Accept device='cpu' or device='cuda' — zero code change between them
    3. Lazy-load model on first call to score() — do not load at __init__
    4. Be stateless across calls (model is loaded once, reused per worker process)
    """

    def __init__(self, device: str = "cpu") -> None:
        # device comes from settings.vision_device — never hardcoded at call site
        self._device = device
        self._model = None  # lazy-loaded on first call

    @property
    def device(self) -> str:
        return self._device

    @abstractmethod
    def _load_model(self) -> None:
        """Load model weights into self._model. Called once by score() on first use."""

    @abstractmethod
    def _infer(self, image_bytes: bytes) -> float:
        """Run inference. Returns raw probability float in [0.0, 1.0]."""

    def score(self, image_bytes: bytes) -> float:
        """Return deepfake probability for the given image bytes.

        Criteria 4.14: return type is ALWAYS float 0.0–1.0, never bool.
        """
        if self._model is None:
            self._load_model()
        result = self._infer(image_bytes)
        # Clamp defensively — subclass must return float in [0,1] but guard anyway
        return float(max(0.0, min(1.0, result)))

    def onnx_providers(self) -> list[str]:
        """Return ONNX execution providers for the configured device.

        Criteria 4.16: CUDAExecutionProvider used when device=cuda.
        Zero code change in service code — only settings.vision_device changes.
        """
        if self._device == "cuda":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def preprocess_image(
        self,
        image_bytes: bytes,
        target_size: tuple[int, int] = (224, 224),
    ):
        """Resize and normalise image bytes to a numpy float32 array [1, C, H, W].

        Standard ImageNet normalisation: mean=(0.485,0.456,0.406), std=(0.229,0.224,0.225).
        Used by FacetorchDetector and EfficientNetDetector.
        """
        import io
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize(target_size, Image.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        # HWC → CHW → NCHW
        return arr.transpose(2, 0, 1)[np.newaxis, ...]

    def has_faces(self, image_bytes: bytes) -> bool:
        """Quick face presence check using OpenCV Haar cascade.

        Returns True if at least one face is detected above the confidence
        threshold. Used to route to FacetorchDetector vs EfficientNetDetector.
        """
        import io
        import numpy as np
        import cv2
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        return len(faces) > 0
