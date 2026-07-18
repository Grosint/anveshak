#!/usr/bin/env python3
"""Seed deepfake media assets + vision results for IAF demo.

Generates placeholder images and inserts media_assets + vision_results rows
for existing IAF disinformation content items. Idempotent.

Run inside vision-worker container (has PIL + asyncpg + media volume):

    docker cp scripts/seed_iaf_deepfake_media.py anveshak-analyse-vision-worker-1:/tmp/
    docker exec anveshak-analyse-vision-worker-1 python /tmp/seed_iaf_deepfake_media.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:anveshak@postgres:5432/anveshak",
)
MEDIA_ROOT = Path("/app/media/media")

# ── Items to seed ──
ITEMS = [
    {
        "content_item_id": "iaf-ci-21",
        "media_id": "iaf-ma-deepfake-01",
        "vision_id": "iaf-vr-deepfake-01",
        "label": "FABRICATED: IAF Rafale Shootdown",
        "sublabel": "AI-Generated — Deepfake Score 0.94",
        "deepfake_score": 0.94,
        "synthetic_probability": 0.96,
        "deepfake_model": "dire-onnx",
        "exif_data": {
            "Software": "Runway Gen-3 Alpha",
            "GPS": "STRIPPED — no geolocation data",
            "CreateDate": "2026-06-17T14:23:00Z",
            "ImageDescription": "AI-generated combat footage",
            "Make": "Unknown",
            "Model": "Unknown",
            "anomalies": [
                "No camera EXIF — AI generation marker",
                "Software field: Runway Gen-3 Alpha",
                "Temporal artifacts in frame sequence",
            ],
        },
        "clip_labels": {
            "military_aircraft": 0.89,
            "explosion": 0.82,
            "combat": 0.78,
            "fabricated": 0.94,
        },
        "yolo_detections": [
            {"class": "aircraft", "confidence": 0.91, "bbox": [120, 80, 580, 320]},
            {"class": "explosion", "confidence": 0.85, "bbox": [200, 150, 500, 400]},
        ],
        "color": (180, 30, 30),  # dark red
    },
    {
        "content_item_id": "iaf-ci-26",
        "media_id": "iaf-ma-deepfake-02",
        "vision_id": "iaf-vr-deepfake-02",
        "label": "FABRICATED: HAL Tejas Crash",
        "sublabel": "AI-Generated — Deepfake Score 0.91",
        "deepfake_score": 0.91,
        "synthetic_probability": 0.93,
        "deepfake_model": "dire-onnx",
        "exif_data": {
            "Software": "Runway Gen-3 Alpha",
            "GPS": "STRIPPED",
            "CreateDate": "2026-06-18T09:15:00Z",
            "ImageDescription": "Repurposed Ukraine Su-25 footage",
            "anomalies": [
                "Frame signature matches Ukraine Su-25 incident footage",
                "Aircraft model swapped via AI inpainting",
                "Same temporal artifacts as Rafale deepfake",
            ],
        },
        "clip_labels": {
            "military_aircraft": 0.85,
            "crash": 0.79,
            "smoke_fire": 0.76,
            "fabricated": 0.91,
        },
        "yolo_detections": [
            {"class": "aircraft", "confidence": 0.88, "bbox": [100, 60, 600, 340]},
            {"class": "fire", "confidence": 0.82, "bbox": [250, 200, 550, 450]},
        ],
        "color": (160, 40, 20),  # dark red-orange
    },
    {
        "content_item_id": "iaf-ci-24",
        "media_id": "iaf-ma-deepfake-03",
        "vision_id": "iaf-vr-deepfake-03",
        "label": "REPOSTED: Rafale Shootdown (IG)",
        "sublabel": "AI-Generated — Deepfake Score 0.88",
        "deepfake_score": 0.88,
        "synthetic_probability": 0.90,
        "deepfake_model": "dire-onnx",
        "exif_data": {
            "Software": "Instagram 302.0",
            "GPS": "STRIPPED",
            "CreateDate": "2026-06-18T16:42:00Z",
            "ImageDescription": "Repost of fabricated Rafale footage via Instagram",
            "anomalies": [
                "Re-encoded via Instagram — compression artifacts overlay AI artifacts",
                "Original source: @fake_iaf_leaks Telegram channel",
            ],
        },
        "clip_labels": {
            "military_aircraft": 0.84,
            "explosion": 0.72,
            "social_media_screenshot": 0.65,
            "fabricated": 0.88,
        },
        "yolo_detections": [
            {"class": "aircraft", "confidence": 0.82, "bbox": [130, 90, 560, 310]},
        ],
        "color": (140, 50, 30),  # dark brown-red
    },
]


def generate_image(label: str, sublabel: str, color: tuple, path: Path) -> str:
    """Generate placeholder deepfake indicator image. Returns SHA-256 hash."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 800, 500
    img = Image.new("RGB", (width, height), color=(20, 20, 25))
    draw = ImageDraw.Draw(img)

    # Dark gradient background
    for y in range(height):
        r = int(20 + (color[0] - 20) * (y / height) * 0.3)
        g = int(20 + (color[1] - 20) * (y / height) * 0.3)
        b = int(25 + (color[2] - 25) * (y / height) * 0.3)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Warning border
    border_color = (220, 50, 50)
    for i in range(4):
        draw.rectangle([i, i, width - 1 - i, height - 1 - i], outline=border_color)

    # Try to use a decent font, fallback to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_small = font_large
        font_tiny = font_large

    # Warning triangle symbol area
    draw.text((width // 2 - 20, 40), "⚠", fill=(255, 60, 60), font=font_large)

    # Main label
    draw.text((width // 2 - 200, 100), label, fill=(255, 80, 80), font=font_large)

    # Sublabel
    draw.text((width // 2 - 160, 160), sublabel, fill=(255, 180, 100), font=font_small)

    # Diagonal watermark
    watermark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    for offset in range(-height, width + height, 120):
        wdraw.text((offset, height // 2 - 30), "AI GENERATED  ·  ", fill=(255, 50, 50, 40), font=font_small)
    watermark = watermark.rotate(30, expand=False, center=(width // 2, height // 2))
    img.paste(Image.alpha_composite(img.convert("RGBA"), watermark).convert("RGB"))

    # Bottom info bar
    draw.rectangle([0, height - 60, width, height], fill=(15, 15, 18))
    draw.text((20, height - 45), "ANVESHAK VISION MODULE  ·  DEEPFAKE DETECTION  ·  DIRE-ONNX", fill=(120, 120, 130), font=font_tiny)
    draw.text((width - 250, height - 45), "CLASSIFICATION: RESTRICTED", fill=(200, 80, 80), font=font_tiny)

    # Save
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "JPEG", quality=85)

    # Compute hash
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


async def main() -> None:
    import asyncpg

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
    assert pool is not None

    async with pool.acquire() as conn:
        for item in ITEMS:
            # Generate image
            storage_dir = MEDIA_ROOT / "iaf-topic-02" / "2026" / "06" / "17"
            img_path = storage_dir / f"{item['media_id']}.jpg"
            content_hash = generate_image(
                item["label"], item["sublabel"], item["color"], img_path,
            )
            storage_path = str(img_path)
            print(f"Generated: {storage_path} ({content_hash[:16]}...)")

            # Insert media_asset
            await conn.execute("""
                INSERT INTO media_assets (id, content_item_id, asset_type, storage_path, content_hash, exif_data, labels)
                VALUES ($1, $2, 'image', $3, $4, $5::jsonb,
                        '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb)
                ON CONFLICT (content_hash) DO UPDATE
                SET storage_path = EXCLUDED.storage_path,
                    exif_data = EXCLUDED.exif_data
            """,
                item["media_id"],
                item["content_item_id"],
                storage_path,
                content_hash,
                json.dumps(item["exif_data"]),
            )
            print(f"  media_asset: {item['media_id']}")

            # Insert vision_result
            await conn.execute("""
                INSERT INTO vision_results (
                    id, media_asset_id, deepfake_score, deepfake_model,
                    synthetic_probability, clip_labels, yolo_detections,
                    processed_at, labels
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8,
                          '{"classification":"RESTRICTED","domain":"info_warfare","owner_org":"iaf"}'::jsonb)
                ON CONFLICT (media_asset_id) DO UPDATE
                SET deepfake_score = EXCLUDED.deepfake_score,
                    deepfake_model = EXCLUDED.deepfake_model,
                    synthetic_probability = EXCLUDED.synthetic_probability,
                    clip_labels = EXCLUDED.clip_labels,
                    yolo_detections = EXCLUDED.yolo_detections,
                    processed_at = EXCLUDED.processed_at
            """,
                item["vision_id"],
                item["media_id"],
                item["deepfake_score"],
                item["deepfake_model"],
                item["synthetic_probability"],
                json.dumps(item["clip_labels"]),
                json.dumps(item["yolo_detections"]),
                datetime.now(timezone.utc),
            )
            print(f"  vision_result: {item['vision_id']} (deepfake={item['deepfake_score']})")

    await pool.close()
    print("\nDone. 3 deepfake media assets + vision results seeded.")


if __name__ == "__main__":
    asyncio.run(main())
