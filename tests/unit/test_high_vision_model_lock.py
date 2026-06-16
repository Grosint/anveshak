"""Unit tests for vision model loading thread safety — HIGH-10.

Model singletons must use double-checked locking to prevent concurrent
jobs from instantiating 500MB models twice.
"""
from __future__ import annotations

import threading
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.unit


class TestVisionModelThreadSafety:

    def test_get_yolo_uses_lock(self):
        """_get_yolo must use a threading.Lock for thread-safe instantiation."""
        from anveshak.vision import jobs as vision_jobs

        # Check that a lock exists for YOLO
        assert hasattr(vision_jobs, "_yolo_lock"), (
            "_get_yolo must use a threading.Lock — _yolo_lock not found"
        )
        assert isinstance(vision_jobs._yolo_lock, type(threading.Lock())), (
            "_yolo_lock must be a threading.Lock"
        )

    def test_get_deepfake_image_uses_lock(self):
        """_get_deepfake_image_detector must use a threading.Lock."""
        from anveshak.vision import jobs as vision_jobs

        assert hasattr(vision_jobs, "_deepfake_image_lock"), (
            "_get_deepfake_image_detector must use _deepfake_image_lock"
        )

    def test_get_clip_uses_lock(self):
        """_get_clip must use a threading.Lock."""
        from anveshak.vision import jobs as vision_jobs

        assert hasattr(vision_jobs, "_clip_lock"), (
            "_get_clip must use _clip_lock"
        )

    def test_concurrent_get_yolo_creates_single_instance(self):
        """Two threads calling _get_yolo simultaneously must create exactly one instance."""
        import anveshak.vision.jobs as vision_jobs

        # Reset singleton
        vision_jobs._yolo_detector = None
        instantiation_count = {"n": 0}

        original_init = vision_jobs.YOLODetector

        class CountingYOLO:
            def __init__(self):
                instantiation_count["n"] += 1

        with patch.object(vision_jobs, "YOLODetector", CountingYOLO):
            threads = []
            for _ in range(10):
                t = threading.Thread(target=vision_jobs._get_yolo)
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert instantiation_count["n"] == 1, (
            f"YOLODetector instantiated {instantiation_count['n']} times, expected 1"
        )

        # Cleanup
        vision_jobs._yolo_detector = None
