"""Unit tests: deepfake score is always float 0.0–1.0, never bool.

Criteria 4.14: score is float 0.0–1.0 — NEVER bool.
CLAUDE.md rule 7: deepfake scores are probabilities, never booleans.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np


# ---------------------------------------------------------------------------
# Helper: build a mock ONNX session that returns controlled logits
# ---------------------------------------------------------------------------

def _mock_session(logits: list[float]):
    """Return a mock onnxruntime.InferenceSession that outputs given logits."""
    session = MagicMock()
    session.run.return_value = [np.array([logits], dtype=np.float32)]
    session.get_inputs.return_value = [MagicMock(name="input")]
    return session


# ---------------------------------------------------------------------------
# Tests: DeepfakeDetector base — score() always returns clamped float
# ---------------------------------------------------------------------------

class TestDeepfakeDetectorBase:
    """Test the ABC contract without needing real ONNX models."""

    def _make_concrete_detector(self, raw_score: float):
        """Create a minimal concrete subclass returning a fixed score."""
        from anveshak.vision.detectors.base import DeepfakeDetector

        class _FakeDetector(DeepfakeDetector):
            def _load_model(self):
                self._model = True  # sentinel

            def _infer(self, image_bytes: bytes) -> float:
                return raw_score

        return _FakeDetector(device="cpu")

    @pytest.mark.unit
    def test_score_returns_float_not_bool(self):
        """score() must return float — never bool (CLAUDE.md rule 7)."""
        detector = self._make_concrete_detector(0.9)
        result = detector.score(b"fake_image_bytes")
        assert isinstance(result, float), "deepfake_score must be float, not bool"
        assert not isinstance(result, bool), "deepfake_score must not be bool"

    @pytest.mark.unit
    def test_score_clamped_to_0_1(self):
        """score() clamps to [0.0, 1.0] regardless of raw model output."""
        detector_high = self._make_concrete_detector(1.5)
        detector_low = self._make_concrete_detector(-0.3)
        assert detector_high.score(b"x") <= 1.0
        assert detector_low.score(b"x") >= 0.0

    @pytest.mark.unit
    def test_score_zero_is_float_not_false(self):
        """Score of 0.0 must be float(0.0), not False."""
        detector = self._make_concrete_detector(0.0)
        result = detector.score(b"x")
        assert result == 0.0
        assert type(result) is float  # strict type check

    @pytest.mark.unit
    def test_score_one_is_float_not_true(self):
        """Score of 1.0 must be float(1.0), not True."""
        detector = self._make_concrete_detector(1.0)
        result = detector.score(b"x")
        assert result == 1.0
        assert type(result) is float

    @pytest.mark.unit
    def test_onnx_providers_cpu(self):
        """CPU device → CPUExecutionProvider only."""
        detector = self._make_concrete_detector(0.5)
        providers = detector.onnx_providers()
        assert providers == ["CPUExecutionProvider"]

    @pytest.mark.unit
    def test_onnx_providers_cuda(self):
        """CUDA device → CUDAExecutionProvider first (criteria 4.16)."""
        from anveshak.vision.detectors.base import DeepfakeDetector

        class _FakeCudaDetector(DeepfakeDetector):
            def _load_model(self):
                self._model = True

            def _infer(self, image_bytes: bytes) -> float:
                return 0.5

        detector = _FakeCudaDetector(device="cuda")
        providers = detector.onnx_providers()
        assert providers[0] == "CUDAExecutionProvider"
        assert "CPUExecutionProvider" in providers


# ---------------------------------------------------------------------------
# Tests: DIRE raises NotImplementedError on CPU
# ---------------------------------------------------------------------------

class TestDIREDetector:
    @pytest.mark.unit
    def test_dire_raises_on_cpu(self):
        """DIREDetector must raise NotImplementedError when device=cpu (criteria 4.19)."""
        from anveshak.vision.detectors.dire import DIREDetector

        with pytest.raises(NotImplementedError, match="GPU"):
            DIREDetector(device="cpu")

    @pytest.mark.unit
    def test_efficientnet_instantiates_on_cpu(self):
        """EfficientNetDetector must instantiate on CPU without error."""
        from anveshak.vision.detectors.efficientnet import EfficientNetDetector

        # Should not raise — lazy loading happens on first score() call
        detector = EfficientNetDetector(device="cpu")
        assert detector.device == "cpu"


# ---------------------------------------------------------------------------
# Tests: worst_case_score — None for empty, max for non-empty
# ---------------------------------------------------------------------------

class TestWorstCaseScore:
    @pytest.mark.unit
    def test_empty_list_returns_none(self):
        """Empty frame list must return None, not 0.0 (analysis failed)."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([])
        assert result is None

    @pytest.mark.unit
    def test_single_frame(self):
        """Single frame score returned as-is."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([0.75])
        assert result == 0.75
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_multiple_frames_returns_max(self):
        """Worst-case (maximum) score across frames."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([0.2, 0.9, 0.5])
        assert result == 0.9


# ---------------------------------------------------------------------------
# Tests: _analyse_image / _analyse_video return (None, "error") on failure
# ---------------------------------------------------------------------------

class TestDeepfakeErrorHandling:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyse_image_returns_none_on_error(self):
        """_analyse_image must return (None, 'error'), never (0.0, 'error')."""
        with patch("anveshak.vision.jobs._get_deepfake_image_detector") as mock_get:
            mock_get.side_effect = RuntimeError("model not found")

            from anveshak.vision.jobs import _analyse_image
            score, model = await _analyse_image(b"fake", "asset-1")

        assert score is None, "Failed deepfake analysis must return None, not 0.0"
        assert model == "error"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyse_video_returns_none_on_error(self):
        """_analyse_video must return (None, 'error'), never (0.0, 'error')."""
        with patch("anveshak.vision.jobs.extract_keyframes", side_effect=RuntimeError("ffmpeg missing")):
            from anveshak.vision.jobs import _analyse_video
            score, model = await _analyse_video("/fake/path.mp4", "asset-2")

        assert score is None, "Failed video analysis must return None, not 0.0"
        assert model == "error"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyse_video_returns_none_on_no_frames(self):
        """_analyse_video with no extractable frames must return (None, 'no_frames')."""
        with patch("anveshak.vision.jobs.extract_keyframes", return_value=[]):
            from anveshak.vision.jobs import _analyse_video
            score, model = await _analyse_video("/fake/path.mp4", "asset-3")

        assert score is None, "No frames must return None, not 0.0"
        assert model == "no_frames"
