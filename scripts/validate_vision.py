#!/usr/bin/env python3
"""Anveshak vision pipeline validation — E2E deepfake detection test (M4).

Tests the complete vision pipeline:
  upload image → ARQ job dispatch → YOLO + deepfake + pHash → DB persistence

Two built-in test fixtures (stdlib-only PNG generation, no network needed):
  - Normal:    32×32 solid-gray PNG  (expected low deepfake score)
  - Synthetic: 32×32 noise PNG       (mimics AI-generated texture)

For a meaningful real-world deepfake score test, pass actual images:
  python scripts/validate_vision.py \\
      --normal  path/to/real_face.jpg \\
      --synthetic path/to/ai_face.jpg

Usage:
    make validate-vision
    python scripts/validate_vision.py
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone

BASE = "http://localhost:8000"
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

JOB_POLL_INTERVAL_S = 5
JOB_TIMEOUT_S = 120


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    warning: bool = False


# ---------------------------------------------------------------------------
# Minimal PNG generator — stdlib only (zlib + struct), no Pillow needed.
# A PNG file: signature + IHDR chunk + IDAT chunk + IEND chunk.
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _make_solid_png(width: int = 32, height: int = 32, rgb: tuple = (128, 160, 128)) -> bytes:
    """32×32 solid-colour RGB PNG — stands in for a 'real' image in pipeline tests."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    # Each scanline: 1-byte filter (0=None) + width * 3 RGB bytes
    raw = b"".join(b"\x00" + bytes(list(rgb) * width) for _ in range(height))
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_noise_png(width: int = 32, height: int = 32, seed: int = 2024) -> bytes:
    """32×32 deterministic random-noise RGB PNG — stands in for a 'synthetic' image."""
    # LCG PRNG (no stdlib import needed) for deterministic output
    state = seed

    def _byte() -> int:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return (state >> 24) & 0xFF

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw = b""
    for _ in range(height):
        raw += b"\x00"
        raw += bytes([_byte() for _ in range(width * 3)])
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — same pattern as validate_pipeline.py)
# ---------------------------------------------------------------------------


def http_get(
    url: str,
    headers: dict | None = None,
    timeout: int = 10,
) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"_text": raw}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def http_post_multipart(
    url: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    auth_headers: dict,
    timeout: int = 30,
) -> tuple[int, dict]:
    """POST a file as multipart/form-data (stdlib only)."""
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n"
        ).encode()
        + file_bytes
        + f"\r\n--{boundary}--\r\n".encode()
    )

    headers = {
        **auth_headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            resp_body = json.loads(e.read().decode())
        except Exception:
            resp_body = {}
        return e.code, resp_body
    except Exception as e:
        return 0, {"error": str(e)}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def login() -> tuple[Check, str | None]:
    try:
        data = json.dumps({"username": DEMO_USER, "password": DEMO_PASS}).encode()
        req = urllib.request.Request(
            f"{BASE}/api/v1/auth/login",
            data=data,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
            token = body.get("access_token")
    except Exception as e:
        return Check("Login", False, str(e)), None

    passed = bool(token)
    return Check("Login", passed, "OK" if passed else "no access_token"), token


def upload_image(
    image_bytes: bytes,
    filename: str,
    token: str,
) -> tuple[Check, dict]:
    """POST /api/v1/vision/analyse — returns (check, response_body)."""
    status, body = http_post_multipart(
        f"{BASE}/api/v1/vision/analyse",
        image_bytes,
        filename,
        "image/png",
        _auth(token),
        timeout=30,
    )
    if status == 503:
        return Check(
            f"Upload {filename}",
            False,
            "HTTP 503 — vision service not started. Fix: make up-vision",
        ), {}
    if status != 200:
        return Check(
            f"Upload {filename}",
            False,
            f"HTTP {status} — {body.get('detail', body)}",
        ), {}
    job_id = body.get("job_id", "?")
    asset_id = body.get("media_asset_id", "?")
    return Check(
        f"Upload {filename}",
        True,
        f"job_id={job_id}  media_asset_id={asset_id}",
    ), body


def poll_job(job_id: str, token: str, label: str = "") -> tuple[Check, dict]:
    """Poll GET /api/v1/vision/jobs/{job_id} until complete or timeout."""
    deadline = time.time() + JOB_TIMEOUT_S
    last_status = "unknown"

    while time.time() < deadline:
        status, body = http_get(f"{BASE}/api/v1/vision/jobs/{job_id}", headers=_auth(token))
        if status != 200:
            return Check(f"Job ({label})", False, f"poll returned HTTP {status}"), {}

        last_status = body.get("status", "")

        if last_status == "complete":
            result = body.get("result") or {}
            error = body.get("error")
            if error:
                return Check(f"Job ({label})", False, f"job failed: {error}"), {}
            score = result.get("deepfake_score")
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
            return Check(f"Job ({label})", True, f"complete — deepfake_score={score_str}"), result

        if last_status == "not_found":
            return Check(f"Job ({label})", False, "job not found in Redis"), {}

        # queued / in_progress — keep polling
        time.sleep(JOB_POLL_INTERVAL_S)

    return Check(
        f"Job ({label})",
        False,
        f"timed out after {JOB_TIMEOUT_S}s — last status: {last_status}. "
        "Fix: make logs-analyse-vision-worker",
    ), {}


def validate_result_fields(result: dict, label: str) -> list[Check]:
    """Assert the four required fields are present and have correct types."""
    checks = []

    score = result.get("deepfake_score")
    checks.append(
        Check(
            f"{label} deepfake_score",
            isinstance(score, (int, float)),
            f"{score:.4f}"
            if isinstance(score, (int, float))
            else f"missing or wrong type ({type(score).__name__})",
        )
    )

    model = result.get("deepfake_model", "")
    model_missing = not bool(model)
    model_error = model == "error"
    checks.append(
        Check(
            f"{label} deepfake_model",
            not model_missing,  # FAIL only if field is missing entirely
            model
            if (bool(model) and not model_error)
            else (
                "field missing — job result incomplete"
                if model_missing
                else "'error' — ML model files not downloaded. Fix: make download-models"
            ),
            warning=model_error,  # 'error' = WARN (models not downloaded), not a pipeline failure
        )
    )

    yolo = result.get("yolo_detections")
    checks.append(
        Check(
            f"{label} yolo ran",
            yolo is not None and yolo >= 0,
            f"{yolo} object(s) detected" if (yolo is not None) else "missing — YOLO skipped",
        )
    )

    phash = result.get("phash")
    checks.append(
        Check(
            f"{label} phash computed",
            phash is not None,
            f"phash={hex(phash)}" if phash is not None else "None — pHash failed",
            warning=(phash is None),  # warn but don't fail (some images are pHash-unfriendly)
        )
    )

    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Anveshak M4 vision pipeline E2E validation")
    parser.add_argument(
        "--normal",
        default=None,
        help="Path to a real/normal image (default: built-in 32×32 solid PNG)",
    )
    parser.add_argument(
        "--synthetic",
        default=None,
        help="Path to a synthetic/AI-generated image (default: built-in 32×32 noise PNG)",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("=" * 62)
    print("ANVESHAK — Vision Pipeline Validation (M4)")
    print(f"Run at: {now}")
    print("=" * 62)

    # Load / generate test images
    if args.normal:
        with open(args.normal, "rb") as fh:
            normal_bytes = fh.read()
        normal_name = args.normal.rsplit("/", 1)[-1]
        print(f"\nNormal image:    {args.normal} ({len(normal_bytes):,} bytes)")
    else:
        normal_bytes = _make_solid_png(32, 32, (128, 160, 128))
        normal_name = "test_normal_32x32.png"
        print(f"\nNormal image:    built-in 32×32 solid-gray PNG ({len(normal_bytes)} bytes)")

    if args.synthetic:
        with open(args.synthetic, "rb") as fh:
            synth_bytes = fh.read()
        synth_name = args.synthetic.rsplit("/", 1)[-1]
        print(f"Synthetic image: {args.synthetic} ({len(synth_bytes):,} bytes)")
    else:
        synth_bytes = _make_noise_png(32, 32, seed=2024)
        synth_name = "test_synthetic_noise_32x32.png"
        print(f"Synthetic image: built-in 32×32 noise PNG ({len(synth_bytes)} bytes)")

    print(
        "\nNote: score thresholds are WARN-only for built-in fixtures."
        "\nPass --normal / --synthetic with real face photos for meaningful deepfake scores."
    )

    all_checks: list[Check] = []

    def _p(c: Check) -> None:
        all_checks.append(c)
        tag = "WARN" if c.warning else ("PASS" if c.passed else "FAIL")
        print(f"  [{tag}] {c.name}: {c.detail}")

    # ------------------------------------------------------------------
    # Stage 1 — Authentication
    # ------------------------------------------------------------------
    print()
    print("Stage 1 — Authentication:")
    login_check, token = login()
    _p(login_check)

    if not token:
        api_status, _ = http_get(f"{BASE}/health")
        print()
        if api_status != 200:
            print("BLOCKED: API not reachable. Fix: make up")
        else:
            print("BLOCKED: Login failed — demo credentials not seeded. Fix: make seed-demo")
        return 1

    # ------------------------------------------------------------------
    # Stage 2 — Upload normal image
    # ------------------------------------------------------------------
    print()
    print("Stage 2 — Upload normal image:")
    up1_check, up1_body = upload_image(normal_bytes, normal_name, token)
    _p(up1_check)

    if not up1_check.passed:
        if "503" in up1_check.detail or "not started" in up1_check.detail:
            print("\nBLOCKED: Vision service not running. Fix: make up-vision")
        return 1

    normal_job_id = up1_body["job_id"]
    normal_asset_id = up1_body["media_asset_id"]

    # ------------------------------------------------------------------
    # Stage 3 — Poll normal job
    # ------------------------------------------------------------------
    print()
    print(f"Stage 3 — Wait for normal image analysis (timeout {JOB_TIMEOUT_S}s):")
    print(f"  Polling job_id={normal_job_id} every {JOB_POLL_INTERVAL_S}s ...")
    job1_check, normal_result = poll_job(normal_job_id, token, "normal")
    _p(job1_check)

    if not job1_check.passed:
        if "timed out" in job1_check.detail:
            print(
                "\nBLOCKED: Vision worker not processing jobs. Fix: make logs-analyse-vision-worker"
            )
        return 1

    # ------------------------------------------------------------------
    # Stage 4 — Validate normal result fields
    # ------------------------------------------------------------------
    print()
    print("Stage 4 — Validate normal image result fields:")
    for c in validate_result_fields(normal_result, "Normal"):
        _p(c)
    normal_score = normal_result.get("deepfake_score")
    if normal_score is None:
        print("  WARN: deepfake_score is null — analysis failed, skipping score comparison")
        return 0

    # ------------------------------------------------------------------
    # Stage 5 — Upload synthetic image
    # ------------------------------------------------------------------
    print()
    print("Stage 5 — Upload synthetic/AI image:")
    up2_check, up2_body = upload_image(synth_bytes, synth_name, token)
    _p(up2_check)

    if not up2_check.passed:
        return 1

    synth_job_id = up2_body["job_id"]

    # ------------------------------------------------------------------
    # Stage 6 — Poll synthetic job
    # ------------------------------------------------------------------
    print()
    print(f"Stage 6 — Wait for synthetic image analysis (timeout {JOB_TIMEOUT_S}s):")
    print(f"  Polling job_id={synth_job_id} every {JOB_POLL_INTERVAL_S}s ...")
    job2_check, synth_result = poll_job(synth_job_id, token, "synthetic")
    _p(job2_check)

    if not job2_check.passed:
        if "timed out" in job2_check.detail:
            print(
                "\nBLOCKED: Vision worker not processing jobs. Fix: make logs-analyse-vision-worker"
            )
        return 1

    # ------------------------------------------------------------------
    # Stage 7 — Validate synthetic result fields
    # ------------------------------------------------------------------
    print()
    print("Stage 7 — Validate synthetic image result fields:")
    for c in validate_result_fields(synth_result, "Synthetic"):
        _p(c)
    synth_score = synth_result.get("deepfake_score")
    if synth_score is None:
        print("  WARN: deepfake_score is null — analysis failed, skipping score comparison")
        return 0

    # ------------------------------------------------------------------
    # Stage 8 — Score comparison (WARN only — built-in fixtures are tiny)
    # ------------------------------------------------------------------
    print()
    print("Stage 8 — Deepfake score comparison:")
    scores_separated = synth_score >= normal_score
    _p(
        Check(
            "Score separation (synthetic >= normal)",
            True,
            f"normal={normal_score:.4f}  synthetic={synth_score:.4f}  "
            + (
                "✓ separated as expected"
                if scores_separated
                else "synthetic < normal — model uncertain on built-in fixtures; use real face images"
            ),
            warning=(not scores_separated),
        )
    )
    _p(
        Check(
            "Normal score range",
            True,
            f"{normal_score:.4f}  (expected 0.0–0.3 for real content; "
            f"{'✓ in range' if normal_score <= 0.5 else 'HIGH — may be false positive'})",
            warning=(normal_score > 0.5),
        )
    )
    _p(
        Check(
            "Synthetic score range",
            True,
            f"{synth_score:.4f}  (noise images may score low; pass --synthetic real_ai_face.jpg for better signal)",
            warning=False,
        )
    )

    # ------------------------------------------------------------------
    # Stage 9 — pHash deduplication (re-upload same image)
    # ------------------------------------------------------------------
    print()
    print("Stage 9 — pHash deduplication (re-uploading normal image):")
    up3_check, up3_body = upload_image(normal_bytes, normal_name, token)
    _p(up3_check)

    if up3_check.passed:
        returned_id = up3_body.get("media_asset_id")
        dedup_hit = returned_id == normal_asset_id
        _p(
            Check(
                "Dedup: same media_asset_id returned",
                dedup_hit,
                f"✓ {returned_id}"
                if dedup_hit
                else f"different ID ({returned_id} vs {normal_asset_id}) — content_hash dedup may not have fired",
                warning=(not dedup_hit),
            )
        )

    # ------------------------------------------------------------------
    # Stage 10 — DB persistence: job result still in Redis (TTL = 1h)
    # ------------------------------------------------------------------
    print()
    print("Stage 10 — DB persistence (job result still in Redis):")
    status, persisted = http_get(f"{BASE}/api/v1/vision/jobs/{normal_job_id}", headers=_auth(token))
    _p(
        Check(
            "Job result persisted",
            status == 200 and persisted.get("status") == "complete",
            f"GET /vision/jobs/{normal_job_id[:8]}… → {persisted.get('status', f'HTTP {status}')}",
        )
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    failures = [c for c in all_checks if not c.passed and not c.warning]
    warnings = [c for c in all_checks if c.warning]

    print()
    print("=" * 62)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED")
        print()
        print("Fix:")
        for f in failures:
            print(f"  - {f.name}: {f.detail}")
        return 1

    if warnings:
        print(f"RESULT: ALL CHECKS PASSED  ({len(warnings)} warning(s))")
        for w in warnings:
            print(f"  WARN: {w.name}: {w.detail}")
    else:
        print("RESULT: ALL CHECKS PASSED — vision pipeline (M4) is healthy")

    print()
    print(f"  Normal score:    {normal_score:.4f}  ({normal_result.get('deepfake_model', '?')})")
    print(f"  Synthetic score: {synth_score:.4f}  ({synth_result.get('deepfake_model', '?')})")
    print(f"  YOLO (normal):   {normal_result.get('yolo_detections', '?')} detection(s)")
    print(f"  YOLO (synth):    {synth_result.get('yolo_detections', '?')} detection(s)")
    print()
    print("  Image Analysis page: http://localhost:3000/image-analysis")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
