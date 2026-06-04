#!/usr/bin/env python3
"""Seed script for Kerala Workflow 3: SGI/Deepfake Detection — Sabarimala Season Disinformation.

Vision results are pre-seeded (no live inference on CPU).

Usage:
    python -m demos.kerala_pathanamthitta.workflow_3_sgi_deepfake.seed --replay
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import structlog

log = structlog.get_logger("demo.kerala_wf3_sgi")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

TOPIC_ID = "kl-sgi-deepfake-001"
PRIOR_TOPIC_ID = "kl-sgi-prior-001"
ORG_ID = os.getenv("DEMO_ORG_ID", "org-anshul")

SOURCE_IDS = {
    "telegram_disinfo_ml": "kl-sgi-src-tg-ml",
    "telegram_disinfo_hi": "kl-sgi-src-tg-hi",
    "blog_inflammatory": "kl-sgi-src-blog",
    "reddit_kerala_1": "kl-sgi-src-reddit-kl1",
    "reddit_kerala_2": "kl-sgi-src-reddit-kl2",
    "reddit_india": "kl-sgi-src-reddit-india",
    "reddit_disinfo": "kl-sgi-src-reddit-media",
    "reddit_factcheck": "kl-sgi-src-reddit-fact",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "telegram_disinfo_ml": {"name": "Telegram: @sabarimala_truth_ml", "url": "https://t.me/sabarimala_truth_ml", "platform": "telegram", "credibility": 15.0},
    "telegram_disinfo_hi": {"name": "Telegram: @sabarimala_truth_hindi", "url": "https://t.me/sabarimala_truth_hindi", "platform": "telegram", "credibility": 15.0},
    "blog_inflammatory": {"name": "Truth of Kerala Blog", "url": "https://truthofkerala.blogspot.com", "platform": "web", "credibility": 12.0},
    "reddit_kerala_1": {"name": "Reddit: r/Kerala", "url": "https://reddit.com/r/Kerala", "platform": "reddit", "credibility": 55.0},
    "reddit_kerala_2": {"name": "Reddit: r/Kerala (verification)", "url": "https://reddit.com/r/Kerala", "platform": "reddit", "credibility": 60.0},
    "reddit_india": {"name": "Reddit: r/india", "url": "https://reddit.com/r/india", "platform": "reddit", "credibility": 50.0},
    "reddit_disinfo": {"name": "Reddit: r/IndianMediaAnalysis", "url": "https://reddit.com/r/IndianMediaAnalysis", "platform": "reddit", "credibility": 58.0},
    "reddit_factcheck": {"name": "Reddit: r/Kerala (fact-check)", "url": "https://reddit.com/r/Kerala", "platform": "reddit", "credibility": 65.0},
}

LABELS = '{"classification": "RESTRICTED", "domain": "osint", "owner_org": "anveshak"}'

# Pre-seeded vision analysis results (3 images)
VISION_RESULTS = [
    {
        "id": "kl-sgi-vision-001",
        "description": "Staged victim face photo — HIGH deepfake",
        "result": {
            "deepfake_score": 0.87,
            "yolo_detections": [
                {"label": "person", "confidence": 0.94, "bbox": [50, 30, 300, 400]},
            ],
            "clip_labels": {
                "injured-person-outdoor": 0.31,
                "posed-portrait-indoor": 0.62,
                "crowd-scene": 0.07,
            },
            "exif_data": {
                "gps_stripped": True,
                "camera_model": "iPhone 13 Pro",
                "timestamp": "2024-11-15T14:30:00",
                "timestamp_anomaly": True,
                "notes": "Image claims to be from 2026 Mandalam season but EXIF shows November 2024",
            },
            "phash_value": 98765432109876,
            "phash_duplicate_found": False,
        },
    },
    {
        "id": "kl-sgi-vision-002",
        "description": "Doctored crowd scene at Pamba — MEDIUM deepfake + pHash hit",
        "result": {
            "deepfake_score": 0.72,
            "yolo_detections": [
                {"label": "person", "confidence": 0.88, "bbox": [10, 50, 200, 350]},
                {"label": "person", "confidence": 0.82, "bbox": [180, 60, 380, 360]},
                {"label": "person", "confidence": 0.76, "bbox": [350, 70, 500, 340]},
            ],
            "clip_labels": {
                "crowd-at-outdoor-religious-site": 0.28,
                "indoor-event-hall": 0.65,
                "outdoor-riverside": 0.07,
            },
            "exif_data": {
                "gps_stripped": False,
                "gps_lat": 9.58,
                "gps_lon": 76.52,
                "gps_anomaly": True,
                "camera_model": "Samsung Galaxy S22",
                "timestamp": "2024-12-20T09:15:00",
                "timestamp_anomaly": True,
                "notes": "GPS points to Kottayam event hall, NOT Pamba. Timestamp is Dec 2024.",
            },
            "phash_value": 11223344556677,
            "phash_duplicate_found": True,
            "phash_duplicate_source": "Known stock photo from Getty Images — previously flagged in 2024 fact-check database",
        },
    },
    {
        "id": "kl-sgi-vision-003",
        "description": "Legitimate press photo — LOW deepfake (authentic)",
        "result": {
            "deepfake_score": 0.08,
            "yolo_detections": [
                {"label": "person", "confidence": 0.91, "bbox": [100, 80, 350, 400]},
                {"label": "religious structure", "confidence": 0.85, "bbox": [0, 0, 500, 200]},
            ],
            "clip_labels": {
                "crowd-at-outdoor-religious-site": 0.82,
                "indoor-event-hall": 0.04,
                "outdoor-riverside": 0.14,
            },
            "exif_data": {
                "gps_stripped": False,
                "gps_lat": 9.43,
                "gps_lon": 77.08,
                "gps_anomaly": False,
                "camera_model": "Canon EOS R5",
                "timestamp": "2026-11-20T10:30:00",
                "timestamp_anomaly": False,
                "notes": "GPS matches Sannidhanam. Timestamp consistent with Mandalam 2026. Professional camera — likely press photographer.",
            },
            "phash_value": 55667788990011,
            "phash_duplicate_found": False,
        },
    },
]


DEMO_SIGNALS = [
    {
        "id": "kl-sgi-signal-001",
        "signal_type": "multi_source_convergence",
        "description": (
            "SGI detection alert: 2 of 3 analysed images show deepfake indicators "
            "(scores 0.87 and 0.72) with EXIF timestamp anomalies and GPS mismatches. "
            "Coordinated disinformation campaign detected across Malayalam and Hindi "
            "Telegram channels (@sabarimala_truth_ml, @sabarimala_truth_hindi). "
            "Recommend platform takedown request and FIR under IT Act 66D + BNS 196."
        ),
        "evidence": json.dumps({
            "deepfake_images": 2,
            "deepfake_scores": [0.87, 0.72],
            "phash_duplicate_found": True,
            "channels": ["@sabarimala_truth_ml", "@sabarimala_truth_hindi"],
            "platforms": ["telegram", "web", "reddit"],
            "independent_source_count": 3,
        }),
    },
    {
        "id": "kl-sgi-signal-002",
        "signal_type": "multi_source_convergence",
        "description": (
            "Cross-platform disinformation amplification: identical inflammatory narrative "
            "('violence at Pamba') propagated in Malayalam (local reach) and Hindi (national reach) "
            "simultaneously. 5 Reddit users independently flagged the images as recycled/manipulated. "
            "Pattern matches seasonal disinformation playbook active since 2019. "
            "Recommend Special Branch monitoring and preemptive media briefing with fact-check evidence."
        ),
        "evidence": json.dumps({
            "narrative": "violence at Pamba",
            "languages": ["ml", "hi"],
            "reddit_flagged_count": 5,
            "platforms": ["telegram", "reddit", "web"],
            "independent_source_count": 3,
        }),
    },
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


async def _seed_db(pool: asyncpg.Pool) -> list[str]:
    async with pool.acquire() as conn:
        # Prior topic for convergence
        await conn.execute("""
            INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, org_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, NOW())
            ON CONFLICT (id) DO NOTHING
        """, PRIOR_TOPIC_ID, "Pilgrim Season Tension Amplification",
            ["Sabarimala", "communal", "pilgrimage", "disinformation", "fake news"],
            3, "active", LABELS, ORG_ID, datetime.now(timezone.utc) - timedelta(days=60))

        # Main topic
        await conn.execute("""
            INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, org_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, TOPIC_ID, "Sabarimala Season Disinformation + SGI Detection",
            ["Sabarimala", "deepfake", "SGI", "disinformation", "Mandalam", "Pamba",
             "Nilackal", "fake photo", "communal tension", "Kerala Cyber Safety Protocol"],
            2, "active", LABELS, ORG_ID)

        # Sources
        for key, sid in SOURCE_IDS.items():
            meta = SOURCE_METADATA[key]
            await conn.execute("""
                INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                                     health_status, is_active, labels, org_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, 'up', true, $6::jsonb, $7, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """, sid, meta["name"], meta["url"], meta["platform"], meta["credibility"], LABELS, ORG_ID)
            await conn.execute("""
                INSERT INTO topic_sources (topic_id, source_id, added_at)
                VALUES ($1, $2, NOW()) ON CONFLICT DO NOTHING
            """, TOPIC_ID, sid)
            await conn.execute("""
                INSERT INTO org_sources (org_id, source_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, ORG_ID, sid)

        # Content
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
                    content_quality, created_at, updated_at, labels, org_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW(),NOW(),$12::jsonb,$13)
                ON CONFLICT (content_hash) DO NOTHING RETURNING id
            """, item["id"], TOPIC_ID, source_id, item["raw_text"], item["clean_text"],
                item["language"], content_hash, item.get("url"),
                datetime.now(timezone.utc) - timedelta(days=2), credibility, "good",
                json.dumps(item["labels"]), ORG_ID)
            if result:
                content_ids.append(result)

        # Vision results (pre-seeded)
        for vr in VISION_RESULTS:
            payload = {"content_item_id": "kl-sgi-content-001", "media_asset_id": vr["id"]}
            await conn.execute("""
                INSERT INTO analysis_jobs (id, job_type, topic_id, status, payload, result, created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, NOW(), NOW(), $7::jsonb)
                ON CONFLICT (id) DO NOTHING
            """, vr["id"], "vision_analysis", TOPIC_ID, "completed",
                json.dumps(payload), json.dumps(vr["result"]), LABELS)

    if not content_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID)
            content_ids = [r["id"] for r in rows]
    return content_ids


async def _enqueue_analysis(content_ids: list[str]) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    for cid in content_ids:
        await redis.enqueue_job("analyse_content", cid, _queue_name="arq:analyst")
    await redis.aclose()


async def _poll_embeddings(pool: asyncpg.Pool, content_ids: list[str], timeout: int = 240) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE id = ANY($1) AND embedding IS NOT NULL", content_ids)
        if count >= len(content_ids):
            return True
        log.info("embeddings.waiting", done=count, total=len(content_ids), elapsed=_elapsed(t0))
        await asyncio.sleep(5)
    return False


async def _enqueue_clustering() -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("run_clustering", TOPIC_ID, _queue_name="arq:analyst")
    await redis.aclose()


async def _poll_clusters(pool: asyncpg.Pool, timeout: int = 120) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1 AND item_count > 0", TOPIC_ID)
        if count and count >= 1:
            return True
        await asyncio.sleep(5)
    return False


async def _generate_report(token: str) -> str | None:
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_BASE}/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={"topic_id": TOPIC_ID, "report_type": "intelligence_brief",
                  "time_window_hours": 168, "credibility_min": 10.0})
        if resp.status_code not in (201, 202):
            return None
        report_id = resp.json().get("report_id") or resp.json().get("id")
        timeout = 600
        while time.monotonic() - t0 < timeout:
            resp = await client.get(f"{API_BASE}/api/v1/reports/{report_id}",
                headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                rdata = resp.json()
                if rdata.get("generated_at"):
                    return report_id
                if rdata.get("generation_error"):
                    return None
            await asyncio.sleep(10)
    return None


async def run(live: bool = False) -> None:
    if live and not os.getenv("ANVESHAK_ALLOW_LIVE"):
        sys.exit("ERROR: --live requires ANVESHAK_ALLOW_LIVE=1")

    total_t0 = time.monotonic()
    print("\n" + "=" * 70)
    print("  ANVESHAK — Kerala W3: SGI/Deepfake Detection")
    print("=" * 70 + "\n")

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    print("[1/8] Seeding database + vision results...")
    content_ids = await _seed_db(pool)
    print(f"  -> {len(content_ids)} content items + 3 vision results")

    print("[2/8] NLP analysis (Malayalam + Hindi translation)...")
    await _enqueue_analysis(content_ids)
    ok = await _poll_embeddings(pool, content_ids)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'}")

    print("[3/8] Narrative clustering...")
    await _enqueue_clustering()
    ok = await _poll_clusters(pool)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'}")

    print("[4/8] Vision analysis (pre-seeded)...")
    for vr in VISION_RESULTS:
        score = vr["result"]["deepfake_score"]
        level = "HIGH" if score > 0.7 else "MEDIUM" if score > 0.4 else "LOW"
        print(f"  -> {vr['description']}: score={score} ({level})")

    print("[5/8] Seeding investigative signals...")
    async with pool.acquire() as conn:
        sc = 0
        for sig in DEMO_SIGNALS:
            await conn.execute("""
                INSERT INTO signals (id, topic_id, signal_type, description, evidence, status, created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5::jsonb, 'new', NOW(), NOW(), $6::jsonb)
                ON CONFLICT (id) DO NOTHING
            """, sig["id"], TOPIC_ID, sig["signal_type"], sig["description"], sig["evidence"], LABELS)
            sc += 1
    print(f"  -> {sc} signal(s) seeded")

    print("[6/8] Authenticating...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_BASE}/api/v1/auth/login",
            json={"username": DEMO_USER, "password": DEMO_PASS})
        token = resp.json()["access_token"]

    print("[7/8] Generating intelligence brief...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED")
        await pool.close()
        return

    print("[8/8] Downloading PDF...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"http://localhost:8005/api/v1/reports/{report_id}/pdf")
        if resp.status_code == 200:
            path = OUTPUT_DIR / "workflow_3_report.pdf"
            path.write_bytes(resp.content)
            print(f"  -> PDF: {path}")

    await pool.close()
    print(f"\n{'='*70}\n  COMPLETE — {_elapsed(total_t0)}\n{'='*70}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay", action="store_true", default=True)
    asyncio.run(run(live=parser.parse_args().live))


if __name__ == "__main__":
    main()
