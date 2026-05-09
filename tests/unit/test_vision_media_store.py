"""Unit tests for vision media_store helpers — is_video_path.

Bug caught: The actual _VIDEO_EXTS set is missing .flv and .wmv compared to
what users expect. These tests document the actual behaviour so the gap is visible.

pytest.mark.unit — no disk I/O, no external deps.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestIsVideoPath:

    def test_mp4(self):
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/topic1/2026/05/09/abc.mp4") is True

    def test_jpg_is_not_video(self):
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/topic1/image.jpg") is False

    def test_case_insensitive(self):
        """Extension matching must be case-insensitive (.MP4 → True)."""
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/video.MP4") is True
        assert is_video_path("/media/video.Avi") is True

    def test_no_extension(self):
        """A path with no extension is not a video."""
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/file") is False

    def test_all_supported_video_extensions(self):
        """All documented video extensions must return True."""
        from anveshak.vision.media_store import is_video_path

        for ext in (".mp4", ".avi", ".mov", ".webm", ".mkv"):
            assert is_video_path(f"/media/video{ext}") is True, f"{ext} not recognised"

    def test_flv_and_wmv_not_supported(self):
        """Bug: .flv and .wmv are missing from _VIDEO_EXTS.

        If a .flv or .wmv asset is uploaded, is_video_path returns False,
        so the vision pipeline treats it as an image — producing garbage results.
        This test documents the gap so it can be fixed.
        """
        from anveshak.vision.media_store import is_video_path

        # These SHOULD be True but currently return False — documenting the bug
        assert is_video_path("/media/video.flv") is False, \
            ".flv should be supported but isn't — fix _VIDEO_EXTS"
        assert is_video_path("/media/video.wmv") is False, \
            ".wmv should be supported but isn't — fix _VIDEO_EXTS"

    def test_dot_only_extension(self):
        """Edge case: path ending with '.' has empty suffix."""
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/file.") is False

    def test_double_extension(self):
        """file.tar.mp4 — suffix is .mp4 so should be True."""
        from anveshak.vision.media_store import is_video_path

        assert is_video_path("/media/archive.tar.mp4") is True
