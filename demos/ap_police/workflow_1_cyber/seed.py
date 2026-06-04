#!/usr/bin/env python3
"""Seed script for Workflow 1: AP Cyber Crime — Investment Scam Ring.

Loads synthetic fixtures into Anveshak's real backend via direct SQL + ARQ job
enqueue, then triggers the full pipeline: NLP -> clustering -> report generation.

Usage:
    python -m demos.ap_police.workflow_1_cyber.seed --replay   # default: fixtures only
    python -m demos.ap_police.workflow_1_cyber.seed --live      # requires ANVESHAK_ALLOW_LIVE=1

All fixture data is tagged synthetic: true, source_origin: 'demo_fixture'.
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

log = structlog.get_logger("demo.workflow_1_cyber")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"

FIXTURES_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR = Path(__file__).parent / "expected_outputs"

# Topic and source UUIDs (deterministic for idempotency)
TOPIC_ID = "ap-cyber-001-topic"
SOURCE_IDS = {
    "telegram_scam_1": "ap-cyber-src-telegram-vja",
    "telegram_scam_2": "ap-cyber-src-telegram-guntur",
    "telegram_scam_3": "ap-cyber-src-telegram-vizag",
    "reddit_scam_report": "ap-cyber-src-reddit-invest",
    "reddit_warning": "ap-cyber-src-reddit-scams",
    "reddit_victim": "ap-cyber-src-reddit-legal",
    "reddit_crypto": "ap-cyber-src-reddit-crypto",
    "news_deccan": "ap-cyber-src-deccan",
    "news_hindu": "ap-cyber-src-hindu",
    "news_toi": "ap-cyber-src-toi",
    "news_eenadu": "ap-cyber-src-eenadu",
}

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "telegram_scam_1": {"name": "Telegram: @quickprofit_vja", "url": "https://t.me/quickprofit_vja", "platform": "telegram", "credibility": 25.0},
    "telegram_scam_2": {"name": "Telegram: @quickprofit_guntur", "url": "https://t.me/quickprofit_guntur", "platform": "telegram", "credibility": 22.0},
    "telegram_scam_3": {"name": "Telegram: @quickprofit_vizag", "url": "https://t.me/quickprofit_vizag", "platform": "telegram", "credibility": 20.0},
    "reddit_scam_report": {"name": "Reddit: r/IndiaInvestments", "url": "https://reddit.com/r/IndiaInvestments", "platform": "reddit", "credibility": 55.0},
    "reddit_warning": {"name": "Reddit: r/Scams", "url": "https://reddit.com/r/Scams", "platform": "reddit", "credibility": 60.0},
    "reddit_victim": {"name": "Reddit: r/LegalAdviceIndia", "url": "https://reddit.com/r/LegalAdviceIndia", "platform": "reddit", "credibility": 50.0},
    "reddit_crypto": {"name": "Reddit: r/CryptoCurrency", "url": "https://reddit.com/r/CryptoCurrency", "platform": "reddit", "credibility": 58.0},
    "news_deccan": {"name": "Deccan Chronicle", "url": "https://www.deccanchronicle.com", "platform": "web", "credibility": 78.0},
    "news_hindu": {"name": "The Hindu", "url": "https://www.thehindu.com", "platform": "web", "credibility": 85.0},
    "news_toi": {"name": "Times of India", "url": "https://timesofindia.indiatimes.com", "platform": "web", "credibility": 75.0},
    "news_eenadu": {"name": "Eenadu", "url": "https://www.eenadu.net", "platform": "web", "credibility": 72.0},
}

LABELS = '{"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}'


def _sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _elapsed(t0: float) -> str:
    return f"{time.monotonic() - t0:.1f}s"


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def _insert_topic(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        INSERT INTO topics (id, name, keywords, signal_threshold, status, labels, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
    """,
        TOPIC_ID,
        "AP Cyber Fraud: Investment Scam Ring",
        ["QuickProfit", "UPI fraud", "crypto scam", "Vijayawada", "Guntur", "Visakhapatnam",
         "Ponzi", "Telegram scam", "investment fraud", "AP cyber crime"],
        3,
        "active",
        LABELS,
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

        # Link source to topic via topic_sources
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
            content_hash, item.get("url"), datetime.now(timezone.utc) - timedelta(days=2),
            credibility, "good",
            json.dumps(item["labels"]),
        )
        if result:
            content_ids.append(result)

    log.info("content.inserted", count=len(content_ids), total_fixtures=len(fixtures))
    return content_ids


# ---------------------------------------------------------------------------
# ARQ job enqueue
# ---------------------------------------------------------------------------

async def _enqueue_analysis_jobs(content_ids: list[str]) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings

    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    for cid in content_ids:
        await redis.enqueue_job("analyse_content", cid, _queue_name="arq:analyst")
    log.info("arq.analyse_content.enqueued", count=len(content_ids))
    await redis.close()


async def _poll_embeddings(pool: asyncpg.Pool, content_ids: list[str], timeout: int = 180) -> bool:
    """Poll until all content items have embeddings (analyse_content completed)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM content_items
                WHERE id = ANY($1) AND embedding IS NOT NULL
            """, content_ids)
        if count >= len(content_ids):
            log.info("embeddings.complete", count=count, elapsed=_elapsed(t0))
            return True
        log.info("embeddings.waiting", done=count, total=len(content_ids), elapsed=_elapsed(t0))
        await asyncio.sleep(5)
    log.warning("embeddings.timeout", timeout=timeout)
    return False


async def _enqueue_clustering(topic_id: str) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings

    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("run_clustering", topic_id, _queue_name="arq:analyst")
    log.info("arq.run_clustering.enqueued", topic_id=topic_id)
    await redis.close()


async def _poll_clusters(pool: asyncpg.Pool, topic_id: str, timeout: int = 120) -> bool:
    """Poll until at least 1 narrative cluster exists for the topic."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        async with pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM narrative_clusters
                WHERE topic_id = $1 AND item_count > 0
            """, topic_id)
        if count and count >= 1:
            log.info("clusters.complete", count=count, elapsed=_elapsed(t0))
            return True
        log.info("clusters.waiting", elapsed=_elapsed(t0))
        await asyncio.sleep(5)
    log.warning("clusters.timeout", timeout=timeout)
    return False


# ---------------------------------------------------------------------------
# Credibility adjustment (for audit log demo)
# ---------------------------------------------------------------------------

async def _adjust_credibility(token: str) -> None:
    """Adjust one source's credibility to demonstrate the audit trail."""
    source_id = SOURCE_IDS["telegram_scam_1"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{API_BASE}/api/v1/sources/{source_id}/credibility",
            headers={"Authorization": f"Bearer {token}"},
            params={"new_score": 15.0, "reason": "Confirmed scam operation — credibility downgraded after multi-source corroboration"},
        )
        if resp.status_code == 200:
            log.info("credibility.adjusted", source_id=source_id, new_score=15.0)
        else:
            log.warning("credibility.adjust_failed", status=resp.status_code, body=resp.text[:200])


# ---------------------------------------------------------------------------
# Report generation via API
# ---------------------------------------------------------------------------

async def _authenticate() -> str:
    """Login and return JWT token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"username": DEMO_USER, "password": DEMO_PASS},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        log.info("auth.success", username=DEMO_USER)
        return token


async def _generate_report(token: str) -> str | None:
    """Create report via API and poll until complete."""
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create report
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
        log.info("report.created", report_id=report_id, elapsed=_elapsed(t0))

        # Poll for completion
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
                    log.error("report.failed", report_id=report_id,
                              error=rdata.get("generation_error", "unknown"))
                    return None
            log.info("report.polling", report_id=report_id, elapsed=_elapsed(t0))
            await asyncio.sleep(10)

    log.error("report.timeout", report_id=report_id, timeout=timeout)
    return None


async def _download_pdf(token: str, report_id: str) -> str | None:
    """Download the generated PDF."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            "http://localhost:8005/api/v1/reports/{}/pdf".format(report_id),
        )
        if resp.status_code == 200:
            pdf_path = OUTPUT_DIR / "workflow_1_report.pdf"
            pdf_path.write_bytes(resp.content)
            log.info("pdf.downloaded", path=str(pdf_path), size_kb=len(resp.content) // 1024)
            return str(pdf_path)
        log.warning("pdf.download_failed", status=resp.status_code)
        return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run(live: bool = False) -> None:
    if live and not os.getenv("ANVESHAK_ALLOW_LIVE"):
        print("ERROR: --live requires ANVESHAK_ALLOW_LIVE=1 environment variable")
        sys.exit(1)

    total_t0 = time.monotonic()
    print("\n" + "=" * 70)
    print("  ANVESHAK — Workflow 1: AP Cyber Crime — Investment Scam Ring")
    print("  Mode: REPLAY (fixtures)" if not live else "  Mode: LIVE")
    print("=" * 70 + "\n")

    # 1. Database seed
    print("[1/8] Seeding database...")
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)
    async with pool.acquire() as conn:
        await _insert_topic(conn)
        await _insert_sources(conn)
        content_ids = await _insert_content(conn)

    if not content_ids:
        print("  WARNING: No new content inserted (may already be seeded)")
        # Fetch existing content IDs
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id FROM content_items WHERE topic_id = $1", TOPIC_ID
            )
            content_ids = [r["id"] for r in rows]

    print(f"  -> {len(content_ids)} content items ready")

    # 2. NLP analysis
    print("[2/8] Running NLP analysis (language detect, translate, NER, embed)...")
    t0 = time.monotonic()
    await _enqueue_analysis_jobs(content_ids)
    ok = await _poll_embeddings(pool, content_ids, timeout=180)
    print(f"  -> Analysis complete in {_elapsed(t0)}" if ok else "  -> WARNING: Analysis timeout")

    # 3. Clustering
    print("[3/8] Running narrative clustering (Leiden)...")
    t0 = time.monotonic()
    await _enqueue_clustering(TOPIC_ID)
    ok = await _poll_clusters(pool, TOPIC_ID, timeout=120)
    print(f"  -> Clustering complete in {_elapsed(t0)}" if ok else "  -> WARNING: Clustering timeout")

    # 4. Check signals
    print("[4/8] Checking signals...")
    async with pool.acquire() as conn:
        signal_count = await conn.fetchval(
            "SELECT COUNT(*) FROM signals WHERE topic_id = $1", TOPIC_ID
        )
    print(f"  -> {signal_count} signal(s) detected")

    # 5. Authenticate
    print("[5/8] Authenticating...")
    token = await _authenticate()

    # 6. Credibility adjustment (audit demo)
    print("[6/8] Adjusting source credibility (audit trail demo)...")
    await _adjust_credibility(token)

    # 7. Report generation
    print("[7/8] Generating prosecution-ready intelligence brief...")
    report_id = await _generate_report(token)
    if not report_id:
        print("  -> FAILED: Report generation failed. Check Ollama status.")
        await pool.close()
        return

    # 8. PDF download
    print("[8/8] Downloading PDF report...")
    pdf_path = await _download_pdf(token, report_id)

    await pool.close()

    # Summary
    total_elapsed = _elapsed(total_t0)
    print("\n" + "=" * 70)
    print(f"  WORKFLOW 1 COMPLETE — {total_elapsed}")
    print(f"  Topic: AP Cyber Fraud: Investment Scam Ring")
    print(f"  Content items: {len(content_ids)}")
    print(f"  Signals: {signal_count}")
    print(f"  Report ID: {report_id}")
    if pdf_path:
        print(f"  PDF: {pdf_path}")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Workflow 1: AP Cyber Crime")
    parser.add_argument("--live", action="store_true", help="Use live sources (requires ANVESHAK_ALLOW_LIVE=1)")
    parser.add_argument("--replay", action="store_true", default=True, help="Use fixtures (default)")
    args = parser.parse_args()
    asyncio.run(run(live=args.live))


if __name__ == "__main__":
    main()
