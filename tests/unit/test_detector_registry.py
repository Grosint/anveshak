"""Unit tests for vision detector registry — get_deepfake_detector factory.

Bug caught: Unknown model_type must raise ValueError with a helpful message
listing valid options. If someone typos "facetorch" as "face_torch", the error
must be actionable.

pytest.mark.unit — imports only; does NOT load actual model weights.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestGetDeepfakeDetector:

    def test_unknown_model_type_raises_valueerror(self):
        """Unknown model type must raise ValueError listing valid options."""
        from anveshak.vision.detectors import get_deepfake_detector

        with pytest.raises(ValueError, match="Unknown deepfake model type"):
            get_deepfake_detector("nonexistent", device="cpu")

    def test_error_message_lists_valid_types(self):
        """The error message must include valid model types for debugging."""
        from anveshak.vision.detectors import get_deepfake_detector

        with pytest.raises(ValueError, match="facetorch.*efficientnet.*dire"):
            get_deepfake_detector("bad_model", device="cpu")

    def test_facetorch_returns_correct_type(self):
        """facetorch model type must import and return a FacetorchDetector."""
        from anveshak.vision.detectors import get_deepfake_detector
        from anveshak.vision.detectors.base import DeepfakeDetector

        detector = get_deepfake_detector("facetorch", device="cpu")
        assert isinstance(detector, DeepfakeDetector)

    def test_dire_on_cpu_raises_not_implemented(self):
        """Bug caught: DIREDetector requires GPU — on CPU it must raise NotImplementedError.

        If this raised a generic Exception or silently returned a broken detector,
        the vision pipeline would produce garbage 0.0 scores with no error.
        The explicit NotImplementedError with hardware.md reference is correct.
        """
        from anveshak.vision.detectors import get_deepfake_detector

        with pytest.raises(NotImplementedError, match="GPU"):
            get_deepfake_detector("dire", device="cpu")

    def test_efficientnet_returns_correct_type(self):
        """efficientnet model type must import and return an EfficientNetDetector."""
        from anveshak.vision.detectors import get_deepfake_detector
        from anveshak.vision.detectors.base import DeepfakeDetector

        detector = get_deepfake_detector("efficientnet", device="cpu")
        assert isinstance(detector, DeepfakeDetector)

    def test_model_type_is_case_sensitive(self):
        """Bug: 'Facetorch' (capitalised) raises ValueError — model_type matching is exact.

        If someone passes an env var that gets capitalised, the factory silently
        fails with a confusing error instead of normalising the input.
        """
        from anveshak.vision.detectors import get_deepfake_detector

        with pytest.raises(ValueError):
            get_deepfake_detector("Facetorch", device="cpu")
