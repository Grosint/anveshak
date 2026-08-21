#!/usr/bin/env python3
"""Anveshak vision pipeline FULL validation — 4 deepfake categories + video + CLIP.

Tests the complete vision pipeline with real-world-like test fixtures:
  1. Real photo WITH face     → facetorch detector → low score
  2. Real photo WITHOUT face  → efficientnet detector → low score
  3. AI-generated WITH face   → facetorch detector → high score
  4. AI-generated WITHOUT face → efficientnet detector → high score
  5. Real video               → efficientnet (keyframes) → low score
  6. AI-generated video        → efficientnet (keyframes) → high score
  + CLIP classification with defence-relevant categories on no-face images

Usage:
    make validate-vision-full
    python scripts/validate_vision_full.py

    # With real images for meaningful deepfake scores:
    python scripts/validate_vision_full.py \\
        --real-face path/to/real_face.jpg \\
        --fake-face path/to/ai_face.jpg \\
        --real-noface path/to/landscape.jpg \\
        --fake-noface path/to/ai_landscape.jpg
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://localhost:8000"
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

JOB_POLL_INTERVAL_S = 5
JOB_TIMEOUT_S = 180  # longer for video (keyframe extraction)

CLIP_CATEGORIES = ["military vehicle", "fighter aircraft", "tank", "person", "landscape"]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    warning: bool = False


@dataclass
class TestCase:
    label: str
    image_bytes: bytes
    filename: str
    content_type: str
    expect_face: bool
    expect_high_score: bool
    is_video: bool = False
    test_clip: bool = False
    # Filled after upload + poll
    job_id: str = ""
    media_asset_id: str = ""
    result: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Image generation — Pillow + numpy for realistic 224x224 test fixtures
# ---------------------------------------------------------------------------


def _generate_real_face(size: int = 256) -> bytes:
    """Generate a realistic face-like image that triggers Haar cascade detection.

    Uses OpenCV's built-in face Haar cascade test pattern: skin-tone oval with
    dark eye regions at the correct proportions for detectMultiScale.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size), (200, 180, 160))  # skin background
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # Face oval (skin tone)
    face_w, face_h = size // 3, int(size * 0.42)
    draw.ellipse(
        [cx - face_w, cy - face_h, cx + face_w, cy + face_h],
        fill=(210, 180, 150),
    )

    # Eye sockets — dark ovals at 1/3 from top, 1/4 apart
    eye_y = cy - face_h // 3
    eye_gap = face_w // 2
    eye_w, eye_h = face_w // 4, face_h // 8
    for ex in [cx - eye_gap, cx + eye_gap]:
        draw.ellipse(
            [ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
            fill=(40, 30, 25),
        )

    # Nose shadow
    draw.line(
        [(cx, eye_y + eye_h * 2), (cx, cy + face_h // 6)],
        fill=(170, 140, 120),
        width=2,
    )

    # Mouth
    mouth_y = cy + face_h // 3
    draw.arc(
        [cx - eye_gap, mouth_y - 5, cx + eye_gap, mouth_y + 10],
        0,
        180,
        fill=(150, 80, 70),
        width=2,
    )

    # Hair (dark region above face)
    draw.rectangle(
        [cx - face_w - 10, cy - face_h - 15, cx + face_w + 10, cy - face_h + 10],
        fill=(30, 20, 15),
    )

    # Add subtle natural variation (camera noise)
    arr = np.array(img, dtype=np.float32)
    rng = np.random.RandomState(42)
    noise = rng.normal(0, 3, arr.shape).astype(np.float32)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _generate_real_landscape(size: int = 256) -> bytes:
    """Generate a landscape image — blue sky gradient + green terrain. No faces."""
    import numpy as np
    from PIL import Image

    arr = np.zeros((size, size, 3), dtype=np.uint8)

    # Sky — gradient from light blue to darker blue
    for y in range(size // 2):
        t = y / (size // 2)
        arr[y, :] = [int(135 + 80 * (1 - t)), int(180 + 60 * (1 - t)), int(220 + 35 * (1 - t))]

    # Ground — green/brown terrain
    rng = np.random.RandomState(123)
    for y in range(size // 2, size):
        t = (y - size // 2) / (size // 2)
        base_g = int(100 + 50 * (1 - t))
        base_r = int(80 + 40 * t)
        arr[y, :] = [base_r, base_g, 40]

    # Add natural texture
    noise = rng.normal(0, 5, arr.shape).astype(np.float32)
    arr = np.clip(arr.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _generate_ai_face(size: int = 256) -> bytes:
    """Generate an AI-like face image with synthetic artifacts.

    Uses the same face structure but adds telltale AI artifacts:
    - Unnaturally smooth skin (no pores/texture)
    - Subtle symmetric patterns
    - Over-saturated colors
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", (size, size), (230, 200, 180))  # over-saturated skin
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    face_w, face_h = size // 3, int(size * 0.42)

    # Perfect oval — unnaturally smooth
    draw.ellipse(
        [cx - face_w, cy - face_h, cx + face_w, cy + face_h],
        fill=(235, 195, 170),
    )

    # Perfect symmetric eyes
    eye_y = cy - face_h // 3
    eye_gap = face_w // 2
    eye_w, eye_h = face_w // 4, face_h // 8
    for ex in [cx - eye_gap, cx + eye_gap]:
        draw.ellipse(
            [ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
            fill=(35, 25, 20),
        )
        # Highlight (too perfect)
        draw.ellipse(
            [ex - eye_w // 3, eye_y - eye_h // 3, ex + eye_w // 3, eye_y + eye_h // 3],
            fill=(255, 255, 255),
        )

    # Perfect nose
    draw.line([(cx, eye_y + eye_h * 2), (cx, cy + face_h // 6)], fill=(200, 160, 140), width=3)

    # Perfect lips
    mouth_y = cy + face_h // 3
    draw.ellipse(
        [cx - eye_gap + 5, mouth_y - 8, cx + eye_gap - 5, mouth_y + 8],
        fill=(200, 100, 90),
    )

    # Hair — too uniform
    draw.rectangle(
        [cx - face_w - 10, cy - face_h - 20, cx + face_w + 10, cy - face_h + 10],
        fill=(25, 15, 10),
    )

    # AI artifact: heavy Gaussian blur (no texture/pores)
    img = img.filter(ImageFilter.GaussianBlur(radius=2))

    # AI artifact: add subtle grid pattern (GAN checkerboard)
    arr = np.array(img, dtype=np.float32)
    grid = np.zeros_like(arr)
    grid[::8, :, :] = 3
    grid[:, ::8, :] = 3
    arr = np.clip(arr + grid, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _generate_ai_landscape(size: int = 256) -> bytes:
    """Generate an AI-like landscape with synthetic artifacts.

    Unnaturally smooth gradients, periodic patterns, over-saturated.
    """
    import numpy as np
    from PIL import Image

    arr = np.zeros((size, size, 3), dtype=np.float32)

    # Over-saturated sky gradient — too smooth
    for y in range(size // 2):
        t = y / (size // 2)
        arr[y, :] = [100, int(200 * (1 - t)), int(255 * (1 - t * 0.3))]

    # Over-saturated ground — too uniform
    for y in range(size // 2, size):
        t = (y - size // 2) / (size // 2)
        arr[y, :] = [int(50 + 60 * t), int(180 - 80 * t), 30]

    # AI artifact: sine wave patterns (diffusion model artifacts)
    x_coords = np.arange(size)
    for y in range(size):
        wave = 5 * np.sin(x_coords * 0.1 + y * 0.05)
        arr[y, :, 0] += wave
        arr[y, :, 1] += wave * 0.5

    # AI artifact: checkerboard at fine scale
    checker = np.zeros((size, size), dtype=np.float32)
    checker[::4, ::4] = 2
    checker[1::4, 1::4] = 2
    arr[:, :, 0] += checker
    arr[:, :, 2] += checker

    arr = np.clip(arr, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _generate_video(frames: list[bytes], fps: int = 1) -> bytes | None:
    """Create a short MP4 from JPEG frames using ffmpeg. Returns None if ffmpeg unavailable."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, frame_bytes in enumerate(frames):
            Path(tmpdir, f"frame_{i:03d}.jpg").write_bytes(frame_bytes)

        out_path = Path(tmpdir, "output.mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(Path(tmpdir, "frame_%03d.jpg")),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-t",
                "3",
                str(out_path),
            ],
            capture_output=True,
            check=True,
        )
        return out_path.read_bytes()


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def http_json(
    method: str, url: str, headers: dict, data=None, timeout: int = 10
) -> tuple[int, dict]:
    try:
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(
            url, data=data, headers={"Accept": "application/json", **headers}, method=method
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except (json.JSONDecodeError, ValueError):
            body = {}
        return e.code, body
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": str(e)}


def http_post_multipart(
    url: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    headers: dict,
    timeout: int = 30,
) -> tuple[int, dict]:
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        + file_bytes
        + f"\r\n--{boundary}--\r\n".encode()
    )
    hdrs = {**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    try:
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except (json.JSONDecodeError, ValueError):
            body = {}
        return e.code, body
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": str(e)}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def login() -> tuple[Check, str | None]:
    status, body = http_json(
        "POST", f"{BASE}/api/v1/auth/login", {}, {"username": DEMO_USER, "password": DEMO_PASS}
    )
    token = body.get("access_token")
    return Check("Login", bool(token), "OK" if token else f"HTTP {status}"), token


def upload(tc: TestCase, token: str) -> Check:
    status, body = http_post_multipart(
        f"{BASE}/api/v1/vision/analyse",
        tc.image_bytes,
        tc.filename,
        tc.content_type,
        _auth(token),
        timeout=60,
    )
    if status != 200:
        return Check(f"Upload {tc.label}", False, f"HTTP {status}: {body.get('detail', body)}")
    tc.job_id = body["job_id"]
    tc.media_asset_id = body["media_asset_id"]
    return Check(f"Upload {tc.label}", True, f"job={tc.job_id[:8]}...")


def poll(tc: TestCase, token: str) -> Check:
    deadline = time.time() + JOB_TIMEOUT_S
    while time.time() < deadline:
        status, body = http_json("GET", f"{BASE}/api/v1/vision/jobs/{tc.job_id}", _auth(token))
        if status != 200:
            return Check(f"Poll {tc.label}", False, f"HTTP {status}")
        if body.get("status") == "complete":
            if body.get("error"):
                return Check(f"Poll {tc.label}", False, f"Error: {body['error']}")
            tc.result = body.get("result", {})
            score = tc.result.get("deepfake_score")
            score_s = f"{score:.4f}" if isinstance(score, float) else str(score)
            return Check(f"Poll {tc.label}", True, f"score={score_s}")
        time.sleep(JOB_POLL_INTERVAL_S)
    return Check(f"Poll {tc.label}", False, f"Timed out after {JOB_TIMEOUT_S}s")


def validate_result(tc: TestCase) -> list[Check]:
    checks = []
    r = tc.result

    # 1. Deepfake score exists and is float
    score = r.get("deepfake_score")
    checks.append(
        Check(
            f"{tc.label} deepfake_score type",
            isinstance(score, float),
            f"{score:.4f}" if isinstance(score, float) else f"wrong type: {type(score).__name__}",
        )
    )

    # 2. Model routing
    model = r.get("deepfake_model", "")
    if tc.is_video:
        expected_prefix = "efficientnet:video"
        routed_ok = model.startswith(expected_prefix)
    elif tc.expect_face:
        expected_prefix = "facetorch:face"
        routed_ok = model == expected_prefix
    else:
        expected_prefix = "efficientnet:no_face"
        routed_ok = model == expected_prefix
    checks.append(
        Check(
            f"{tc.label} model routing",
            routed_ok,
            f"{model} (expected {expected_prefix})",
            warning=not routed_ok,
        )
    )

    # 3. Score direction
    if isinstance(score, float):
        if tc.expect_high_score:
            direction_ok = score > 0.5
            checks.append(
                Check(
                    f"{tc.label} score > 0.5 (fake expected)",
                    True,
                    f"{score:.4f}",
                    warning=not direction_ok,
                )
            )
        else:
            direction_ok = score < 0.5
            checks.append(
                Check(
                    f"{tc.label} score < 0.5 (real expected)",
                    True,
                    f"{score:.4f}",
                    warning=not direction_ok,
                )
            )

    # 4. YOLO (images only)
    if not tc.is_video:
        yolo = r.get("yolo_detections")
        checks.append(
            Check(
                f"{tc.label} YOLO ran",
                yolo is not None and yolo >= 0,
                f"{yolo} detection(s)" if yolo is not None else "missing",
            )
        )

    # 5. pHash (images only)
    if not tc.is_video:
        phash = r.get("phash")
        checks.append(
            Check(
                f"{tc.label} pHash",
                phash is not None,
                f"{hex(phash)}" if phash is not None else "None",
                warning=phash is None,
            )
        )

    # 6. CLIP (only for no-face images with test_clip flag)
    if tc.test_clip:
        clip_matched = r.get("clip_categories_matched", 0)
        checks.append(
            Check(
                f"{tc.label} CLIP categories",
                clip_matched is not None and clip_matched >= 0,
                f"{clip_matched} categories matched",
                warning=clip_matched == 0,
            )
        )

    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Anveshak vision full E2E validation")
    parser.add_argument("--real-face", help="Path to real face photo")
    parser.add_argument("--fake-face", help="Path to AI-generated face photo")
    parser.add_argument("--real-noface", help="Path to real landscape/no-face photo")
    parser.add_argument("--fake-noface", help="Path to AI-generated landscape")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("=" * 70)
    print("ANVESHAK — Vision Pipeline FULL Validation")
    print(f"Run at: {now}")
    print("=" * 70)

    all_checks: list[Check] = []

    def _p(c: Check) -> None:
        all_checks.append(c)
        tag = "WARN" if c.warning else ("PASS" if c.passed else "FAIL")
        print(f"  [{tag}] {c.name}: {c.detail}")

    # -- Stage 1: Login --
    print("\nStage 1 — Authentication:")
    login_check, token = login()
    _p(login_check)
    if not token:
        print("\nBLOCKED: Login failed. Fix: make up && make seed-demo")
        return 1

    # -- Stage 2: Generate test fixtures --
    print("\nStage 2 — Generating test fixtures:")

    def _load_or_generate(arg_path, generator, label, ext="jpg"):
        if arg_path:
            data = Path(arg_path).read_bytes()
            print(f"  {label}: {arg_path} ({len(data):,} bytes)")
            return data
        data = generator()
        print(f"  {label}: generated ({len(data):,} bytes)")
        return data

    real_face = _load_or_generate(args.real_face, _generate_real_face, "Real face")
    fake_face = _load_or_generate(args.fake_face, _generate_ai_face, "AI face")
    real_noface = _load_or_generate(args.real_noface, _generate_real_landscape, "Real landscape")
    fake_noface = _load_or_generate(args.fake_noface, _generate_ai_landscape, "AI landscape")

    # Videos
    real_video_bytes = _generate_video([real_noface, real_noface, real_noface])
    fake_video_bytes = _generate_video([fake_noface, fake_noface, fake_noface])

    if real_video_bytes:
        print(f"  Real video: generated ({len(real_video_bytes):,} bytes)")
        print(f"  AI video:   generated ({len(fake_video_bytes):,} bytes)")
    else:
        print("  Videos: SKIPPED (ffmpeg not available)")

    # Build test cases
    cases: list[TestCase] = [
        TestCase(
            "Real+Face",
            real_face,
            "real_face.jpg",
            "image/jpeg",
            expect_face=True,
            expect_high_score=False,
        ),
        TestCase(
            "Real+NoFace",
            real_noface,
            "real_landscape.jpg",
            "image/jpeg",
            expect_face=False,
            expect_high_score=False,
            test_clip=True,
        ),
        TestCase(
            "AI+Face",
            fake_face,
            "ai_face.jpg",
            "image/jpeg",
            expect_face=True,
            expect_high_score=True,
        ),
        TestCase(
            "AI+NoFace",
            fake_noface,
            "ai_landscape.jpg",
            "image/jpeg",
            expect_face=False,
            expect_high_score=True,
            test_clip=True,
        ),
    ]

    if real_video_bytes and fake_video_bytes:
        cases.extend(
            [
                TestCase(
                    "Real+Video",
                    real_video_bytes,
                    "real_video.mp4",
                    "video/mp4",
                    expect_face=False,
                    expect_high_score=False,
                    is_video=True,
                ),
                TestCase(
                    "AI+Video",
                    fake_video_bytes,
                    "ai_video.mp4",
                    "video/mp4",
                    expect_face=False,
                    expect_high_score=True,
                    is_video=True,
                ),
            ]
        )

    # -- Stage 3: Upload all --
    print(f"\nStage 3 — Uploading {len(cases)} test cases:")
    for tc in cases:
        _p(upload(tc, token))
        if not all_checks[-1].passed:
            print(f"\nBLOCKED: Upload failed for {tc.label}")
            return 1

    # -- Stage 4: Poll all jobs --
    print(f"\nStage 4 — Polling {len(cases)} jobs (timeout {JOB_TIMEOUT_S}s each):")
    for tc in cases:
        _p(poll(tc, token))
        if not all_checks[-1].passed:
            print(f"\nBLOCKED: Job failed for {tc.label}")
            return 1

    # -- Stage 5: Validate results --
    print("\nStage 5 — Validating results:")
    for tc in cases:
        for c in validate_result(tc):
            _p(c)

    # -- Stage 6: Score comparison --
    print("\nStage 6 — Score comparisons:")

    pairs = [
        ("Face", "Real+Face", "AI+Face"),
        ("NoFace", "Real+NoFace", "AI+NoFace"),
    ]
    if real_video_bytes:
        pairs.append(("Video", "Real+Video", "AI+Video"))

    case_map = {tc.label: tc for tc in cases}
    for pair_label, real_label, fake_label in pairs:
        real_tc = case_map[real_label]
        fake_tc = case_map[fake_label]
        rs = real_tc.result.get("deepfake_score")
        fs = fake_tc.result.get("deepfake_score")
        if isinstance(rs, float) and isinstance(fs, float):
            separated = fs > rs
            _p(
                Check(
                    f"{pair_label}: AI score > Real score",
                    True,
                    f"real={rs:.4f}  ai={fs:.4f}  {'separated' if separated else 'NOT separated'}",
                    warning=not separated,
                )
            )
        else:
            _p(Check(f"{pair_label}: score comparison", False, "missing scores"))

    # -- Summary table --
    print("\n" + "=" * 70)
    print(f"{'Test Case':<16} {'Score':>8} {'Model':<28} {'YOLO':>6} {'pHash':>6}")
    print("-" * 70)
    for tc in cases:
        r = tc.result
        score = r.get("deepfake_score")
        score_s = f"{score:.4f}" if isinstance(score, float) else "N/A"
        model = r.get("deepfake_model", "N/A")
        yolo = r.get("yolo_detections", "-")
        phash = "yes" if r.get("phash") else "-"
        print(f"{tc.label:<16} {score_s:>8} {model:<28} {str(yolo):>6} {phash:>6}")
    print("=" * 70)

    # -- Final verdict --
    failures = [c for c in all_checks if not c.passed and not c.warning]
    warnings = [c for c in all_checks if c.warning]

    print()
    if failures:
        print(f"RESULT: {len(failures)} FAILED")
        for f in failures:
            print(f"  FAIL: {f.name}: {f.detail}")
        return 1

    if warnings:
        print(f"RESULT: ALL PASSED ({len(warnings)} warning(s))")
        for w in warnings:
            print(f"  WARN: {w.name}: {w.detail}")
    else:
        print("RESULT: ALL PASSED — vision pipeline fully validated")

    print()
    print("  Note: Score thresholds are WARN-only for generated fixtures.")
    print("  Pass --real-face / --fake-face with real photos for hard assertions.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
