"""Backfill PHONE_INTL identifiers from existing content items.

Finds content that contains international phone numbers (previously missed or
misclassified as DATE by spaCy) and inserts PHONE_INTL extracted_entities rows.

Usage:
    uv run python scripts/backfill_phone_intl.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid

import asyncpg
import structlog
from anveshak.analyst.identifiers import extract_identifiers

log = structlog.get_logger(__name__)

# Find content items likely containing international phone numbers
# by matching the +XX pattern in clean_text
SQL_CANDIDATES = """
    SELECT ci.id, ci.clean_text, ci.labels->>'language' AS lang,
           s.platform
    FROM content_items ci
    LEFT JOIN sources s ON ci.source_id = s.id
    WHERE ci.clean_text ~ '\\+(?:86|852|971|92|977|880|95)\\s?\\d'
    ORDER BY ci.captured_at DESC
"""

SQL_EXISTING = """
    SELECT entity_text
    FROM extracted_entities
    WHERE content_item_id = $1
      AND entity_type = 'PHONE_INTL'
"""

SQL_INSERT = """
    INSERT INTO extracted_entities (
        id, content_item_id, entity_type, entity_text, confidence,
        language, created_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6, NOW(), '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT DO NOTHING
"""

# Also clean up misclassified DATE entities that are actually phone numbers
SQL_DELETE_MISCLASSIFIED = """
    DELETE FROM extracted_entities
    WHERE content_item_id = $1
      AND entity_type = 'DATE'
      AND entity_text ~ '^\\+?\\d[\\d\\s.-]+$'
      AND entity_text ~ '(?:86|852|971|92|977|880|95)'
"""


async def main(dry_run: bool = False) -> None:
    dsn = os.environ.get("POSTGRES_URL")
    if not dsn:
        raise SystemExit("POSTGRES_URL env var required")
    conn = await asyncpg.connect(dsn)

    try:
        rows = await conn.fetch(SQL_CANDIDATES)
        log.info("backfill.candidates_found", count=len(rows))

        inserted_total = 0
        cleaned_total = 0

        for row in rows:
            content_id = row["id"]
            text = row["clean_text"] or ""
            platform = row["platform"] or ""
            lang = row["lang"] or "en"

            # Extract PHONE_INTL from this content
            matches = extract_identifiers(text, platform)
            phone_intl = [m for m in matches if m.identifier_type == "PHONE_INTL"]

            if not phone_intl:
                continue

            # Check what already exists
            existing = {r["entity_text"] for r in await conn.fetch(SQL_EXISTING, content_id)}

            new_phones = [m for m in phone_intl if m.normalized_value not in existing]

            if not new_phones:
                continue

            if dry_run:
                log.info(
                    "backfill.would_insert",
                    content_id=content_id,
                    phones=[m.normalized_value for m in new_phones],
                )
                inserted_total += len(new_phones)
                continue

            async with conn.transaction():
                for m in new_phones:
                    await conn.execute(
                        SQL_INSERT,
                        str(uuid.uuid4()),
                        content_id,
                        "PHONE_INTL",
                        m.normalized_value,
                        m.confidence,
                        lang,
                    )
                    inserted_total += 1

                # Clean up misclassified DATE entities
                deleted = await conn.execute(SQL_DELETE_MISCLASSIFIED, content_id)
                count = int(deleted.split()[-1])
                if count:
                    cleaned_total += count

            log.info(
                "backfill.inserted",
                content_id=content_id,
                phones=[m.normalized_value for m in new_phones],
            )

        log.info(
            "backfill.complete",
            inserted=inserted_total,
            misclassified_dates_removed=cleaned_total,
            dry_run=dry_run,
        )

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill PHONE_INTL identifiers")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
