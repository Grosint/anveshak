#!/usr/bin/env python3
"""Seed script for Kerala Workflow 2: Multi-State Religious-Asset Misappropriation Trail.

SYNTHETIC SCENARIO ONLY. Does NOT reference any real ongoing case.

Usage:
    python -m demos.kerala_pathanamthitta.workflow_2_asset_trail.seed --replay
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

log = structlog.get_logger("demo.kerala_wf2_asset_trail")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

TOPIC_ID = "kl-asset-trail-001"

SOURCE_IDS = {
    "news_synthetic_1": "kl-at-src-manorama",
    "news_synthetic_2": "kl-at-src-hindu",
    "rti_doc_1": "kl-at-src-rti-1",
    "rti_doc_2": "kl-at-src-rti-2",
    "rti_doc_3": "kl-at-src-rti-3",
    "reddit_temples_1": "kl-at-src-reddit-temples1",
    "reddit_temples_2": "kl-at-src-reddit-temples2",
    "reddit_kerala": "kl-at-src-reddit-kerala",
    "reddit_finance": "kl-at-src-reddit-finance",
    "telegram_insider": "kl-at-src-tg-insider",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "news_synthetic_1": {"name": "Manorama Online", "url": "https://www.manoramaonline.com", "platform": "web", "credibility": 80.0},
    "news_synthetic_2": {"name": "The Hindu", "url": "https://www.thehindu.com", "platform": "web", "credibility": 85.0},
    "rti_doc_1": {"name": "RTI Kerala Portal", "url": "https://rti.kerala.gov.in", "platform": "web", "credibility": 90.0},
    "rti_doc_2": {"name": "RTI Kerala Portal", "url": "https://rti.kerala.gov.in", "platform": "web", "credibility": 90.0},
    "rti_doc_3": {"name": "RTI Kerala Portal", "url": "https://rti.kerala.gov.in", "platform": "web", "credibility": 88.0},
    "reddit_temples_1": {"name": "Reddit: r/IndianTemples", "url": "https://reddit.com/r/IndianTemples", "platform": "reddit", "credibility": 45.0},
    "reddit_temples_2": {"name": "Reddit: r/IndianTemples", "url": "https://reddit.com/r/IndianTemples", "platform": "reddit", "credibility": 48.0},
    "reddit_kerala": {"name": "Reddit: r/Kerala", "url": "https://reddit.com/r/Kerala", "platform": "reddit", "credibility": 52.0},
    "reddit_finance": {"name": "Reddit: r/IndianFinance", "url": "https://reddit.com/r/IndianFinance", "platform": "reddit", "credibility": 55.0},
    "telegram_insider": {"name": "Telegram: @temple_watch_kerala", "url": "https://t.me/temple_watch_kerala", "platform": "telegram", "credibility": 30.0},
}

LABELS = '{"classification": "RESTRICTED", "domain": "osint", "owner_org": "anveshak"}'


def _sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()

def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


async def _seed_db(pool: asyncpg.Pool) -> list[str]:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, TOPIC_ID, "Multi-State Temple Asset Misappropriation (Synthetic)",
            ["Sree Vaikundeswara", "gold misappropriation", "Idukki", "Chennai",
             "Bengaluru", "temple gold", "PMLA", "Ramachandran", "Sundaram", "Pillai"],
            3, "active", LABELS)

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
                VALUES ($1, $2, NOW()) ON CONFLICT DO NOTHING
            """, TOPIC_ID, sid)

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
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW(),NOW(),$12::jsonb)
                ON CONFLICT (content_hash) DO NOTHING RETURNING id
            """, item["id"], TOPIC_ID, source_id, item["raw_text"], item["clean_text"],
                item["language"], content_hash, item.get("url"),
                datetime.now(timezone.utc) - timedelta(days=5), credibility, "good",
                json.dumps(item["labels"]))
            if result:
                content_ids.append(result)

    if not content_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID)
            content_ids = [r["id"] for r in rows]
    return content_ids


async def _seed_signals(pool: asyncpg.Pool) -> int:
    signals = [
        {
            "id": "kl-at-signal-001",
            "signal_type": "multi_source_convergence",
            "description": (
                "Multi-source entity convergence: accused K. Ramachandran and routing pattern "
                "Idukki to Chennai to Bengaluru corroborated across RTI documents, news reports, "
                "and social media discussion. Recommend ED coordination for PMLA inquiry and "
                "asset freeze on identified accounts."
            ),
            "evidence": json.dumps({
                "corroborated_entities": ["K. Ramachandran", "P. Sundaram", "M. Naveen Pillai"],
                "routing_pattern": "Idukki → Chennai (Sowcarpet) → Bengaluru",
                "platforms": ["web", "reddit", "telegram"],
                "independent_source_count": 3,
                "estimated_value_inr": 28000000,
            }),
        },
        {
            "id": "kl-at-signal-002",
            "signal_type": "multi_source_convergence",
            "description": (
                "Financial anomaly detected: bank transfers totalling Rs 18.5 lakh from "
                "Bengaluru-linked account to temple administrative officer whose declared "
                "income is Rs 8.4 lakh. Disproportionate assets pattern. "
                "Recommend Vigilance inquiry and bank record preservation."
            ),
            "evidence": json.dumps({
                "transfer_amount_inr": 1850000,
                "declared_income_inr": 840000,
                "ratio": 2.2,
                "source_count": 3,
            }),
        },
    ]
    count = 0
    async with pool.acquire() as conn:
        for sig in signals:
            await conn.execute("""
                INSERT INTO signals (id, topic_id, signal_type, description, evidence, status, created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5::jsonb, 'new', NOW(), NOW(), $6::jsonb)
                ON CONFLICT (id) DO NOTHING
            """, sig["id"], TOPIC_ID, sig["signal_type"], sig["description"], sig["evidence"], LABELS)
            count += 1
    return count


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
        log.info("embeddings.waiting", done=count, total=len(content_ids))
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
                  "time_window_hours": 336, "credibility_min": 25.0})
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
    print("  ANVESHAK — Kerala W2: Multi-State Asset Misappropriation Trail")
    print("  [SYNTHETIC SCENARIO — no real case references]")
    print("=" * 70 + "\n")

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    print("[1/7] Seeding database...")
    content_ids = await _seed_db(pool)
    print(f"  -> {len(content_ids)} content items")

    print("[2/7] NLP analysis...")
    await _enqueue_analysis(content_ids)
    ok = await _poll_embeddings(pool, content_ids)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'}")

    print("[3/7] Narrative clustering...")
    await _enqueue_clustering()
    ok = await _poll_clusters(pool)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'}")

    print("[4/7] Seeding investigative signals...")
    sc = await _seed_signals(pool)
    print(f"  -> {sc} signal(s) seeded")

    print("[5/7] Authenticating...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_BASE}/api/v1/auth/login",
            json={"username": DEMO_USER, "password": DEMO_PASS})
        token = resp.json()["access_token"]

    print("[6/7] Generating intelligence brief...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED")
        await pool.close()
        return

    print("[7/7] Downloading PDF...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"http://localhost:8005/api/v1/reports/{report_id}/pdf")
        if resp.status_code == 200:
            path = OUTPUT_DIR / "workflow_2_report.pdf"
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
