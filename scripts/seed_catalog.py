#!/usr/bin/env python3
"""Seed the source_catalog table from JSON manifests in scripts/catalog/.

Idempotent — uses ON CONFLICT(platform, url_or_handle) DO NOTHING.
Run: uv run python scripts/seed_catalog.py

Requires POSTGRES_URL env var or defaults to local dev database.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import structlog

log = structlog.get_logger(__name__)

CATALOG_DIR = Path(__file__).parent / "catalog"
POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
)
LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

SQL_INSERT = """
    INSERT INTO source_catalog (
        id, name, url_or_handle, platform, domain_tags,
        reliability_tier, bias_indicator, risk_level, language,
        category, description, subscriber_count, activity_frequency,
        created_at, updated_at, labels
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
    ON CONFLICT (platform, url_or_handle) DO NOTHING
"""


def load_manifests() -> list[dict]:
    """Load all JSON manifest files from the catalog directory."""
    entries = []
    if not CATALOG_DIR.exists():
        log.warning("catalog.dir_not_found", path=str(CATALOG_DIR))
        return entries

    for manifest_path in sorted(CATALOG_DIR.glob("*.json")):
        try:
            data = json.loads(manifest_path.read_text())
            if not isinstance(data, list):
                log.warning("catalog.invalid_manifest", path=str(manifest_path),
                            reason="expected JSON array")
                continue
            for entry in data:
                entry["_source_file"] = manifest_path.stem
            entries.extend(data)
            log.info("catalog.manifest_loaded", file=manifest_path.stem,
                     count=len(data))
        except json.JSONDecodeError as exc:
            log.error("catalog.json_parse_error", path=str(manifest_path),
                      error=str(exc))
    return entries


async def seed(pool: asyncpg.Pool) -> int:
    """Insert catalog entries. Returns count of new rows inserted."""
    entries = load_manifests()
    if not entries:
        log.warning("catalog.no_entries_found")
        return 0

    now = datetime.now(UTC)
    inserted = 0

    async with pool.acquire() as conn:
        for entry in entries:
            result = await conn.execute(
                SQL_INSERT,
                str(uuid.uuid4()),
                entry["name"],
                entry["url_or_handle"],
                entry["platform"],
                entry.get("domain_tags", []),
                entry.get("reliability_tier", "C"),
                entry.get("bias_indicator", "unknown"),
                entry.get("risk_level", "low"),
                entry.get("language", "en"),
                entry.get("category", "news"),
                entry.get("description", ""),
                entry.get("subscriber_count"),
                entry.get("activity_frequency", "unknown"),
                now, now, LABELS_JSON,
            )
            if result and "INSERT 0 1" in result:
                inserted += 1

    log.info("catalog.seed_complete", total=len(entries), inserted=inserted,
             skipped=len(entries) - inserted)
    return inserted


async def main():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    try:
        count = await seed(pool)
        print(f"Seeded {count} new catalog entries")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
