# ONNX Hardware Independence Pattern

## When to load: adding any ONNX-based ML model to a service

> See also: `learned/hf-model-label-order-verification.md` — verify id2label from config.json before writing FAKE_INDEX; inverted labels produce confident but wrong predictions
> See also: `learned/optimum-onnx-export-cleanup.md` — partial file cleanup on export failure; optimum extras; model.onnx rename

---

## Pattern: transparent CPU/CUDA via provider list

```python
# detectors/base.py
from .settings import settings   # settings.vision_device = "cpu" or "cuda"

def onnx_providers(self) -> list[str]:
    if settings.vision_device == "cuda":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]

# Usage in any detector subclass:
import onnxruntime as ort

class FacetorchDetector(DeepfakeDetector):
    def _load_model(self):
        self._session = ort.InferenceSession(
            str(model_path),
            providers=self.onnx_providers()   # ← device comes from config, never hardcoded
        )
```

**Why:** ONNX Runtime silently falls back down the provider list. If CUDA isn't available but
`CUDAExecutionProvider` is listed first, it falls back to CPU. This means code works on both
laptop (CPU) and production (GPU) with zero code changes — just flip `VISION_DEVICE=cuda`.

---

## Pattern: DeepfakeDetector ABC — score() always returns float

```python
# detectors/base.py
from abc import ABC, abstractmethod

class DeepfakeDetector(ABC):
    @abstractmethod
    def _load_model(self) -> None: ...

    @abstractmethod
    def _infer(self, image_bytes: bytes) -> float: ...

    def score(self, image_bytes: bytes) -> float:
        """Always returns float 0.0–1.0. CLAUDE.md rule 7: never bool."""
        result = self._infer(image_bytes)
        return float(max(0.0, min(1.0, result)))   # clamp — never trust raw model output
```

**Why:** The clamp in `score()` is the single enforcement point for CLAUDE.md rule 7.
Subclasses override `_infer()` only — they never touch clamping or type conversion.
If a new detector returns logits or raw float > 1.0, `score()` silently corrects it.

---

## Pattern: GPU-only detector raises NotImplementedError on CPU

```python
# detectors/dire.py
class DIREDetector(DeepfakeDetector):
    def _load_model(self) -> None:
        if settings.vision_device != "cuda":
            raise NotImplementedError(
                "DIRE requires GPU (RTX 3080+). See hardware.md. "
                "Set VISION_DEEPFAKE_VIDEO_MODEL=efficientnet for CPU deployment."
            )
```

**Why:** Failing fast with a clear message is better than running at 90s/frame and timing out.
The error references hardware.md — operator knows exactly what to change.

---

## Hardware upgrade: zero code change

```
VISION_DEVICE=cpu  →  VISION_DEVICE=cuda
YOLO_MODEL_SIZE=nano  →  YOLO_MODEL_SIZE=xlarge
VISION_DEEPFAKE_VIDEO_MODEL=efficientnet  →  VISION_DEEPFAKE_VIDEO_MODEL=dire
CLIP_MODEL_NAME=openai/clip-vit-base-patch32  →  openai/clip-vit-large-patch14
```

No application code changes. All routing done by factory in `detectors/__init__.py`.
See hardware.md for full upgrade matrix.
