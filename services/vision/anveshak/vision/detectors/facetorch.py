"""FacetorchDetector — face-centric deepfake detection via ONNX.

Criteria 4.13: FacetorchDetector implements DeepfakeDetector ABC.
Criteria 4.16: CUDAExecutionProvider when device=cuda (from base.onnx_providers()).

Model: face_deepfake.onnx — binary classifier trained on FaceForensics++.
Input:  [1, 3, 224, 224] float32 (ImageNet-normalised)
Output: [1, 2] float32 logits — index 0 = real, index 1 = fake
"""
from __future__ import annotations

import structlog

from .base import DeepfakeDetector
from ..settings import settings

log = structlog.get_logger(__name__)


class FacetorchDetector(DeepfakeDetector):
    """ONNX-based face deepfake detector.

    Hardware independence: device='cpu' → CPUExecutionProvider,
                           device='cuda' → CUDAExecutionProvider (zero code change).
    Accuracy: ~91% AUC on FaceForensics++ benchmark (CPU, ONNX).
    Speed:    ~8–12s per image on CPU; ~0.3s on GPU (see hardware.md).
    """

    MODEL_INPUT_SIZE = (224, 224)

    def _load_model(self) -> None:
        import onnxruntime as ort

        model_path = settings.model_dir / settings.facetorch_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"FacetorchDetector: model file not found at {model_path}. "
                f"Run 'make download-models' or check VISION_MODEL_DIR."
            )

        self._model = ort.InferenceSession(
            str(model_path),
            providers=self.onnx_providers(),
        )
        log.info(
            "vision.facetorch.loaded",
            model_path=str(model_path),
            device=self._device,
            providers=self.onnx_providers(),
        )

    def _infer(self, image_bytes: bytes) -> float:
        import numpy as np
        import scipy.special

        arr = self.preprocess_image(image_bytes, self.MODEL_INPUT_SIZE)

        # Run ONNX inference
        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: arr})

        # Output: [1, 2] logits → softmax → index 1 is "fake" probability
        logits = outputs[0][0]  # shape (2,)
        probs = scipy.special.softmax(logits)
        return float(probs[1])  # probability of being a deepfake
