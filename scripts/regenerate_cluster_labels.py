"""Force-regenerate cluster labels for all clusters with fallback 'Cluster N' labels.

Calls Ollama directly for each cluster via the labeller module.

Usage:
    uv run python scripts/regenerate_cluster_labels.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg
import structlog

log = structlog.get_logger(__name__)

SQL_FALLBACK_CLUSTERS = """
    SELECT id, label, item_count
    FROM narrative_clusters
    WHERE label LIKE 'Cluster %%'
       OR label = 'Unclassified cluster'
       OR label_generated_at IS NULL
       OR executive_summary IS NULL
    ORDER BY item_count DESC
"""

SQL_RESET_LABEL_HASH = """
    UPDATE narrative_clusters
    SET label_item_hash = NULL
    WHERE id = $1
"""


async def regenerate(postgres_url: str, dry_run: bool) -> None:
    pool = await asyncpg.create_pool(postgres_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        clusters = await conn.fetch(SQL_FALLBACK_CLUSTERS)

    log.info("regen.found_fallback_clusters", count=len(clusters))

    if dry_run:
        for row in clusters:
            log.info("regen.would_regenerate", cluster_id=row["id"],
                     label=row["label"], item_count=row["item_count"])
        await pool.close()
        return

    from anveshak.analyst.labeller import generate_label_for_cluster

    generated = 0
    failed = 0
    for row in clusters:
        cluster_id = row["id"]
        try:
            # Reset hash to force regeneration
            async with pool.acquire() as conn:
                await conn.execute(SQL_RESET_LABEL_HASH, cluster_id)

            label = await generate_label_for_cluster(cluster_id, pool)
            generated += 1
            log.info("regen.success", cluster_id=cluster_id, label=label,
                     item_count=row["item_count"])
        except Exception as exc:
            failed += 1
            log.warning("regen.failed", cluster_id=cluster_id, error=str(exc))

    await pool.close()
    log.info("regen.done", generated=generated, failed=failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate fallback cluster labels")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    postgres_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak",
    )
    asyncio.run(regenerate(postgres_url, args.dry_run))


if __name__ == "__main__":
    main()
