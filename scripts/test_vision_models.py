"""Vision ML model integration tests — runs INSIDE the analyse-vision-worker container.

Tests YOLO, CLIP, and deepfake detectors using real models from the
vision_models volume. Outputs JSON to stdout.

Usage (from host):
    docker cp scripts/test_vision_models.py anveshak-analyse-vision-worker-1:/tmp/
    docker exec anveshak-analyse-vision-worker-1 python /tmp/test_vision_models.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

os.environ["LOG_LEVEL"] = "ERROR"


def _result(test: str, passed: bool, detail: str, elapsed: float) -> dict[str, Any]:
    return {
        "test": test,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "elapsed_s": round(elapsed, 2),
    }


def _exc_detail(exc: BaseException, limit: int = 200) -> str:
    """Format an exception as type plus message.

    Many exceptions stringify to nothing: httpx.ReadTimeout is the one that cost
    time here, since a timed-out Ollama call was reported as `"detail": ""`, with
    only the elapsed_s hinting at what happened. The type alone is diagnostic.
    """
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}"[:limit] if message else type(exc).__name__


def _make_test_image() -> bytes:
    """Generate a minimal valid JPEG image for testing."""
    try:
        import io

        from PIL import Image

        img = Image.new("RGB", (224, 224), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Fallback: minimal JPEG bytes (1x1 pixel)
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\x9e\xa7\xa3\xff\xd9"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_yolo_loads() -> dict:
    """YOLO detector loads from /app/models/yolo/ and runs inference."""
    t0 = time.monotonic()
    try:
        from anveshak.vision.detectors.yolo_detector import YOLODetector

        detector = YOLODetector()
        image_bytes = _make_test_image()
        detections = detector.detect(image_bytes)
        elapsed = time.monotonic() - t0
        return _result(
            "yolo_load_and_detect",
            True,
            f"model loaded, {len(detections)} detections on test image",
            elapsed,
        )
    except Exception as exc:
        return _result("yolo_load_and_detect", False, _exc_detail(exc), time.monotonic() - t0)


def test_clip_loads() -> dict:
    """CLIP classifier loads from HF cache and runs classification."""
    t0 = time.monotonic()
    try:
        from anveshak.vision.detectors.clip_detector import CLIPClassifier

        classifier = CLIPClassifier()
        image_bytes = _make_test_image()
        results = classifier.classify(image_bytes, ["military", "civilian", "landscape"])
        elapsed = time.monotonic() - t0
        has_scores = len(results) > 0
        return _result(
            "clip_load_and_classify",
            has_scores,
            f"model loaded, {len(results)} categories scored",
            elapsed,
        )
    except Exception as exc:
        return _result("clip_load_and_classify", False, _exc_detail(exc), time.monotonic() - t0)


def test_deepfake_image_score() -> dict:
    """Deepfake image detector loads ONNX model and returns float score."""
    t0 = time.monotonic()
    try:
        from anveshak.vision.detectors import get_deepfake_detector
        from anveshak.vision.settings import settings

        detector = get_deepfake_detector(
            settings.vision_deepfake_image_model, settings.vision_device
        )
        image_bytes = _make_test_image()
        score = detector.score(image_bytes)
        elapsed = time.monotonic() - t0
        ok = isinstance(score, float) and 0.0 <= score <= 1.0
        return _result(
            "deepfake_image_score", ok, f"score={score:.4f}, type={type(score).__name__}", elapsed
        )
    except Exception as exc:
        return _result("deepfake_image_score", False, _exc_detail(exc), time.monotonic() - t0)


def test_deepfake_video_score() -> dict:
    """Deepfake video detector loads ONNX model and returns float score."""
    t0 = time.monotonic()
    try:
        from anveshak.vision.detectors import get_deepfake_detector
        from anveshak.vision.settings import settings

        detector = get_deepfake_detector(
            settings.vision_deepfake_video_model, settings.vision_device
        )
        image_bytes = _make_test_image()
        score = detector.score(image_bytes)
        elapsed = time.monotonic() - t0
        ok = isinstance(score, float) and 0.0 <= score <= 1.0
        return _result(
            "deepfake_video_score", ok, f"score={score:.4f}, type={type(score).__name__}", elapsed
        )
    except Exception as exc:
        return _result("deepfake_video_score", False, _exc_detail(exc), time.monotonic() - t0)


def test_deepfake_score_not_bool() -> dict:
    """Deepfake score must be float, never bool (AGENTS.md rule 7)."""
    t0 = time.monotonic()
    try:
        from anveshak.vision.detectors import get_deepfake_detector
        from anveshak.vision.settings import settings

        detector = get_deepfake_detector(
            settings.vision_deepfake_image_model, settings.vision_device
        )
        score = detector.score(_make_test_image())
        elapsed = time.monotonic() - t0
        ok = type(score) is float  # strict check: True/False are bool, not float
        return _result(
            "deepfake_not_bool", ok, f"type={type(score).__name__}, value={score}", elapsed
        )
    except Exception as exc:
        return _result("deepfake_not_bool", False, _exc_detail(exc), time.monotonic() - t0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    results = []
    for test_fn in [
        test_yolo_loads,
        test_clip_loads,
        test_deepfake_image_score,
        test_deepfake_video_score,
        test_deepfake_score_not_bool,
    ]:
        results.append(test_fn())

    sys.__stdout__.write(json.dumps(results, indent=2) + "\n")
    sys.__stdout__.flush()

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    sys.__stdout__.write(f"\nVision models: {passed}/{total} passed\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
