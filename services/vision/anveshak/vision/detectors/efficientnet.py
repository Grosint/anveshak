"""EfficientNetDetector — non-face/general AI-generation detection via ONNX.

Criteria 4.17: EfficientNetDetector implements DeepfakeDetector ABC.
Criteria 4.18: VISION_DEEPFAKE_VIDEO_MODEL=efficientnet → this class instantiated.

Model: deepfake_b0.onnx — EfficientNet-B0 fine-tuned on GenImage synthetic dataset.
Input:  [1, 3, 224, 224] float32 (ImageNet-normalised)
Output: [1, 1] float32 logit — sigmoid → fake probability
Accuracy: ~85% on GenImage benchmark (CPU, ONNX).
Speed:    ~2s per frame on CPU (see hardware.md).
"""
from __future__ import annotations

import structlog

from .base import DeepfakeDetector
from ..settings import settings

log = structlog.get_logger(__name__)


class EfficientNetDetector(DeepfakeDetector):
    """ONNX EfficientNet-B0 proxy classifier for non-face deepfake detection.

    Used for landscapes, architecture, constructed scenes, and any image
    where Haar cascade face detection returns no faces.

    Hardware independence: device='cpu' → CPUExecutionProvider,
                           device='cuda' → CUDAExecutionProvider.
    """

    MODEL_INPUT_SIZE = (224, 224)

    def _load_model(self) -> None:
        import onnxruntime as ort

        model_path = settings.model_dir / settings.efficientnet_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"EfficientNetDetector: model file not found at {model_path}. "
                f"Run 'make download-models' or check VISION_MODEL_DIR."
            )

        self._model = ort.InferenceSession(
            str(model_path),
            providers=self.onnx_providers(),
        )
        log.info(
            "vision.efficientnet.loaded",
            model_path=str(model_path),
            device=self._device,
        )

    def _infer(self, image_bytes: bytes) -> float:
        import numpy as np

        arr = self.preprocess_image(image_bytes, self.MODEL_INPUT_SIZE)

        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: arr})

        # Output: [1, 1] single logit → sigmoid → fake probability
        logit = float(outputs[0][0][0])
        prob = 1.0 / (1.0 + (2.718281828 ** -logit))  # sigmoid
        return prob
