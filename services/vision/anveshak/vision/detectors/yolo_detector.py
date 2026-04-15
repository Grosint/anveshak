"""YOLODetector — object detection via YOLOv8.

Criteria 4.7–4.11:
  4.7:  run_yolo ARQ function (in jobs.py) calls this detector
  4.8:  Model loaded from settings.yolo_model_size (never hardcoded)
  4.9:  Returns list of detections with label, confidence, bbox
  4.10: Detections stored in vision_results.yolo_detections JSONB
  4.11: Weapons/aircraft/vehicles → tagged in content_items.labels

Hardware: YOLOv8n (nano) on CPU by default.
Upgrade:  YOLO_MODEL_SIZE=xlarge → YOLOv8x (see hardware.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from ..settings import settings

log = structlog.get_logger(__name__)

# COCO class IDs relevant to OSINT / defence monitoring — tagged in content_items.labels
# YOLOv8 COCO classes: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
_HIGH_INTEREST_LABELS: frozenset[str] = frozenset({
    "person",
    "car", "truck", "bus", "motorcycle",
    "airplane", "helicopter",
    "boat", "ship",
    "military vehicle",
    "gun", "knife", "rifle",       # not in standard COCO but appear in custom fine-tuned
})


@dataclass
class YOLODetection:
    label: str
    confidence: float   # 0.0–1.0
    bbox: list[float]   # [x1, y1, x2, y2] in pixel coordinates


class YOLODetector:
    """YOLOv8 object detector.

    Lazy-loads the model on first call. Model file determined entirely by
    settings.yolo_model_size → never hardcoded.
    """

    def __init__(self) -> None:
        self._model = None

    def _load_model(self) -> None:
        from ultralytics import YOLO

        model_file = settings.yolo_model_file()
        model_path = settings.model_dir / "yolo" / model_file

        if model_path.exists():
            self._model = YOLO(str(model_path))
        else:
            # ultralytics will download if not found — log the download
            log.info(
                "vision.yolo.downloading",
                model=model_file,
                hint="Pre-download in Dockerfile to avoid runtime fetch",
            )
            self._model = YOLO(model_file)

        log.info("vision.yolo.loaded", model=model_file, device=settings.vision_device)

    def detect(self, image_bytes: bytes) -> list[YOLODetection]:
        """Run YOLO detection on image bytes.

        Returns list of YOLODetection objects. Empty list if no objects detected.
        Confidence filter: settings.yolo_confidence_threshold (never hardcoded).
        """
        if self._model is None:
            self._load_model()

        import io
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)

        results = self._model.predict(
            source=arr,
            conf=settings.yolo_confidence_threshold,
            device=settings.vision_device,
            verbose=False,
        )
        if not results:
            return []

        detections: list[YOLODetection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                label = result.names[int(box.cls[0])]
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                detections.append(
                    YOLODetection(
                        label=label,
                        confidence=round(conf, 4),
                        bbox=[round(v, 1) for v in xyxy],
                    )
                )

        log.debug(
            "vision.yolo.detected",
            count=len(detections),
            labels=[d.label for d in detections],
        )
        return detections

    def high_interest_labels(self, detections: list[YOLODetection]) -> list[str]:
        """Return detected labels that are high-interest for OSINT monitoring.

        Used to tag content_items.labels JSONB (criteria 4.11).
        """
        return [d.label for d in detections if d.label in _HIGH_INTEREST_LABELS]

    def to_jsonb(self, detections: list[YOLODetection]) -> list[dict]:
        """Serialise detections for vision_results.yolo_detections JSONB column."""
        return [
            {"label": d.label, "confidence": d.confidence, "bbox": d.bbox}
            for d in detections
        ]
