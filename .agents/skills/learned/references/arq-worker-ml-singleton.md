# ARQ Worker ML Singleton Pattern

## When to load: any task adding ML inference to an ARQ worker

---

## Pattern

Module-level lazy globals — load each ML model ONCE per worker process, reuse across jobs.

```python
# jobs.py
from typing import Optional
from .detectors.yolo_detector import YOLODetector
from .detectors.clip_detector import CLIPClassifier

_yolo_detector: Optional[YOLODetector] = None
_clip_classifier: Optional[CLIPClassifier] = None

def _get_yolo() -> YOLODetector:
    global _yolo_detector
    if _yolo_detector is None:
        _yolo_detector = YOLODetector()   # loads model from disk on first call
    return _yolo_detector

def _get_clip() -> CLIPClassifier:
    global _clip_classifier
    if _clip_classifier is None:
        _clip_classifier = CLIPClassifier()
    return _clip_classifier

async def run_vision_analysis(ctx: dict, media_asset_id: str) -> dict:
    yolo = _get_yolo()     # free after first job
    clip = _get_clip()     # free after first job
    ...
```

**Why:** ML models are large (YOLOv8n = 6MB but CLIP = 1.5GB, Facetorch = 200MB+).
Re-loading per job would crater throughput and risk OOM on every restart.
ARQ forks one worker process per `max_jobs` slot — each process holds its own model copy.

**Where this lives:** Only in ARQ worker `jobs.py`. Never in FastAPI routes (routes don't run inference).

---

## Companion: limit concurrency in WorkerSettings

```python
class WorkerSettings:
    max_jobs = 2        # vision is CPU-heavy — limit to avoid OOM
    job_timeout = 300   # 5 minutes max (slow CPU deepfake)
```

On GPU hardware: bump `max_jobs = 4` via env-var override (add to settings.py if needed).

---

## Pitfall: don't use `on_startup` to load models

`on_startup(ctx)` is called before the first job. Loading all models there forces 3-4GB RAM
even when jobs only use one model (e.g. a YOLO-only job). Lazy loading means you only
pay for what you use.

Exception: if your worker ALWAYS uses all models, eager loading in `on_startup` is fine
and avoids first-job latency. Use judgement.
