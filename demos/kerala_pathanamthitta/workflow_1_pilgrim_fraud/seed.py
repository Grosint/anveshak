#!/usr/bin/env python3
"""Seed script for Kerala Workflow 1: Pilgrim Cyber Fraud Network.

Usage:
    python -m demos.kerala_pathanamthitta.workflow_1_pilgrim_fraud.seed --replay
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import structlog

log = structlog.get_logger("demo.kerala_wf1_pilgrim_fraud")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
REPORTER_BASE = os.getenv("REPORTER_BASE", "http://localhost:8005")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

TOPIC_ID = "kl-pilgrim-fraud-001"

SOURCE_IDS = {
    "telegram_booking_1": "kl-pf-src-tg-vip",
    "telegram_booking_2": "kl-pf-src-tg-mandalam",
    "telegram_booking_3": "kl-pf-src-tg-pamba",
    "reddit_kerala": "kl-pf-src-reddit-kerala",
    "reddit_india": "kl-pf-src-reddit-india",
    "reddit_legal": "kl-pf-src-reddit-legal",
    "news_manorama": "kl-pf-src-manorama",
    "news_hindu": "kl-pf-src-hindu",
    "news_mathrubhumi": "kl-pf-src-mathrubhumi",
    "news_ndtv": "kl-pf-src-ndtv",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "telegram_booking_1": {"name": "Telegram: @sabarimala_booking_vip", "url": "https://t.me/sabarimala_booking_vip", "platform": "telegram", "credibility": 18.0},
    "telegram_booking_2": {"name": "Telegram: @mandalam_yatra_deals", "url": "https://t.me/mandalam_yatra_deals", "platform": "telegram", "credibility": 20.0},
    "telegram_booking_3": {"name": "Telegram: @pamba_darshan_group", "url": "https://t.me/pamba_darshan_group", "platform": "telegram", "credibility": 22.0},
    "reddit_kerala": {"name": "Reddit: r/Kerala", "url": "https://reddit.com/r/Kerala", "platform": "reddit", "credibility": 52.0},
    "reddit_india": {"name": "Reddit: r/india", "url": "https://reddit.com/r/india", "platform": "reddit", "credibility": 48.0},
    "reddit_legal": {"name": "Reddit: r/LegalAdviceIndia", "url": "https://reddit.com/r/LegalAdviceIndia", "platform": "reddit", "credibility": 52.0},
    "news_manorama": {"name": "Manorama Online", "url": "https://www.manoramaonline.com", "platform": "web", "credibility": 80.0},
    "news_hindu": {"name": "The Hindu", "url": "https://www.thehindu.com", "platform": "web", "credibility": 85.0},
    "news_mathrubhumi": {"name": "Mathrubhumi", "url": "https://www.mathrubhumi.com", "platform": "web", "credibility": 78.0},
    "news_ndtv": {"name": "NDTV", "url": "https://www.ndtv.com", "platform": "web", "credibility": 82.0},
}

LABELS = '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'


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
        "Sabarimala Pilgrim Cyber Fraud Network",
        ["Sabarimala", "pilgrim fraud", "fake booking", "darshanmoksha", "Mandalam",
         "Pamba", "UPI scam", "pilgrim scam", "Kerala cyber crime", "Pathanamthitta"],
        3, "active", LABELS,
    )
    log.info("topic.inserted", topic_id=TOPIC_ID)


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
    log.info("sources.inserted", count=len(SOURCE_IDS))


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
            content_hash, item.get("url"), datetime.now(UTC) - timedelta(days=3),
            credibility, "good", json.dumps(item["labels"]),
        )
        if result:
            content_ids.append(result)
    log.info("content.inserted", count=len(content_ids))
    return content_ids


async def _enqueue_analysis_jobs(content_ids: list[str]) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    for cid in content_ids:
        await redis.enqueue_job("analyse_content", cid, _queue_name="arq:analyst")
    log.info("arq.enqueued", count=len(content_ids))
    await redis.aclose()


async def _poll_embeddings(pool: asyncpg.Pool, content_ids: list[str], timeout: int = 240) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE id = ANY($1) AND embedding IS NOT NULL",
                content_ids,
            )
        if count >= len(content_ids):
            log.info("embeddings.complete", count=count, elapsed=_elapsed(t0))
            return True
        log.info("embeddings.waiting", done=count, total=len(content_ids), elapsed=_elapsed(t0))
        await asyncio.sleep(5)
    log.warning("embeddings.timeout")
    return False


async def _enqueue_clustering(topic_id: str) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("run_clustering", topic_id, _queue_name="arq:analyst")
    await redis.aclose()


async def _poll_clusters(pool: asyncpg.Pool, topic_id: str, timeout: int = 120) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1 AND item_count > 0",
                topic_id,
            )
        if count and count >= 1:
            log.info("clusters.complete", count=count, elapsed=_elapsed(t0))
            return True
        await asyncio.sleep(5)
    log.warning("clusters.timeout")
    return False


async def _seed_signals(pool: asyncpg.Pool) -> int:
    """Pre-seed investigative signals for demo reliability."""
    signals = [
        {
            "id": "kl-pf-signal-001",
            "signal_type": "multi_source_convergence",
            "description": (
                "Cross-platform corroboration: UPI handle pilgrimstay@ybl and domain "
                "darshanmokshahomestay.in confirmed across 3 independent platforms "
                "(Telegram, Reddit, web news). Recommend immediate investigation of "
                "UPI mule account holder and domain registrar records."
            ),
            "evidence": json.dumps({
                "corroborated_entities": ["pilgrimstay@ybl", "darshanmokshahomestay.in"],
                "platforms": ["telegram", "reddit", "web"],
                "independent_source_count": 3,
                "content_item_count": 8,
            }),
        },
        {
            "id": "kl-pf-signal-002",
            "signal_type": "multi_source_convergence",
            "description": (
                "Multi-state suspect network detected: operators in Nuh (Haryana) using "
                "VoIP numbers with Kerala area codes. UPI mule entity registered in Tamil Nadu. "
                "Fund routing through Karnataka accounts. Recommend inter-state coordination "
                "with Haryana Cyber Cell and Tamil Nadu ED."
            ),
            "evidence": json.dumps({
                "corroborated_entities": ["+91-9847123456", "Nuh, Haryana"],
                "platforms": ["reddit", "web"],
                "states_involved": ["Kerala", "Tamil Nadu", "Karnataka", "Haryana"],
                "independent_source_count": 3,
            }),
        },
        {
            "id": "kl-pf-signal-003",
            "signal_type": "multi_source_convergence",
            "description": (
                "Victim count threshold breached: 80+ complaints registered across "
                "Kerala, Tamil Nadu, and Karnataka. Aggregate loss Rs 65 lakh. "
                "Pattern matches organised pilgrim-season fraud ring. "
                "Recommend escalation to I4C and freezing of UPI mule accounts."
            ),
            "evidence": json.dumps({
                "victim_count": 80,
                "aggregate_loss_inr": 6500000,
                "states_affected": ["Kerala", "Tamil Nadu", "Karnataka"],
                "source_count": 4,
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
            """, sig["id"], TOPIC_ID, sig["signal_type"], sig["description"],
                sig["evidence"], LABELS)
            count += 1
    log.info("signals.seeded", count=count)
    return count


async def _adjust_credibility(token: str) -> None:
    source_id = SOURCE_IDS["telegram_booking_1"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{API_BASE}/api/v1/sources/{source_id}/credibility",
            headers={"Authorization": f"Bearer {token}"},
            params={"new_score": 10.0, "reason": "Confirmed fraud operation — site darshanmokshahomestay.in verified as fake"},
        )
        if resp.status_code == 200:
            log.info("credibility.adjusted", source_id=source_id, new_score=10.0)


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
            json={"topic_id": TOPIC_ID, "report_type": "intelligence_brief",
                  "time_window_hours": 168, "credibility_min": 15.0},
        )
        if resp.status_code not in (201, 202):
            log.error("report.create_failed", status=resp.status_code)
            return None
        data = resp.json()
        report_id = data.get("report_id") or data.get("id")
        log.info("report.created", report_id=report_id)

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
                    log.info("report.complete", report_id=report_id, elapsed=_elapsed(t0))
                    return report_id
                if status == "failed":
                    log.error("report.failed", error=rdata.get("generation_error"))
                    return None
            log.info("report.polling", elapsed=_elapsed(t0))
            await asyncio.sleep(10)
    return None


async def _download_pdf(report_id: str) -> str | None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            "http://localhost:8005/api/v1/reports/{}/pdf".format(report_id),
        )
        if resp.status_code == 200:
            pdf_path = OUTPUT_DIR / "workflow_1_report.pdf"
            pdf_path.write_bytes(resp.content)
            log.info("pdf.downloaded", path=str(pdf_path))
            return str(pdf_path)
    return None


async def run(live: bool = False) -> None:
    if live and not os.getenv("ANVESHAK_ALLOW_LIVE"):
        print("ERROR: --live requires ANVESHAK_ALLOW_LIVE=1")
        sys.exit(1)

    total_t0 = time.monotonic()
    print("\n" + "=" * 70)
    print("  ANVESHAK — Kerala W1: Sabarimala Pilgrim Cyber Fraud Network")
    print("  Mode: REPLAY (fixtures)" if not live else "  Mode: LIVE")
    print("=" * 70 + "\n")

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    print("[1/8] Seeding database...")
    async with pool.acquire() as conn:
        await _insert_topic(conn)
        await _insert_sources(conn)
        content_ids = await _insert_content(conn)

    if not content_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID)
            content_ids = [r["id"] for r in rows]
    print(f"  -> {len(content_ids)} content items ready")

    print("[2/8] Running NLP analysis (Malayalam translation + NER)...")
    t0 = time.monotonic()
    await _enqueue_analysis_jobs(content_ids)
    ok = await _poll_embeddings(pool, content_ids)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'} in {_elapsed(t0)}")

    print("[3/8] Running narrative clustering...")
    await _enqueue_clustering(TOPIC_ID)
    ok = await _poll_clusters(pool, TOPIC_ID)
    print(f"  -> {'Complete' if ok else 'WARNING: timeout'}")

    print("[4/8] Seeding investigative signals...")
    signal_count = await _seed_signals(pool)
    print(f"  -> {signal_count} signal(s) seeded")

    print("[5/8] Authenticating...")
    token = await _authenticate()

    print("[6/8] Credibility adjustment (audit trail demo)...")
    await _adjust_credibility(token)

    print("[7/8] Generating intelligence brief...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED. Check Ollama.")
        await pool.close()
        return

    print("[8/8] Downloading PDF...")
    pdf_path = await _download_pdf(report_id)

    await pool.close()
    print("\n" + "=" * 70)
    print(f"  WORKFLOW 1 COMPLETE — {_elapsed(total_t0)}")
    print(f"  Report ID: {report_id}")
    if pdf_path:
        print(f"  PDF: {pdf_path}")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay", action="store_true", default=True)
    args = parser.parse_args()
    asyncio.run(run(live=args.live))


if __name__ == "__main__":
    main()
