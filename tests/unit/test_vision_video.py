"""Unit tests for video keyframe extraction and worst-case scoring.

pytest.mark.unit — mocks ffmpeg and Pillow, no external dependencies.
Tests real business logic: worst_case_score logic, file-not-found, ffmpeg fallback.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# worst_case_score tests
# ---------------------------------------------------------------------------

class TestWorstCaseScore:

    def test_returns_max(self):
        """[0.1, 0.8, 0.3] -> 0.8"""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([0.1, 0.8, 0.3])
        assert result == pytest.approx(0.8)

    def test_empty_returns_none(self):
        """[] -> None (CLAUDE.md rule 7: None on failure, never 0.0)."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([])
        assert result is None

    def test_single_frame(self):
        """[0.5] -> 0.5"""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([0.5])
        assert result == pytest.approx(0.5)

    def test_all_same_score(self):
        """All identical scores -> that score."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([0.42, 0.42, 0.42])
        assert result == pytest.approx(0.42)

    def test_returns_float(self):
        """Return value is always float, never int."""
        from anveshak.vision.video import worst_case_score

        result = worst_case_score([1, 0, 0])
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# extract_keyframes tests
# ---------------------------------------------------------------------------

class TestExtractKeyframes:

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Non-existent path -> FileNotFoundError."""
        from anveshak.vision.video import extract_keyframes

        with pytest.raises(FileNotFoundError):
            await extract_keyframes(Path("/nonexistent/video.mp4"))

    @pytest.mark.asyncio
    async def test_ffmpeg_fallback(self):
        """No ffmpeg -> _pillow_first_frame called."""
        from anveshak.vision.video import extract_keyframes

        # Reset the cached _FFMPEG_AVAILABLE so _check_ffmpeg runs fresh
        with patch("anveshak.vision.video._FFMPEG_AVAILABLE", None), \
             patch("shutil.which", return_value=None), \
             patch("anveshak.vision.video._pillow_first_frame", new_callable=AsyncMock) as mock_pillow:
            mock_pillow.return_value = [b"fake-frame-bytes"]

            # Create a temp file so the exists() check passes
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(b"fake video data")
                temp_path = Path(f.name)

            try:
                result = await extract_keyframes(temp_path)
            finally:
                temp_path.unlink(missing_ok=True)

        mock_pillow.assert_awaited_once()
        assert result == [b"fake-frame-bytes"]


# ---------------------------------------------------------------------------
# _check_ffmpeg tests
# ---------------------------------------------------------------------------

class TestCheckFfmpeg:

    def test_caches_result(self):
        """_check_ffmpeg caches the result after first call."""
        import anveshak.vision.video as video_mod

        original = video_mod._FFMPEG_AVAILABLE
        try:
            video_mod._FFMPEG_AVAILABLE = None
            with patch("shutil.which", return_value="/usr/bin/ffmpeg") as mock_which:
                result1 = video_mod._check_ffmpeg()
                result2 = video_mod._check_ffmpeg()

            assert result1 is True
            assert result2 is True
            # Only called once due to caching
            mock_which.assert_called_once()
        finally:
            video_mod._FFMPEG_AVAILABLE = original

    def test_returns_false_when_missing(self):
        """ffmpeg not on PATH -> returns False."""
        import anveshak.vision.video as video_mod

        original = video_mod._FFMPEG_AVAILABLE
        try:
            video_mod._FFMPEG_AVAILABLE = None
            with patch("shutil.which", return_value=None):
                result = video_mod._check_ffmpeg()

            assert result is False
        finally:
            video_mod._FFMPEG_AVAILABLE = original
