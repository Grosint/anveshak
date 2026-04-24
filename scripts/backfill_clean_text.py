"""One-time backfill: re-clean existing content_items.clean_text.

Reads raw_text, applies clean_extracted_text(), updates clean_text.
Preserves raw_text and content_hash (hash is based on raw, not cleaned).

Usage:
    uv run python scripts/backfill_clean_text.py [--dry-run] [--batch-size 500]
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg
import structlog

from anveshak.scraper.clean import clean_extracted_text

log = structlog.get_logger(__name__)

SQL_COUNT = "SELECT COUNT(*) FROM content_items"

SQL_FETCH_BATCH = """
    SELECT id, raw_text
    FROM content_items
    ORDER BY created_at ASC
    LIMIT $1 OFFSET $2
"""

SQL_UPDATE_CLEAN_TEXT = """
    UPDATE content_items SET clean_text = $1, updated_at = NOW()
    WHERE id = $2
"""


async def backfill(postgres_url: str, batch_size: int, dry_run: bool) -> None:
    pool = await asyncpg.create_pool(postgres_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        total = await conn.fetchval(SQL_COUNT)

    log.info("backfill.start", total_items=total, batch_size=batch_size, dry_run=dry_run)

    updated = 0
    skipped = 0
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

                if cleaned and cleaned != raw:
                    if not dry_run:
                        await conn.execute(SQL_UPDATE_CLEAN_TEXT, cleaned, row["id"])
                    updated += 1
                else:
                    skipped += 1

        offset += batch_size
        log.info(
            "backfill.progress",
            processed=offset,
            total=total,
            updated=updated,
            skipped=skipped,
        )

    await pool.close()
    log.info("backfill.done", updated=updated, skipped=skipped)


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description="Backfill clean_text for existing content items")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without updating DB")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per batch (default: 500)")
    args = parser.parse_args()

    postgres_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://anveshak:anveshak@localhost:5433/anveshak",
    )

    asyncio.run(backfill(postgres_url, args.batch_size, args.dry_run))


if __name__ == "__main__":
    main()
