"""Unit tests for vision ARQ worker — run_vision_analysis and helpers.

pytest.mark.unit — mocks all DB, ML models, and file I/O.
Tests real business logic: routing to face/no-face detector, video analysis,
None-on-error (CLAUDE.md rule 7), media cleanup.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx():
    """Build a fake ARQ context with mocked DB pool."""
    db_pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    db_pool.acquire.return_value = acm
    return {"db_pool": db_pool}, db_pool, conn


def _make_asset_row(
    media_asset_id="asset-1",
    topic_id="topic-1",
    content_item_id="ci-1",
    storage_path="/media/topic-1/2026/05/09/abc123.jpg",
):
    return {
        "id": media_asset_id,
        "topic_id": topic_id,
        "content_item_id": content_item_id,
        "storage_path": storage_path,
    }


# ---------------------------------------------------------------------------
# run_vision_analysis tests
# ---------------------------------------------------------------------------

class TestRunVisionAnalysis:

    @pytest.mark.asyncio
    async def test_asset_not_found(self):
        """Asset doesn't exist -> returns error dict."""
        ctx, db_pool, conn = _make_ctx()

        with patch("anveshak.vision.jobs.get_media_asset", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "nonexistent-id")

        assert result["error"] == "media_asset_not_found"

    @pytest.mark.asyncio
    async def test_file_missing(self):
        """File not on disk -> returns error dict."""
        ctx, db_pool, conn = _make_ctx()
        asset = _make_asset_row()

        with patch("anveshak.vision.jobs.get_media_asset", new_callable=AsyncMock) as mock_get, \
             patch("anveshak.vision.jobs.read_media_bytes") as mock_read:
            mock_get.return_value = asset
            mock_read.side_effect = FileNotFoundError("No such file")

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "asset-1")

        assert result["error"] == "file_not_found"

    @pytest.mark.asyncio
    async def test_analyse_image_routes_to_face_detector(self):
        """has_faces=True -> face detector used."""
        face_detector = MagicMock()
        face_detector.has_faces = MagicMock(return_value=True)
        face_detector.score = MagicMock(return_value=0.7)

        with patch("anveshak.vision.jobs._get_deepfake_image_detector", return_value=face_detector), \
             patch("anveshak.vision.jobs.settings") as mock_settings:
            mock_settings.vision_deepfake_image_model = "facetorch"
            mock_settings.vision_deepfake_video_model = "dire"

            from anveshak.vision.jobs import _analyse_image
            score, model_name = await _analyse_image(b"fake-image-bytes", "asset-1")

        assert score == 0.7
        assert "face" in model_name
        face_detector.score.assert_called_once_with(b"fake-image-bytes")

    @pytest.mark.asyncio
    async def test_analyse_image_routes_to_no_face_detector(self):
        """has_faces=False -> video/non-face detector used."""
        face_detector = MagicMock()
        face_detector.has_faces = MagicMock(return_value=False)

        video_detector = MagicMock()
        video_detector.score = MagicMock(return_value=0.3)

        with patch("anveshak.vision.jobs._get_deepfake_image_detector", return_value=face_detector), \
             patch("anveshak.vision.jobs._get_deepfake_video_detector", return_value=video_detector), \
             patch("anveshak.vision.jobs.settings") as mock_settings:
            mock_settings.vision_deepfake_image_model = "facetorch"
            mock_settings.vision_deepfake_video_model = "dire"

            from anveshak.vision.jobs import _analyse_image
            score, model_name = await _analyse_image(b"fake-image-bytes", "asset-1")

        assert score == 0.3
        assert "no_face" in model_name
        video_detector.score.assert_called_once_with(b"fake-image-bytes")

    @pytest.mark.asyncio
    async def test_analyse_image_returns_none_on_error(self):
        """Detector raises -> returns (None, 'error')."""
        face_detector = MagicMock()
        face_detector.has_faces = MagicMock(side_effect=RuntimeError("ONNX crash"))

        with patch("anveshak.vision.jobs._get_deepfake_image_detector", return_value=face_detector), \
             patch("anveshak.vision.jobs.settings") as mock_settings:
            mock_settings.vision_deepfake_image_model = "facetorch"

            from anveshak.vision.jobs import _analyse_image
            score, model_name = await _analyse_image(b"fake-image-bytes", "asset-1")

        assert score is None
        assert model_name == "error"

    @pytest.mark.asyncio
    async def test_analyse_video_no_frames(self):
        """extract_keyframes returns [] -> returns (None, 'no_frames')."""
        with patch("anveshak.vision.jobs.extract_keyframes", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = []

            from anveshak.vision.jobs import _analyse_video
            score, model_name = await _analyse_video("/path/to/video.mp4", "asset-1")

        assert score is None
        assert model_name == "no_frames"

    @pytest.mark.asyncio
    async def test_analyse_video_worst_case_propagated(self):
        """Multiple frame scores -> max score returned."""
        video_detector = MagicMock()
        video_detector.score = MagicMock(side_effect=[0.2, 0.8, 0.4])

        with patch("anveshak.vision.jobs.extract_keyframes", new_callable=AsyncMock) as mock_extract, \
             patch("anveshak.vision.jobs._get_deepfake_video_detector", return_value=video_detector), \
             patch("anveshak.vision.jobs.settings") as mock_settings:
            mock_extract.return_value = [b"frame1", b"frame2", b"frame3"]
            mock_settings.vision_deepfake_video_model = "dire"

            from anveshak.vision.jobs import _analyse_video
            score, model_name = await _analyse_video("/path/to/video.mp4", "asset-1")

        assert score == 0.8
        assert "video" in model_name
        assert "3frames" in model_name


# ---------------------------------------------------------------------------
# cleanup_expired_media tests
# ---------------------------------------------------------------------------

class TestCleanupExpiredMedia:

    @pytest.mark.asyncio
    async def test_disabled_when_retention_zero(self):
        """MEDIA_RETENTION_DAYS=0 -> skipped."""
        ctx, _, _ = _make_ctx()

        with patch("anveshak.vision.jobs.settings") as mock_settings:
            mock_settings.media_retention_days = 0

            from anveshak.vision.jobs import cleanup_expired_media
            result = await cleanup_expired_media(ctx)

        assert result["skipped"] == "retention_disabled"

    @pytest.mark.asyncio
    async def test_deletes_file_and_clears_db(self):
        """File exists -> unlinked, clear_media_storage_path called."""
        ctx, db_pool, conn = _make_ctx()
        expired_rows = [{"id": "asset-1", "storage_path": "/tmp/test_media_file.jpg"}]

        with patch("anveshak.vision.jobs.settings") as mock_settings, \
             patch("anveshak.vision.jobs.get_expired_media_assets", new_callable=AsyncMock) as mock_get, \
             patch("anveshak.vision.jobs.clear_media_storage_path", new_callable=AsyncMock) as mock_clear, \
             patch("pathlib.Path.unlink") as mock_unlink:
            mock_settings.media_retention_days = 30
            mock_get.return_value = expired_rows

            from anveshak.vision.jobs import cleanup_expired_media
            result = await cleanup_expired_media(ctx)

        assert result["deleted"] == 1
        assert result["errors"] == 0
        mock_unlink.assert_called_once_with(missing_ok=True)
        mock_clear.assert_awaited_once_with(conn, "asset-1")


# ---------------------------------------------------------------------------
# Pipeline routing tests — video/image branch guards
# ---------------------------------------------------------------------------

_VISION_JOBS = "anveshak.vision.jobs"


class TestVideoSkipsImageOnlySteps:
    """Video assets must skip YOLO, EXIF, pHash, and CLIP (image-only steps)."""

    @pytest.mark.asyncio
    async def test_video_skips_yolo_and_exif(self):
        """is_video_path returns True → YOLO detector NOT called, extract_exif NOT called."""
        ctx, db_pool, conn = _make_ctx()
        asset = _make_asset_row(storage_path="/media/topic-1/2026/05/09/abc123.mp4")

        with patch(f"{_VISION_JOBS}.get_media_asset", new_callable=AsyncMock) as mock_get_asset, \
             patch(f"{_VISION_JOBS}.read_media_bytes") as mock_read, \
             patch(f"{_VISION_JOBS}.is_video_path") as mock_is_video, \
             patch(f"{_VISION_JOBS}.extract_exif") as mock_exif, \
             patch(f"{_VISION_JOBS}.compute_phash") as mock_phash, \
             patch(f"{_VISION_JOBS}.update_media_asset_exif_phash", new_callable=AsyncMock) as mock_update_exif, \
             patch(f"{_VISION_JOBS}._get_yolo") as mock_get_yolo, \
             patch(f"{_VISION_JOBS}._analyse_video", new_callable=AsyncMock) as mock_analyse_video, \
             patch(f"{_VISION_JOBS}.get_topic_clip_categories", new_callable=AsyncMock) as mock_clip_cats, \
             patch(f"{_VISION_JOBS}.insert_vision_result", new_callable=AsyncMock) as mock_insert, \
             patch(f"{_VISION_JOBS}.tag_content_item", new_callable=AsyncMock) as mock_tag, \
             patch(f"{_VISION_JOBS}.vision_analyses_total") as mock_metric, \
             patch(f"{_VISION_JOBS}.vision_deepfake_score") as mock_df_metric:
            mock_get_asset.return_value = asset
            mock_read.return_value = b"video-bytes"
            mock_is_video.return_value = True
            mock_analyse_video.return_value = (0.5, "dire:video")

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "asset-1")

        # YOLO never instantiated for video
        mock_get_yolo.assert_not_called()
        # EXIF never extracted for video
        mock_exif.assert_not_called()
        # pHash never computed for video
        mock_phash.assert_not_called()
        assert result["is_video"] is True


class TestClipSkippedWhenNoCategories:
    """CLIP classification requires topic categories; empty list → skip."""

    @pytest.mark.asyncio
    async def test_clip_skipped_when_no_categories(self):
        """get_topic_clip_categories returns [] → _get_clip() never called."""
        ctx, db_pool, conn = _make_ctx()
        asset = _make_asset_row()

        yolo = MagicMock()
        yolo.detect = MagicMock(return_value=[])
        yolo.to_jsonb = MagicMock(return_value=[])
        yolo.high_interest_labels = MagicMock(return_value=[])

        with patch(f"{_VISION_JOBS}.get_media_asset", new_callable=AsyncMock) as mock_get_asset, \
             patch(f"{_VISION_JOBS}.read_media_bytes") as mock_read, \
             patch(f"{_VISION_JOBS}.is_video_path") as mock_is_video, \
             patch(f"{_VISION_JOBS}.extract_exif") as mock_exif, \
             patch(f"{_VISION_JOBS}.compute_phash") as mock_phash, \
             patch(f"{_VISION_JOBS}.update_media_asset_exif_phash", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}._get_yolo", return_value=yolo), \
             patch(f"{_VISION_JOBS}._analyse_image", new_callable=AsyncMock) as mock_analyse_img, \
             patch(f"{_VISION_JOBS}.get_topic_clip_categories", new_callable=AsyncMock) as mock_clip_cats, \
             patch(f"{_VISION_JOBS}._get_clip") as mock_get_clip, \
             patch(f"{_VISION_JOBS}.insert_vision_result", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}.tag_content_item", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}.vision_analyses_total") as mock_metric, \
             patch(f"{_VISION_JOBS}.vision_deepfake_score") as mock_df_metric:
            mock_get_asset.return_value = asset
            mock_read.return_value = b"image-bytes"
            mock_is_video.return_value = False
            mock_exif.return_value = {}
            mock_phash.return_value = 12345
            mock_analyse_img.return_value = (0.3, "facetorch:face")
            mock_clip_cats.return_value = []  # no categories

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "asset-1")

        # CLIP singleton never created when no categories
        mock_get_clip.assert_not_called()
        assert result["clip_categories_matched"] == 0


class TestDeepfakeNoneSkipsMetric:
    """Deepfake score None (error case) must NOT be recorded in the histogram."""

    @pytest.mark.asyncio
    async def test_deepfake_none_skips_metric(self):
        """_analyse_image returns (None, 'error') → vision_deepfake_score.observe NOT called."""
        ctx, db_pool, conn = _make_ctx()
        asset = _make_asset_row()

        yolo = MagicMock()
        yolo.detect = MagicMock(return_value=[])
        yolo.to_jsonb = MagicMock(return_value=[])
        yolo.high_interest_labels = MagicMock(return_value=[])

        with patch(f"{_VISION_JOBS}.get_media_asset", new_callable=AsyncMock) as mock_get_asset, \
             patch(f"{_VISION_JOBS}.read_media_bytes") as mock_read, \
             patch(f"{_VISION_JOBS}.is_video_path") as mock_is_video, \
             patch(f"{_VISION_JOBS}.extract_exif") as mock_exif, \
             patch(f"{_VISION_JOBS}.compute_phash") as mock_phash, \
             patch(f"{_VISION_JOBS}.update_media_asset_exif_phash", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}._get_yolo", return_value=yolo), \
             patch(f"{_VISION_JOBS}._analyse_image", new_callable=AsyncMock) as mock_analyse_img, \
             patch(f"{_VISION_JOBS}.get_topic_clip_categories", new_callable=AsyncMock) as mock_clip_cats, \
             patch(f"{_VISION_JOBS}.insert_vision_result", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}.tag_content_item", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}.vision_analyses_total") as mock_metric, \
             patch(f"{_VISION_JOBS}.vision_deepfake_score") as mock_df_metric:
            mock_get_asset.return_value = asset
            mock_read.return_value = b"image-bytes"
            mock_is_video.return_value = False
            mock_exif.return_value = {}
            mock_phash.return_value = 12345
            mock_analyse_img.return_value = (None, "error")  # deepfake failed
            mock_clip_cats.return_value = []

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "asset-1")

        # None score must NOT be observed in histogram (line 220-221 guard)
        mock_df_metric.observe.assert_not_called()
        assert result["deepfake_score"] is None


class TestNoHighInterestNoTag:
    """YOLO detections present but no high-interest labels → tag_content_item NOT called."""

    @pytest.mark.asyncio
    async def test_no_high_interest_labels_no_tag(self):
        """high_interest_labels returns [] → tag_content_item NOT called."""
        ctx, db_pool, conn = _make_ctx()
        asset = _make_asset_row()

        yolo = MagicMock()
        yolo.detect = MagicMock(return_value=[{"label": "car", "confidence": 0.9}])
        yolo.to_jsonb = MagicMock(return_value=[{"label": "car", "confidence": 0.9}])
        yolo.high_interest_labels = MagicMock(return_value=[])  # car is not high-interest

        with patch(f"{_VISION_JOBS}.get_media_asset", new_callable=AsyncMock) as mock_get_asset, \
             patch(f"{_VISION_JOBS}.read_media_bytes") as mock_read, \
             patch(f"{_VISION_JOBS}.is_video_path") as mock_is_video, \
             patch(f"{_VISION_JOBS}.extract_exif") as mock_exif, \
             patch(f"{_VISION_JOBS}.compute_phash") as mock_phash, \
             patch(f"{_VISION_JOBS}.update_media_asset_exif_phash", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}._get_yolo", return_value=yolo), \
             patch(f"{_VISION_JOBS}._analyse_image", new_callable=AsyncMock) as mock_analyse_img, \
             patch(f"{_VISION_JOBS}.get_topic_clip_categories", new_callable=AsyncMock) as mock_clip_cats, \
             patch(f"{_VISION_JOBS}.insert_vision_result", new_callable=AsyncMock), \
             patch(f"{_VISION_JOBS}.tag_content_item", new_callable=AsyncMock) as mock_tag, \
             patch(f"{_VISION_JOBS}.vision_analyses_total") as mock_metric, \
             patch(f"{_VISION_JOBS}.vision_deepfake_score") as mock_df_metric:
            mock_get_asset.return_value = asset
            mock_read.return_value = b"image-bytes"
            mock_is_video.return_value = False
            mock_exif.return_value = {}
            mock_phash.return_value = 12345
            mock_analyse_img.return_value = (0.2, "facetorch:face")
            mock_clip_cats.return_value = []

            from anveshak.vision.jobs import run_vision_analysis
            result = await run_vision_analysis(ctx, "asset-1")

        # tag_content_item NOT called when high_interest is empty (line 190 guard)
        mock_tag.assert_not_called()
        # But YOLO detections are still counted
        assert result["yolo_detections"] == 1
        assert result["high_interest_labels"] == []
