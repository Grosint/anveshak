"""Force-regenerate cluster labels for clusters with bad/fallback labels.

Detects entity-soup labels (e.g., "TGCSB — Telangana — Hyderabad"),
missing summaries, and ungenerated labels. Logs old label before overwrite
for audit trail (NIA requirement).

Usage:
    uv run python scripts/regenerate_cluster_labels.py [--dry-run] [--batch-size 10] [--delay 2.0]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re

import asyncpg
import structlog

log = structlog.get_logger(__name__)

# Match entity-soup: "Word — Word — Word" pattern
_ENTITY_SOUP_RE = re.compile(r"^[\w\s,.'()-]+( — [\w\s,.'()-]+){1,2}$")

SQL_BAD_LABEL_CLUSTERS = """
    SELECT id, label, item_count, topic_id
    FROM narrative_clusters
    WHERE label LIKE 'Cluster %%'
       OR label = 'Unclassified cluster'
       OR label LIKE 'Activity: %%'
       OR label_generated_at IS NULL
       OR executive_summary IS NULL
    ORDER BY item_count DESC
"""

SQL_RESET_LABEL_HASH = """
    UPDATE narrative_clusters
    SET label_item_hash = NULL
    WHERE id = $1
"""


def is_entity_soup(label: str) -> bool:
    """Detect old-format entity-soup labels like 'TGCSB — Telangana — Hyderabad'."""
    return bool(_ENTITY_SOUP_RE.match(label)) and " — " in label


async def regenerate(
    postgres_url: str,
    dry_run: bool,
    batch_size: int,
    delay: float,
) -> None:
    pool = await asyncpg.create_pool(postgres_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        clusters = await conn.fetch(SQL_BAD_LABEL_CLUSTERS)

    # Also find entity-soup labels not caught by SQL patterns
    async with pool.acquire() as conn:
        all_clusters = await conn.fetch(
            "SELECT id, label, item_count, topic_id FROM narrative_clusters "
            "WHERE label IS NOT NULL AND label != '' ORDER BY item_count DESC"
        )
    soup_clusters = [
        r for r in all_clusters
        if is_entity_soup(r["label"]) and r["id"] not in {c["id"] for c in clusters}
    ]

    all_targets = list(clusters) + soup_clusters
    log.info("regen.found_targets", sql_match=len(clusters),
             entity_soup=len(soup_clusters), total=len(all_targets))

    if dry_run:
        for row in all_targets:
            reason = "entity_soup" if row in soup_clusters else "sql_match"
            log.info("regen.would_regenerate", cluster_id=row["id"],
                     label=row["label"], item_count=row["item_count"], reason=reason)
        await pool.close()
        return

    from anveshak.analyst.labeller import generate_label_for_cluster

    sem = asyncio.Semaphore(batch_size)
    generated = 0
    failed = 0

    async def process_one(row: dict) -> None:
        nonlocal generated, failed
        async with sem:
            cluster_id = row["id"]
            old_label = row["label"]
            try:
                # Audit: log old label before overwrite (NIA requirement)
                log.info("regen.old_label", cluster_id=cluster_id,
                         old_label=old_label, item_count=row["item_count"])

                async with pool.acquire() as conn:
                    await conn.execute(SQL_RESET_LABEL_HASH, cluster_id)

                label = await generate_label_for_cluster(cluster_id, pool)
                generated += 1
                log.info("regen.success", cluster_id=cluster_id,
                         old_label=old_label, new_label=label,
                         item_count=row["item_count"])
            except Exception as exc:
                failed += 1
                log.warning("regen.failed", cluster_id=cluster_id, error=str(exc))

            if delay > 0:
                await asyncio.sleep(delay)

    # Process in batches with progress logging
    total = len(all_targets)
    for i in range(0, total, batch_size):
        batch = all_targets[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        log.info("regen.batch_start", batch=batch_num, of=total_batches,
                 done=generated + failed, remaining=total - generated - failed)
        await asyncio.gather(*(process_one(row) for row in batch))

    await pool.close()
    log.info("regen.done", generated=generated, failed=failed, total=len(all_targets))


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate bad cluster labels")
    parser.add_argument("--dry-run", action="store_true",
                        help="List clusters that would be regenerated without changing them")
    parser.add_argument("--batch-size", type=int, default=3,
                        help="Max concurrent Ollama calls (default: 3)")
    parser.add_argument("--delay", type=float, default=5.0,
                        help="Delay in seconds between calls (default: 5.0)")
    args = parser.parse_args()

    postgres_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
    )
    asyncio.run(regenerate(postgres_url, args.dry_run, args.batch_size, args.delay))


if __name__ == "__main__":
    main()
