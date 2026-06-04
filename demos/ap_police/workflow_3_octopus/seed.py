#!/usr/bin/env python3
"""Seed script for Workflow 3: OCTOPUS — AP Coastal Infiltration Risk.

Loads synthetic fixtures with pre-seeded vision analysis results.
Vision pipeline is NOT run live (too slow for demo) — results are pre-seeded.

Usage:
    python -m demos.ap_police.workflow_3_octopus.seed --replay
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import structlog

log = structlog.get_logger("demo.workflow_3_octopus")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

TOPIC_ID = "ap-octo-001-topic"

SOURCE_IDS = {
    "telegram_coast_te": "ap-octo-src-tg-te",
    "telegram_coast_ta": "ap-octo-src-tg-ta",
    "news_coast_1": "ap-octo-src-hindu",
    "news_coast_2": "ap-octo-src-ndtv",
    "news_coast_3": "ap-octo-src-deccan",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "telegram_coast_te": {"name": "Telegram: @fishcargo_ap (Telugu)", "url": "https://t.me/fishcargo_ap", "platform": "telegram", "credibility": 20.0},
    "telegram_coast_ta": {"name": "Telegram: @fishcargo_tamil", "url": "https://t.me/fishcargo_tamil", "platform": "telegram", "credibility": 18.0},
    "news_coast_1": {"name": "The Hindu", "url": "https://www.thehindu.com", "platform": "web", "credibility": 85.0},
    "news_coast_2": {"name": "NDTV", "url": "https://www.ndtv.com", "platform": "web", "credibility": 82.0},
    "news_coast_3": {"name": "Deccan Chronicle", "url": "https://www.deccanchronicle.com", "platform": "web", "credibility": 78.0},
}

LABELS = '{"classification": "SECRET", "domain": "osint", "owner_org": "anveshak"}'

# Pre-seeded vision analysis result (no live inference)
VISION_RESULT = {
    "deepfake_score": 0.12,  # Low — image is NOT deepfake
    "yolo_detections": [
        {"label": "boat", "confidence": 0.92, "bbox": [120, 80, 450, 320]},
        {"label": "person", "confidence": 0.78, "bbox": [200, 150, 260, 280]},
    ],
    "clip_labels": {
        "fishing-boat-at-commercial-port": 0.73,
        "fishing-boat-at-fishing-harbour": 0.21,
        "cargo-vessel": 0.06,
    },
    "exif_data": {
        "gps_stripped": True,
        "camera_model": "Unknown",
        "timestamp": "2026-05-01T02:15:00",
        "timestamp_anomaly": True,
        "notes": "GPS metadata stripped; timestamp indicates 2:15 AM — consistent with nighttime operations",
    },
    "phash_value": 12345678901234,
    "phash_duplicate_found": True,
    "phash_duplicate_source": "Previously flagged image from maritime smuggling database",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


async def _insert_topic(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
    """,
        TOPIC_ID,
        "AP Coastal Infiltration Risk — OCTOPUS",
        ["coastal security", "fishing boat", "smuggling", "Machilipatnam", "Nizampatnam",
         "Kakinada", "Visakhapatnam", "coast guard", "maritime", "infiltration"],
        2, "active", LABELS,
    )


async def _insert_sources(conn: asyncpg.Connection) -> None:
    for key, sid in SOURCE_IDS.items():
        meta = SOURCE_METADATA[key]
        await conn.execute("""
            INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                                 health_status, is_active, labels, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'up', true, $6::jsonb, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, sid, meta["name"], meta["url"], meta["platform"], meta["credibility"], LABELS)
        await conn.execute("""
            INSERT INTO topic_sources (topic_id, source_id, added_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT DO NOTHING
        """, TOPIC_ID, sid)


async def _insert_content(conn: asyncpg.Connection) -> list[str]:
    fixtures = json.loads((FIXTURES_DIR / "content.json").read_text())
    content_ids: list[str] = []
    for item in fixtures:
        content_hash = _sha256(item["clean_text"])
        source_id = SOURCE_IDS.get(item["source_key"], list(SOURCE_IDS.values())[0])
        credibility = SOURCE_METADATA.get(item["source_key"], {}).get("credibility", 50.0)
        result = await conn.fetchval("""
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                content_quality, created_at, updated_at, labels
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW(), $12::jsonb)
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING id
        """,
            item["id"], TOPIC_ID, source_id,
            item["raw_text"], item["clean_text"], item["language"],
            content_hash, item.get("url"), datetime.now(timezone.utc) - timedelta(days=1),
            credibility, "good", json.dumps(item["labels"]),
        )
        if result:
            content_ids.append(result)
    return content_ids


async def _insert_vision_result(conn: asyncpg.Connection) -> None:
    """Pre-seed a vision analysis job result for the boat image."""
    job_id = "ap-octo-vision-001"
    content_id = "ap-octo-content-001"
    payload = {"content_item_id": content_id, "media_asset_id": "ap-octo-media-001"}
    await conn.execute("""
        INSERT INTO analysis_jobs (
            id, job_type, topic_id, status, payload, result,
            created_at, updated_at, labels
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, NOW(), NOW(), $7::jsonb)
        ON CONFLICT (id) DO NOTHING
    """,
        job_id, "vision_analysis", TOPIC_ID, "completed",
        json.dumps(payload), json.dumps(VISION_RESULT), LABELS,
    )
    log.info("vision_result.inserted", job_id=job_id, deepfake_score=VISION_RESULT["deepfake_score"])


async def _enqueue_analysis_jobs(content_ids: list[str]) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    for cid in content_ids:
        await redis.enqueue_job("analyse_content", cid, _queue_name="arq:analyst")
    await redis.close()


async def _poll_embeddings(pool: asyncpg.Pool, content_ids: list[str], timeout: int = 180) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE id = ANY($1) AND embedding IS NOT NULL",
                content_ids,
            )
        if count >= len(content_ids):
            return True
        await asyncio.sleep(5)
    return False


async def _enqueue_clustering(topic_id: str) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("run_clustering", topic_id, _queue_name="arq:analyst")
    await redis.close()


async def _poll_clusters(pool: asyncpg.Pool, topic_id: str, timeout: int = 120) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1 AND item_count > 0",
                topic_id,
            )
        if count and count >= 1:
            return True
        await asyncio.sleep(5)
    return False


async def _authenticate() -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"username": DEMO_USER, "password": DEMO_PASS},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _generate_report(token: str) -> str | None:
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "topic_id": TOPIC_ID,
                "report_type": "intelligence_brief",
                "time_window_hours": 168,
                "credibility_min": 15.0,
            },
        )
        if resp.status_code not in (201, 202):
            log.error("report.create_failed", status=resp.status_code)
            return None
        data = resp.json()
        report_id = data.get("report_id") or data.get("id")

        timeout = 600
        while time.monotonic() - t0 < timeout:
            resp = await client.get(
                f"{API_BASE}/api/v1/reports/{report_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                rdata = resp.json()
                status = rdata.get("generation_status") or ("complete" if rdata.get("generated_at") else "pending")
                if status == "complete":
                    return report_id
                if status == "failed":
                    return None
            await asyncio.sleep(10)
    return None


async def _download_pdf(token: str, report_id: str) -> str | None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            "http://localhost:8005/api/v1/reports/{}/pdf".format(report_id),
        )
        if resp.status_code == 200:
            pdf_path = OUTPUT_DIR / "workflow_3_report.pdf"
            pdf_path.write_bytes(resp.content)
            return str(pdf_path)
    return None


async def run(live: bool = False) -> None:
    if live and not os.getenv("ANVESHAK_ALLOW_LIVE"):
        print("ERROR: --live requires ANVESHAK_ALLOW_LIVE=1")
        sys.exit(1)

    total_t0 = time.monotonic()
    print("\n" + "=" * 70)
    print("  ANVESHAK — Workflow 3: OCTOPUS — AP Coastal Infiltration Risk")
    print("  Mode: REPLAY (fixtures)" if not live else "  Mode: LIVE")
    print("=" * 70 + "\n")

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    print("[1/8] Seeding database...")
    async with pool.acquire() as conn:
        await _insert_topic(conn)
        await _insert_sources(conn)
        content_ids = await _insert_content(conn)
        await _insert_vision_result(conn)

    if not content_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID)
            content_ids = [r["id"] for r in rows]
    print(f"  -> {len(content_ids)} content items + 1 vision result ready")

    print("[2/8] Running NLP analysis (incl. Telugu translation)...")
    t0 = time.monotonic()
    await _enqueue_analysis_jobs(content_ids)
    ok = await _poll_embeddings(pool, content_ids, timeout=180)
    print(f"  -> Analysis complete in {_elapsed(t0)}" if ok else "  -> WARNING: timeout")

    print("[3/8] Running narrative clustering...")
    t0 = time.monotonic()
    await _enqueue_clustering(TOPIC_ID)
    ok = await _poll_clusters(pool, TOPIC_ID, timeout=120)
    print(f"  -> Clustering complete in {_elapsed(t0)}" if ok else "  -> WARNING: timeout")

    print("[4/8] Vision analysis results (pre-seeded)...")
    print(f"  -> Deepfake score: {VISION_RESULT['deepfake_score']} (low — image is authentic)")
    print(f"  -> YOLO detections: boat (0.92), person (0.78)")
    print(f"  -> CLIP: fishing-boat-at-commercial-port (0.73)")
    print(f"  -> EXIF: GPS stripped, timestamp 2:15 AM (anomalous)")
    print(f"  -> pHash: duplicate found in prior database")

    print("[5/8] Checking signals...")
    async with pool.acquire() as conn:
        signal_count = await conn.fetchval("SELECT COUNT(*) FROM signals WHERE topic_id = $1", TOPIC_ID)
    print(f"  -> {signal_count} signal(s) detected")

    print("[6/8] Authenticating...")
    token = await _authenticate()

    print("[7/8] Generating intelligence brief...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED")
        await pool.close()
        return

    print("[8/8] Downloading PDF...")
    pdf_path = await _download_pdf(token, report_id)

    await pool.close()
    print("\n" + "=" * 70)
    print(f"  WORKFLOW 3 COMPLETE — {_elapsed(total_t0)}")
    print(f"  Report ID: {report_id}")
    if pdf_path:
        print(f"  PDF: {pdf_path}")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Workflow 3: OCTOPUS")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay", action="store_true", default=True)
    args = parser.parse_args()
    asyncio.run(run(live=args.live))


if __name__ == "__main__":
    main()
