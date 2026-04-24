"""Backfill content_quality, clean_hash, and title for all existing content items.

Also re-cleans clean_text with the latest cleaner. Preserves raw_text and content_hash.

Usage:
    uv run python scripts/backfill_quality_and_titles.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg
import structlog

from anveshak.scraper.clean import (
    clean_extracted_text,
    compute_clean_hash,
    extract_title,
    score_content_quality,
)

log = structlog.get_logger(__name__)

SQL_COUNT = "SELECT COUNT(*) FROM content_items"

SQL_FETCH_BATCH = """
    SELECT id, raw_text, clean_text
    FROM content_items
    ORDER BY created_at ASC
    LIMIT $1 OFFSET $2
"""

SQL_UPDATE = """
    UPDATE content_items
    SET clean_text = $1,
        content_quality = $2,
        clean_hash = $3,
        title = $4,
        updated_at = NOW()
    WHERE id = $5
"""


async def backfill(postgres_url: str, batch_size: int, dry_run: bool) -> None:
    pool = await asyncpg.create_pool(postgres_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        total = await conn.fetchval(SQL_COUNT)

    log.info("backfill.start", total_items=total, batch_size=batch_size, dry_run=dry_run)

    stats = {"updated": 0, "low_quality": 0, "skipped": 0}
    offset = 0

    while offset < total:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_FETCH_BATCH, batch_size, offset)

        if not rows:
            break

        async with pool.acquire() as conn:
            for row in rows:
                raw = row["raw_text"]
                cleaned = clean_extracted_text(raw)
                effective = cleaned or raw

                quality = score_content_quality(raw, effective)
                c_hash = compute_clean_hash(effective)
                title = extract_title(effective)

                if quality == "low_quality":
                    stats["low_quality"] += 1

                if not dry_run:
                    await conn.execute(SQL_UPDATE, effective, quality, c_hash, title, row["id"])
                stats["updated"] += 1

        offset += batch_size
        log.info(
            "backfill.progress",
            processed=offset,
            total=total,
            **stats,
        )

    await pool.close()
    log.info("backfill.done", **stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill quality, clean_hash, and titles")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    postgres_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
    )
    asyncio.run(backfill(postgres_url, args.batch_size, args.dry_run))


if __name__ == "__main__":
    main()
