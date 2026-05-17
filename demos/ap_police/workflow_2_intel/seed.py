#!/usr/bin/env python3
"""Seed script for Workflow 2: AP Intel — CPI-Maoist Recruitment & Financing.

Loads synthetic fixtures into Anveshak's real backend, triggers the full pipeline
with three-lens evaluation enabled.

Usage:
    python -m demos.ap_police.workflow_2_intel.seed --replay   # default: fixtures only
    python -m demos.ap_police.workflow_2_intel.seed --live      # requires ANVESHAK_ALLOW_LIVE=1
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

log = structlog.get_logger("demo.workflow_2_intel")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

# Topic IDs
TOPIC_ID = "ap-intel-001-topic"
PRIOR_TOPIC_ID = "ap-intel-000-prior"  # convergence detection target

SOURCE_IDS = {
    "telegram_recruit_te": "ap-intel-src-tg-recruit",
    "telegram_finance_or": "ap-intel-src-tg-finance",
    "blog_ideological": "ap-intel-src-blog",
    "reddit_tribal": "ap-intel-src-reddit-vizag",
    "reddit_aob": "ap-intel-src-reddit-defence",
    "reddit_mining": "ap-intel-src-reddit-india",
    "news_ndtv": "ap-intel-src-ndtv",
    "reddit_finance": "ap-intel-src-reddit-finance",
    "news_hindu_intel": "ap-intel-src-hindu",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "telegram_recruit_te": {"name": "Telegram: @janashakti_aob (Telugu)", "url": "https://t.me/janashakti_aob", "platform": "telegram", "credibility": 30.0},
    "telegram_finance_or": {"name": "Telegram: @janashakti_odisha (Odia)", "url": "https://t.me/janashakti_odisha", "platform": "telegram", "credibility": 28.0},
    "blog_ideological": {"name": "Leftword Books Blog", "url": "https://leftwordbooks.com/blog", "platform": "web", "credibility": 40.0},
    "reddit_tribal": {"name": "Reddit: r/Visakhapatnam", "url": "https://reddit.com/r/Visakhapatnam", "platform": "reddit", "credibility": 45.0},
    "reddit_aob": {"name": "Reddit: r/IndianDefence", "url": "https://reddit.com/r/IndianDefence", "platform": "reddit", "credibility": 60.0},
    "reddit_mining": {"name": "Reddit: r/india", "url": "https://reddit.com/r/india", "platform": "reddit", "credibility": 50.0},
    "news_ndtv": {"name": "NDTV", "url": "https://www.ndtv.com", "platform": "web", "credibility": 82.0},
    "reddit_finance": {"name": "Reddit: r/IndianFinance", "url": "https://reddit.com/r/IndianFinance", "platform": "reddit", "credibility": 52.0},
    "news_hindu_intel": {"name": "The Hindu", "url": "https://www.thehindu.com", "platform": "web", "credibility": 85.0},
}

LABELS = '{"classification": "RESTRICTED", "domain": "osint", "owner_org": "anveshak"}'


def _sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


async def _insert_prior_topic(conn: asyncpg.Connection) -> None:
    """Seed a prior topic for convergence detection."""
    await conn.execute("""
        INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, NOW())
        ON CONFLICT (id) DO NOTHING
    """,
        PRIOR_TOPIC_ID,
        "Tribal Welfare Grievance Amplification",
        ["tribal rights", "mining protest", "Visakhapatnam Agency", "bauxite", "forest rights", "Vedanta"],
        3, "active", LABELS,
        datetime.now(UTC) - timedelta(days=30),
    )
    log.info("prior_topic.inserted", topic_id=PRIOR_TOPIC_ID)


async def _insert_topic(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
    """,
        TOPIC_ID,
        "AOB Maoist Recruitment & Financing",
        ["CPI-Maoist", "Janashakti", "AOB", "Alluri Sitharama Raju", "Vizianagaram",
         "tribal recruitment", "hawala", "Maoist", "left-wing extremism", "LWE"],
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
    log.info("arq.analyse_content.enqueued", count=len(content_ids))
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
            log.info("embeddings.complete", count=count, elapsed=_elapsed(t0))
            return True
        log.info("embeddings.waiting", done=count, total=len(content_ids), elapsed=_elapsed(t0))
        await asyncio.sleep(5)
    return False


async def _enqueue_clustering(topic_id: str) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("run_clustering", topic_id, _queue_name="arq:analyst")
    log.info("arq.run_clustering.enqueued", topic_id=topic_id)
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
            log.info("clusters.complete", count=count, elapsed=_elapsed(t0))
            return True
        log.info("clusters.waiting", elapsed=_elapsed(t0))
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
                "credibility_min": 20.0,
            },
        )
        if resp.status_code not in (201, 202):
            log.error("report.create_failed", status=resp.status_code, body=resp.text[:200])
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
                    log.error("report.failed", error=rdata.get("generation_error", "unknown"))
                    return None
            log.info("report.polling", elapsed=_elapsed(t0))
            await asyncio.sleep(10)
    return None


async def _download_pdf(token: str, report_id: str) -> str | None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            "http://localhost:8005/api/v1/reports/{}/pdf".format(report_id),
        )
        if resp.status_code == 200:
            pdf_path = OUTPUT_DIR / "workflow_2_report.pdf"
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
    print("  ANVESHAK — Workflow 2: AOB Maoist Recruitment & Financing")
    print("  Mode: REPLAY (fixtures)" if not live else "  Mode: LIVE")
    print("=" * 70 + "\n")

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    print("[1/7] Seeding database (including prior topic for convergence)...")
    async with pool.acquire() as conn:
        await _insert_prior_topic(conn)
        await _insert_topic(conn)
        await _insert_sources(conn)
        content_ids = await _insert_content(conn)

    if not content_ids:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID)
            content_ids = [r["id"] for r in rows]
    print(f"  -> {len(content_ids)} content items ready")

    print("[2/7] Running NLP analysis (incl. Telugu and Odia translation)...")
    t0 = time.monotonic()
    await _enqueue_analysis_jobs(content_ids)
    ok = await _poll_embeddings(pool, content_ids, timeout=240)
    print(f"  -> Analysis complete in {_elapsed(t0)}" if ok else "  -> WARNING: timeout")

    print("[3/7] Running narrative clustering...")
    t0 = time.monotonic()
    await _enqueue_clustering(TOPIC_ID)
    ok = await _poll_clusters(pool, TOPIC_ID, timeout=120)
    print(f"  -> Clustering complete in {_elapsed(t0)}" if ok else "  -> WARNING: timeout")

    print("[4/7] Checking signals...")
    async with pool.acquire() as conn:
        signal_count = await conn.fetchval("SELECT COUNT(*) FROM signals WHERE topic_id = $1", TOPIC_ID)
    print(f"  -> {signal_count} signal(s) detected")

    print("[5/7] Authenticating...")
    token = await _authenticate()

    print("[6/7] Generating intelligence brief with three-lens evaluation...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED")
        await pool.close()
        return

    print("[7/7] Downloading PDF...")
    pdf_path = await _download_pdf(token, report_id)

    await pool.close()
    total_elapsed = _elapsed(total_t0)
    print("\n" + "=" * 70)
    print(f"  WORKFLOW 2 COMPLETE — {total_elapsed}")
    print(f"  Report ID: {report_id}")
    if pdf_path:
        print(f"  PDF: {pdf_path}")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Workflow 2: AOB Intel")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay", action="store_true", default=True)
    args = parser.parse_args()
    asyncio.run(run(live=args.live))


if __name__ == "__main__":
    main()
