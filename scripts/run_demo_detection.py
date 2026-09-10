#!/usr/bin/env python3
"""Run detection over the seeded demonstration corpus - issue #40.

The seed writes content and nothing else. Narrative Clusters and Signals are
produced by the platform, so this script drives the same jobs production ingest
drives and then waits for the Signal engine, rather than writing rows that look
like detection.

Stages:

  1/4  enqueue analyse_content for the org's unembedded content
  2/4  wait for exactly those items to be embedded
  3/4  enqueue run_clustering for the org's active Topics and wait for clusters
  4/4  wait for the Signal engine to fire on any breaching cluster

Stage 4 is a wait rather than a call because the engine runs inside the analyst
service on a fixed interval. Reaching into the database from here would produce
a Signal the deployment did not fire, which is the thing this script exists to
avoid.

Credentials come from the environment only, never from argv, because argv is
readable by any process on the host. POSTGRES_URL wins if it is set; otherwise
the DSN is assembled from POSTGRES_PASSWORD with the password percent-encoded,
so a password containing '@', '/' or '#' cannot corrupt the DSN.

    make demo-detect
    POSTGRES_PASSWORD=... uv run python scripts/run_demo_detection.py \
        --org-id org-anshul
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import quote

import asyncpg
from arq import create_pool
from arq.connections import RedisSettings

ANALYST_QUEUE = "arq:analyst"

# Bounded, org-scoped, and quality-gated to match the clustering read path.
# Without the bound this enqueues one job per unembedded row across every
# tenant, which is not a thing a demonstration helper should be able to do.
SQL_UNEMBEDDED = """
    SELECT id FROM content_items
    WHERE org_id = $1
      AND embedding IS NULL
      AND COALESCE(content_quality, 'good') != 'low_quality'
    ORDER BY captured_at ASC
    LIMIT $2
"""

# Counts the enqueued set specifically. Counting embedded rows table-wide
# raced with the worker: an item embedded between listing and counting was
# counted in both terms, so the target exceeded the row count and was
# unreachable.
SQL_STILL_UNEMBEDDED = """
    SELECT COUNT(*) FROM content_items
    WHERE id = ANY($1::text[]) AND embedding IS NULL
"""

SQL_ACTIVE_TOPICS = "SELECT id FROM topics WHERE status = 'active' AND org_id = $1"

# narrative_clusters and signals carry no org_id of their own, so both scope
# through topics.org_id. See the multi-tenancy rules in AGENTS.md.
SQL_CLUSTER_COUNT = """
    SELECT COUNT(*)
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE t.org_id = $1 AND nc.archived_at IS NULL
"""

SQL_SIGNAL_COUNT = """
    SELECT COUNT(*)
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    WHERE t.org_id = $1
"""

# A cluster at or above its Topic's threshold is what the Signal engine acts
# on. If none exists, waiting for a Signal is waiting for something that will
# never happen, and the script says so instead of timing out.
SQL_BREACHING_CLUSTERS = """
    SELECT COUNT(*)
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    WHERE t.org_id = $1
      AND nc.independent_source_count >= t.signal_threshold
      AND t.status = 'active'
      AND nc.archived_at IS NULL
"""

POLL_INTERVAL_S = 5
# Stage 4 can wait out a full engine cycle. Reporting every poll turned that
# into 40+ identical lines, which buries the stages either side of it.
PROGRESS_EVERY_S = 30


def _step(number: int, message: str) -> None:
    print(f"[{number}/4] {message}", flush=True)


def _signal_interval_s() -> int:
    """The deployed Signal engine's cycle length.

    Read from settings rather than restated, so a tuned interval does not turn
    this script's progress message into a false statement.
    """
    try:
        from anveshak.analyst.settings import settings

        return int(settings.signal_check_interval_s)
    except Exception:
        # The analyst package is not importable from every host. Fall back to
        # the documented default rather than failing the run over a message.
        return 300


def resolve_postgres_url(env: dict[str, str]) -> str:
    """Build a DSN from the environment, percent-encoding the password.

    Returns an empty string when no credential is available, so the caller can
    refuse rather than connect with an empty password.
    """
    # An empty POSTGRES_URL is treated as unset. `make demo-detect` blanks it
    # deliberately: .env may carry the in-container DSN, which is unreachable
    # from the host, and silently using it produced a bare connection error.
    explicit = env.get("POSTGRES_URL", "").strip()
    if explicit:
        return explicit

    password = env.get("POSTGRES_PASSWORD", "").strip()
    if not password:
        return ""

    host = env.get("POSTGRES_HOST", "localhost")
    port = env.get("POSTGRES_PORT", "5433")
    user = env.get("POSTGRES_USER", "anveshak")
    database = env.get("POSTGRES_DB", "anveshak")
    return (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}"
    )


async def _poll_until(
    pool: asyncpg.Pool,
    sql: str,
    *args: object,
    reached,
    timeout_s: int,
    label: str,
) -> int:
    """Poll a count query until `reached` accepts it, or the timeout expires."""
    waited = 0
    while True:
        count = int(await pool.fetchval(sql, *args))
        if reached(count):
            return count
        if waited >= timeout_s:
            return count
        if waited % PROGRESS_EVERY_S == 0:
            print(f"      {label}: {count} after {waited}s", flush=True)
        await asyncio.sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S


async def run(
    postgres_url: str,
    redis_url: str,
    *,
    org_id: str,
    max_items: int,
    signal_timeout_s: int,
) -> int:
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=2)
    if pool is None:
        print("Could not open a database pool.", file=sys.stderr)
        return 1

    redis = None
    try:
        redis = await create_pool(RedisSettings.from_dsn(redis_url))

        # Baselines, so a re-run cannot report pre-existing rows as this run's
        # work. An absolute count of 1 was green the instant the script started.
        clusters_before = int(await pool.fetchval(SQL_CLUSTER_COUNT, org_id))
        signals_before = int(await pool.fetchval(SQL_SIGNAL_COUNT, org_id))

        _step(1, "Enqueueing analysis for unembedded content")
        pending = [r["id"] for r in await pool.fetch(SQL_UNEMBEDDED, org_id, max_items)]
        for item_id in pending:
            await redis.enqueue_job("analyse_content", item_id, _queue_name=ANALYST_QUEUE)
        print(
            f"      {len(pending)} enqueued for org {org_id} "
            f"(baseline: {clusters_before} cluster(s), {signals_before} Signal(s))",
            flush=True,
        )

        _step(2, "Waiting for embeddings")
        if pending:
            outstanding = await _poll_until(
                pool,
                SQL_STILL_UNEMBEDDED,
                pending,
                reached=lambda n: n == 0,
                timeout_s=300,
                label="still unembedded",
            )
            if outstanding:
                print(
                    f"      {outstanding} of {len(pending)} items never embedded. "
                    "Check the analyst worker logs.",
                    file=sys.stderr,
                )
                return 1
        else:
            print("      nothing to embed", flush=True)

        _step(3, "Clustering active Topics")
        topic_ids = [r["id"] for r in await pool.fetch(SQL_ACTIVE_TOPICS, org_id)]
        for topic_id in topic_ids:
            await redis.enqueue_job("run_clustering", topic_id, _queue_name=ANALYST_QUEUE)
        clusters = await _poll_until(
            pool,
            SQL_CLUSTER_COUNT,
            org_id,
            reached=lambda n: n >= 1,
            timeout_s=180,
            label="clusters",
        )
        if clusters == 0:
            print(
                f"      No cluster formed across {len(topic_ids)} active Topic(s). "
                "The corpus may hold no two items similar enough to group.",
                file=sys.stderr,
            )
            return 1
        print(
            f"      {clusters} cluster(s) across {len(topic_ids)} active Topic(s) "
            f"(was {clusters_before})",
            flush=True,
        )

        _step(4, "Waiting for the Signal engine")
        breaching = int(await pool.fetchval(SQL_BREACHING_CLUSTERS, org_id))
        if breaching == 0:
            print(
                "      No cluster reaches its Topic's signal_threshold, so no "
                "Signal is due. This is a corpus result, not a failure.",
                flush=True,
            )
            return 0

        if signals_before:
            # The engine dedups per cluster for 24 hours, so it will not fire
            # again for the same narrative. Waiting for a new row here would
            # hang on every re-run.
            print(
                f"      {signals_before} Signal(s) already fired for this org. "
                "The engine dedups per cluster for 24h, so none is due now.",
                flush=True,
            )
            return 0

        interval = _signal_interval_s()
        print(
            f"      {breaching} cluster(s) at or above threshold; the engine "
            f"checks every {interval}s",
            flush=True,
        )
        signals = await _poll_until(
            pool,
            SQL_SIGNAL_COUNT,
            org_id,
            reached=lambda n: n >= 1,
            timeout_s=signal_timeout_s,
            label="signals",
        )
        if signals == 0:
            print(
                "      No Signal fired within the timeout. Check that the "
                "analyst scheduler is running.",
                file=sys.stderr,
            )
            return 1
        print(f"      {signals} Signal(s) fired by the engine", flush=True)
        return 0
    finally:
        if redis is not None:
            await redis.aclose()
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--org-id",
        required=True,
        help="Organisation to run detection for. Scopes every query.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=500,
        help="Cap on content items enqueued in one run (default: 500).",
    )
    parser.add_argument(
        "--signal-timeout",
        type=int,
        default=0,
        help="Seconds to wait for the Signal engine. Default: one cycle plus 120s.",
    )
    args = parser.parse_args()

    postgres_url = resolve_postgres_url(dict(os.environ))
    if not postgres_url:
        print(
            "Set POSTGRES_URL, or POSTGRES_PASSWORD for the default host "
            "connection. This script ships no credential default.",
            file=sys.stderr,
        )
        return 2

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    signal_timeout = args.signal_timeout or (_signal_interval_s() + 120)

    return asyncio.run(
        run(
            postgres_url,
            redis_url,
            org_id=args.org_id,
            max_items=args.max_items,
            signal_timeout_s=signal_timeout,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
