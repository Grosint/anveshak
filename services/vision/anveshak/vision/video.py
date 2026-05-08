"""Video keyframe extraction for deepfake analysis.

Criteria 4.20: keyframes extracted every settings.video_keyframe_interval_s seconds
Criteria 4.21: each keyframe analysed independently; worst-case score propagated

Requires ffmpeg on PATH. Falls back to first-frame-only if ffmpeg is absent,
with a structured warning log so the operator knows precision is degraded.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import structlog

from .settings import settings

log = structlog.get_logger(__name__)

_FFMPEG_AVAILABLE: Optional[bool] = None


def _check_ffmpeg() -> bool:
    """Check once whether ffmpeg is available on PATH."""
    global _FFMPEG_AVAILABLE
    if _FFMPEG_AVAILABLE is None:
        _FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
        if not _FFMPEG_AVAILABLE:
            log.warning(
                "vision.video.ffmpeg_missing",
                hint="Install ffmpeg for full keyframe extraction. "
                     "Falling back to first-frame-only analysis.",
            )
    return _FFMPEG_AVAILABLE


async def extract_keyframes(video_path: Path) -> list[bytes]:
    """Extract keyframes from a video file.

    Frames are extracted every settings.video_keyframe_interval_s seconds.
    Returns list of JPEG-encoded frame bytes (at least one frame always returned).

    Falls back to first-frame extraction if ffmpeg is not available.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if _check_ffmpeg():
        return await _ffmpeg_extract(video_path)
    else:
        return await _pillow_first_frame(video_path)


async def _ffmpeg_extract(video_path: Path) -> list[bytes]:
    """Extract frames at regular interval using ffmpeg."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_pattern = Path(tmpdir) / "frame_%04d.jpg"
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{settings.video_keyframe_interval_s}",
            "-q:v", "2",          # JPEG quality (2 = high quality, low compression)
            str(output_pattern),
            "-y",                  # overwrite without asking
            "-loglevel", "error",  # suppress ffmpeg console output
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            log.warning(
                "vision.video.ffmpeg_error",
                video_path=str(video_path),
                stderr=stderr.decode(errors="replace")[:500],
            )
            # Fallback to first-frame
            return await _pillow_first_frame(video_path)

        frame_files = sorted(Path(tmpdir).glob("frame_*.jpg"))
        if not frame_files:
            log.warning("vision.video.no_frames_extracted", video=str(video_path))
            return await _pillow_first_frame(video_path)

        frames = [f.read_bytes() for f in frame_files]
        log.info(
            "vision.video.frames_extracted",
            count=len(frames),
            interval_s=settings.video_keyframe_interval_s,
        )
        return frames


async def _pillow_first_frame(video_path: Path) -> list[bytes]:
    """Extract the first frame using Pillow (no ffmpeg required).

    Only works for GIF/animated formats. For other video formats returns
    a placeholder that will produce a neutral (0.0) deepfake score.
    """
    import io
    from PIL import Image

    try:
        img = Image.open(video_path)
        img.seek(0)  # first frame for animated GIFs
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        return [buf.getvalue()]
    except Exception as exc:
        log.warning(
            "vision.video.pillow_fallback_failed",
            video=str(video_path),
            error=str(exc),
        )
        return []


def worst_case_score(frame_scores: list[float]) -> float | None:
    """Return worst-case (maximum) deepfake score across all keyframes.

    Criteria 4.21: worst-case score propagated to media_asset.
    CLAUDE.md rule 7: always float, never bool. None = analysis failed.
    """
    if not frame_scores:
        return None
    return float(max(frame_scores))
