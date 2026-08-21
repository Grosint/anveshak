"""Unit tests: YOLO detection output schema.

Criteria 4.9: returns list of {label, confidence, bbox} dicts.
Criteria 4.10: stored as JSONB (must be JSON-serialisable).
Criteria 4.11: high_interest_labels extracts defence-relevant detections.
"""

import json

import pytest


class TestYOLODetectorOutputSchema:
    @pytest.mark.unit
    def test_yolo_detection_has_required_fields(self):
        """Each detection must have label (str), confidence (float), bbox (list of 4 floats)."""
        from anveshak.vision.detectors.yolo_detector import YOLODetection

        det = YOLODetection(label="person", confidence=0.98, bbox=[10.0, 20.0, 100.0, 200.0])
        assert isinstance(det.label, str)
        assert isinstance(det.confidence, float)
        assert isinstance(det.bbox, list)
        assert len(det.bbox) == 4

    @pytest.mark.unit
    def test_yolo_to_jsonb_is_serialisable(self):
        """to_jsonb() output must be JSON-serialisable (stored in JSONB column)."""
        from anveshak.vision.detectors.yolo_detector import YOLODetection, YOLODetector

        yolo = YOLODetector()
        detections = [
            YOLODetection(label="airplane", confidence=0.91, bbox=[0.0, 0.0, 640.0, 480.0]),
            YOLODetection(label="person", confidence=0.75, bbox=[100.0, 50.0, 200.0, 300.0]),
        ]
        jsonb = yolo.to_jsonb(detections)
        # Must be JSON-serialisable
        serialised = json.dumps(jsonb)
        reloaded = json.loads(serialised)
        assert len(reloaded) == 2
        assert reloaded[0]["label"] == "airplane"
        assert isinstance(reloaded[0]["confidence"], float)
        assert isinstance(reloaded[0]["bbox"], list)

    @pytest.mark.unit
    def test_high_interest_labels_filters_correctly(self):
        """high_interest_labels() returns only defence-relevant YOLO detections."""
        from anveshak.vision.detectors.yolo_detector import YOLODetection, YOLODetector

        yolo = YOLODetector()
        detections = [
            YOLODetection(label="airplane", confidence=0.9, bbox=[0, 0, 100, 100]),
            YOLODetection(label="cat", confidence=0.85, bbox=[0, 0, 50, 50]),
            YOLODetection(label="person", confidence=0.7, bbox=[0, 0, 200, 200]),
            YOLODetection(label="bicycle", confidence=0.6, bbox=[0, 0, 80, 80]),
        ]
        high = yolo.high_interest_labels(detections)
        assert "airplane" in high
        assert "person" in high
        assert "cat" not in high
        assert "bicycle" not in high

    @pytest.mark.unit
    def test_empty_detections_returns_empty_jsonb(self):
        """Empty detection list → empty JSONB list."""
        from anveshak.vision.detectors.yolo_detector import YOLODetector

        yolo = YOLODetector()
        jsonb = yolo.to_jsonb([])
        assert jsonb == []
        assert json.dumps(jsonb) == "[]"
