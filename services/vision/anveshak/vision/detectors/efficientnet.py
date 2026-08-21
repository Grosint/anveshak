"""EfficientNetDetector — non-face/general AI-generation detection via ONNX.

Criteria 4.17: EfficientNetDetector implements DeepfakeDetector ABC.
Criteria 4.18: VISION_DEEPFAKE_VIDEO_MODEL=efficientnet → this class instantiated.

Model: umm-maybe/AI-image-detector (Swin-Base, trained on AI vs human images).
Input:  [1, 3, 224, 224] float32 (ImageNet-normalised)
Output: [1, 2] float32 logits — softmax → FAKE_INDEX is fake probability
"""

from __future__ import annotations

import structlog

from ..settings import settings
from .base import DeepfakeDetector

log = structlog.get_logger(__name__)

# Label ordering from HF model config.json: {0: "artificial", 1: "human"}
# Verified against umm-maybe/AI-image-detector config.
# Index 0 = "artificial" (AI-generated) = fake probability
FAKE_INDEX = 0


class EfficientNetDetector(DeepfakeDetector):
    """ONNX EfficientNet-B0 classifier for non-face deepfake detection.

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
        import scipy.special

        arr = self.preprocess_image(image_bytes, self.MODEL_INPUT_SIZE)

        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: arr})

        # Output: [1, 2] logits → softmax → FAKE_INDEX is fake probability
        # onnxruntime types run() as returning Sequence[Any | SparseTensor];
        # these models return dense ndarrays.
        logits = outputs[0][0]  # pyright: ignore[reportIndexIssue]
        probs = scipy.special.softmax(logits)
        return float(probs[FAKE_INDEX])
