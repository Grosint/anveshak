# Vision Patterns

## When to load: any task involving image analysis, video processing, deepfake detection, or computer vision

> See also: `.claude/skills/learned/onnx-hardware-independence.md` — ONNX provider selection, DeepfakeDetector ABC, DIRE GPU guard
> See also: `.claude/skills/learned/arq-worker-ml-singleton.md` — lazy module-level model loading in ARQ workers
> See also: `.claude/skills/learned/sdk-shared-utility-no-db.md` — shared downloader in SDK without DB/ARQ deps
> See also: `.claude/skills/learned/phase-check-pitfalls.md` — pitfall 7 (standalone ARQ function vs helper)

---

### Hardware independence — ALWAYS use config, never hardcode
```python
# settings.py
class VisionSettings(BaseSettings):
    yolo_model_size: str = "nano"      # nano|small|medium|large|xlarge
    vision_device: str = "cpu"         # cpu|cuda — see hardware.md
    deepfake_image_model: str = "facetorch"   # facetorch|dire
    deepfake_video_model: str = "efficientnet"  # efficientnet|dire — see hardware.md
    vision_batch_size: int = 1         # increase on GPU
```

### YOLOv8 object detection
```python
from ultralytics import YOLO

MODEL_MAP = {"nano": "yolov8n.pt", "small": "yolov8s.pt", "xlarge": "yolov8x.pt"}

def load_yolo(size: str, device: str) -> YOLO:
    model = YOLO(MODEL_MAP[size])
    model.to(device)
    return model

def detect_objects(model: YOLO, image_bytes: bytes) -> list[dict]:
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes))
    results = model(img)[0]
    return [
        {"class": model.names[int(b.cls)], "confidence": float(b.conf),
         "bbox": b.xyxy[0].tolist()}
        for b in results.boxes
    ]
```

### CLIP zero-shot classification (HuggingFace transformers — NOT openai/clip)
```python
# Use transformers, NOT the `clip` package — see services/vision/pyproject.toml
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
import io, torch

processor = CLIPProcessor.from_pretrained(settings.clip_model_name)
model = CLIPModel.from_pretrained(settings.clip_model_name)

def classify_image(image_bytes: bytes, categories: list[str]) -> list[dict]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(text=categories, images=img, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits_per_image
        probs = logits.softmax(dim=-1)[0]
    results = [{"label": cat, "score": float(p)} for cat, p in zip(categories, probs)]
    return sorted(results, key=lambda x: x["score"], reverse=True)
```

### Video deepfake — worst-case frame propagation
```python
import asyncio
from pathlib import Path

async def analyse_video(storage_path: str) -> tuple[float, str]:
    frames = await extract_keyframes(Path(storage_path))  # ffmpeg → JPEG bytes
    if not frames:
        return 0.0, "no_frames"
    scores = [await asyncio.to_thread(detector.score, f) for f in frames]
    return float(max(scores)), f"{model_name}:video:{len(frames)}frames"

# worst_case_score() in video.py:
def worst_case_score(frame_scores: list[float]) -> float:
    return float(max(frame_scores)) if frame_scores else 0.0
```

**Why worst-case:** For deepfake detection, a single manipulated frame is enough to
flag a video. Mean would dilute the signal from mostly-authentic frames.

### DeepfakeDetector ABC — canonical structure
```python
from abc import ABC, abstractmethod

class DeepfakeDetector(ABC):
    @abstractmethod
    def _load_model(self) -> None: ...

    @abstractmethod
    def _infer(self, image_bytes: bytes) -> float: ...

    def score(self, image_bytes: bytes) -> float:
        """CLAUDE.md rule 7: always float 0.0–1.0, never bool."""
        return float(max(0.0, min(1.0, self._infer(image_bytes))))
```

See `.claude/skills/learned/onnx-hardware-independence.md` for the full ONNX provider pattern.

### Deepfake detection — always return float, never bool
```python
# WRONG
is_deepfake: bool = score > 0.5

# CORRECT
deepfake_score: float = score  # always 0.0–1.0
# UI shows "P(synthetic) = 87%" — analyst decides threshold
```

### EXIF extraction
```python
from PIL import Image
from PIL.ExifTags import TAGS
import io

def extract_exif(image_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(image_bytes))
    exif_data = img._getexif() or {}
    return {
        TAGS.get(tag_id, tag_id): str(value)
        for tag_id, value in exif_data.items()
    }
```

### Perceptual hash (reverse image lookup)
```python
from PIL import Image
import imagehash
import io

def compute_phash(image_bytes: bytes) -> int:
    img = Image.open(io.BytesIO(image_bytes))
    return int(str(imagehash.phash(img)), 16)

def is_duplicate_image(phash: int, existing_phashes: list[int],
                        threshold: int = 8) -> bool:
    return any(bin(phash ^ p).count("1") <= threshold for p in existing_phashes)
```
