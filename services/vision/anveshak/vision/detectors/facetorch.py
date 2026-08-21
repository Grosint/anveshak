"""FacetorchDetector — face-centric deepfake detection via ONNX.

Criteria 4.13: FacetorchDetector implements DeepfakeDetector ABC.
Criteria 4.16: CUDAExecutionProvider when device=cuda (from base.onnx_providers()).

Model: prithivMLmods/Deep-Fake-Detector-v2-Model (ViT-base, ~92% accuracy).
Input:  [1, 3, 224, 224] float32 (ImageNet-normalised)
Output: [1, 2] float32 logits — softmax → FAKE_INDEX is fake probability
"""

from __future__ import annotations

import structlog

from ..settings import settings
from .base import DeepfakeDetector

log = structlog.get_logger(__name__)

# Label ordering from HF model config.json: {0: "Realism", 1: "Deepfake"}
# Verified against prithivMLmods/Deep-Fake-Detector-v2-Model config.
FAKE_INDEX = 1


class FacetorchDetector(DeepfakeDetector):
    """ONNX-based face deepfake detector.

    Hardware independence: device='cpu' → CPUExecutionProvider,
                           device='cuda' → CUDAExecutionProvider (zero code change).
    Accuracy: ~92% on FaceForensics++/DFDC/GAN faces (see hardware.md).
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
        import scipy.special

        arr = self.preprocess_image(image_bytes, self.MODEL_INPUT_SIZE)

        # Run ONNX inference
        input_name = self._model.get_inputs()[0].name
        outputs = self._model.run(None, {input_name: arr})

        # Output: [1, 2] logits → softmax → FAKE_INDEX is fake probability
        # onnxruntime types run() as returning Sequence[Any | SparseTensor];
        # these models return dense ndarrays.
        logits = outputs[0][0]  # pyright: ignore[reportIndexIssue]  # shape (2,)
        probs = scipy.special.softmax(logits)
        return float(probs[FAKE_INDEX])
