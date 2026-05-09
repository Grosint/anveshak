"""Unit tests: real deepfake model integration.

Tests that the vision pipeline uses real HuggingFace models instead of
dummy random-weight ONNX exports.

TDD RED phase — these tests define the expected interface BEFORE implementation.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np


# ---------------------------------------------------------------------------
# Tests: settings.py — HuggingFace model source env vars
# ---------------------------------------------------------------------------

class TestVisionSettingsHFModels:
    """Settings must expose HuggingFace model names for deepfake detectors."""

    @pytest.mark.unit
    def test_facetorch_hf_model_setting_exists(self):
        """settings.facetorch_hf_model must exist and default to a real HF repo."""
        from anveshak.vision.settings import settings

        assert hasattr(settings, "facetorch_hf_model"), (
            "settings.facetorch_hf_model must exist — controls which HF model "
            "is downloaded for face deepfake detection"
        )
        # Must be a non-empty string pointing to a HuggingFace repo
        assert isinstance(settings.facetorch_hf_model, str)
        assert "/" in settings.facetorch_hf_model, (
            "facetorch_hf_model must be a HuggingFace repo path like 'org/model'"
        )

    @pytest.mark.unit
    def test_efficientnet_hf_model_setting_exists(self):
        """settings.efficientnet_hf_model must exist and default to a real HF repo."""
        from anveshak.vision.settings import settings

        assert hasattr(settings, "efficientnet_hf_model"), (
            "settings.efficientnet_hf_model must exist — controls which HF model "
            "is downloaded for non-face deepfake detection"
        )
        assert isinstance(settings.efficientnet_hf_model, str)
        assert "/" in settings.efficientnet_hf_model, (
            "efficientnet_hf_model must be a HuggingFace repo path like 'org/model'"
        )


# ---------------------------------------------------------------------------
# Tests: EfficientNetDetector — 2-class softmax output (not sigmoid)
# ---------------------------------------------------------------------------

def _mock_session_2class(logits: list[float]):
    """Mock ONNX session returning [1, 2] logits (real HF model output)."""
    session = MagicMock()
    session.run.return_value = [np.array([logits], dtype=np.float32)]
    session.get_inputs.return_value = [MagicMock(name="input")]
    return session


class TestEfficientNet2ClassOutput:
    """EfficientNetDetector must handle 2-class logit output from real HF models."""

    @pytest.mark.unit
    def test_infer_with_2class_logits(self):
        """_infer() must handle [1, 2] logits via softmax, not [1, 1] sigmoid."""
        from anveshak.vision.detectors.efficientnet import EfficientNetDetector, FAKE_INDEX

        detector = EfficientNetDetector(device="cpu")
        # umm-maybe/AI-image-detector: {0: "artificial", 1: "human"}
        # FAKE_INDEX=0, so high logit at index 0 → high fake score
        detector._model = _mock_session_2class([2.5, 0.1])

        with patch.object(detector, "preprocess_image", return_value=np.zeros((1, 3, 224, 224), dtype=np.float32)):
            score = detector._infer(b"test_image")

        assert isinstance(score, float)
        assert score > 0.5, (
            f"High artificial logit [2.5, 0.1] should produce score > 0.5, got {score}"
        )

    @pytest.mark.unit
    def test_infer_real_image_low_score(self):
        """Real image logits [0.1, 2.5] → low fake probability (high human logit)."""
        from anveshak.vision.detectors.efficientnet import EfficientNetDetector, FAKE_INDEX

        detector = EfficientNetDetector(device="cpu")
        # High human logit (index 1), low artificial logit (index 0) → low fake score
        detector._model = _mock_session_2class([0.1, 2.5])

        with patch.object(detector, "preprocess_image", return_value=np.zeros((1, 3, 224, 224), dtype=np.float32)):
            score = detector._infer(b"test_image")

        assert isinstance(score, float)
        assert score < 0.5, (
            f"High human logit [0.1, 2.5] should produce score < 0.5, got {score}"
        )

    @pytest.mark.unit
    def test_infer_uses_softmax_not_sigmoid(self):
        """Verify softmax is used for 2-class output, not sigmoid."""
        import scipy.special
        from anveshak.vision.detectors.efficientnet import EfficientNetDetector, FAKE_INDEX

        detector = EfficientNetDetector(device="cpu")
        logits = [3.0, 1.0]
        detector._model = _mock_session_2class(logits)

        with patch.object(detector, "preprocess_image", return_value=np.zeros((1, 3, 224, 224), dtype=np.float32)):
            score = detector._infer(b"test")

        # Expected softmax result at FAKE_INDEX=0
        expected_probs = scipy.special.softmax(logits)
        assert abs(score - float(expected_probs[FAKE_INDEX])) < 0.01, (
            f"Score {score} doesn't match softmax result {expected_probs[FAKE_INDEX]}. "
            "EfficientNet must use softmax for 2-class output, not sigmoid."
        )


# ---------------------------------------------------------------------------
# Tests: FacetorchDetector — FAKE_INDEX constant
# ---------------------------------------------------------------------------

class TestFacetorchFakeIndex:
    """FacetorchDetector must have a documented FAKE_INDEX for label ordering."""

    @pytest.mark.unit
    def test_fake_index_constant_exists(self):
        """Module must define FAKE_INDEX to document label ordering from model config."""
        import anveshak.vision.detectors.facetorch as ft_module

        assert hasattr(ft_module, "FAKE_INDEX"), (
            "facetorch module must define FAKE_INDEX constant documenting "
            "which output index corresponds to 'fake' in the HF model's config.json"
        )

    @pytest.mark.unit
    def test_fake_index_is_valid(self):
        """FAKE_INDEX must be 0 or 1 (2-class model)."""
        from anveshak.vision.detectors.facetorch import FAKE_INDEX

        assert FAKE_INDEX in (0, 1), f"FAKE_INDEX must be 0 or 1, got {FAKE_INDEX}"


# ---------------------------------------------------------------------------
# Tests: EfficientNetDetector — FAKE_INDEX constant
# ---------------------------------------------------------------------------

class TestEfficientNetFakeIndex:
    """EfficientNetDetector must also have a FAKE_INDEX constant."""

    @pytest.mark.unit
    def test_fake_index_constant_exists(self):
        """Module must define FAKE_INDEX for label ordering."""
        import anveshak.vision.detectors.efficientnet as en_module

        assert hasattr(en_module, "FAKE_INDEX"), (
            "efficientnet module must define FAKE_INDEX constant documenting "
            "which output index corresponds to 'fake'"
        )

    @pytest.mark.unit
    def test_fake_index_is_valid(self):
        """FAKE_INDEX must be 0 or 1 (2-class model)."""
        from anveshak.vision.detectors.efficientnet import FAKE_INDEX

        assert FAKE_INDEX in (0, 1), f"FAKE_INDEX must be 0 or 1, got {FAKE_INDEX}"


# ---------------------------------------------------------------------------
# Tests: download_models.py — no more random torch.onnx.export
# ---------------------------------------------------------------------------

class TestDownloadModelsNoRandom:
    """download_models.py must download real weights, not generate random ones."""

    @pytest.mark.unit
    def test_facetorch_function_not_named_export(self):
        """Function should be named _download_*, not _export_* (downloads real weights)."""
        import anveshak.vision.download_models as dm

        assert not hasattr(dm, "_export_facetorch_onnx"), (
            "_export_facetorch_onnx still exists — must be replaced with "
            "a download function that fetches real HuggingFace weights"
        )
        assert hasattr(dm, "_download_facetorch_onnx"), (
            "_download_facetorch_onnx must exist — downloads real HF model "
            "and exports to ONNX"
        )

    @pytest.mark.unit
    def test_efficientnet_function_not_named_export(self):
        """Function should be named _download_*, not _export_* (downloads real weights)."""
        import anveshak.vision.download_models as dm

        assert not hasattr(dm, "_export_efficientnet_onnx"), (
            "_export_efficientnet_onnx still exists — must be replaced with "
            "a download function that fetches real HuggingFace weights"
        )
        assert hasattr(dm, "_download_efficientnet_onnx"), (
            "_download_efficientnet_onnx must exist — downloads real HF model "
            "and exports to ONNX"
        )
