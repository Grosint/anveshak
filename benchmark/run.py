"""Benchmark runner — orchestrates inject → analyse → cluster → signal → measure.

Usage:
    python -m benchmark.run                    # Full run
    python -m benchmark.run --clean-only       # Just cleanup
    python -m benchmark.run --skip-analyse     # Skip NLP (if already done)
    python -m benchmark.run --events path/     # Custom events dir
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path

import asyncpg
import structlog
import yaml
from arq import create_pool as create_arq_pool
from arq.connections import RedisSettings

from .inject import inject_all, cleanup
from .metrics import evaluate_event, compute_metrics, save_results
from .report import fill_template
from .settings import settings

log = structlog.get_logger(__name__)


async def wait_for_embeddings(pool: asyncpg.Pool, topic_ids: list[str]) -> bool:
    """Poll until all content items have embeddings or timeout."""
    start = time.time()
    while time.time() - start < settings.analyse_timeout_s:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) as total,
                       COUNT(embedding) as with_embedding
                FROM content_items
                WHERE topic_id = ANY($1)
            """, topic_ids)

        total = row["total"]
        done = row["with_embedding"]

        # Wait for 100% embedding completion
        if total > 0 and done >= total:
            log.info(
                "benchmark.embeddings_complete",
                done=done,
                total=total,
                elapsed_s=int(time.time() - start),
            )
            return True

        log.debug(
            "benchmark.waiting_for_embeddings",
            done=done,
            total=total,
            elapsed_s=int(time.time() - start),
        )
        await asyncio.sleep(settings.poll_interval_s)

    log.warning(
        "benchmark.embedding_timeout",
        timeout_s=settings.analyse_timeout_s,
    )
    return False


async def enqueue_analysis_jobs(
    pool: asyncpg.Pool,
    topic_ids: list[str],
) -> int:
    """Enqueue analyse_content ARQ jobs for all benchmark content items."""
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_arq_pool(redis_settings)

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id FROM content_items
            WHERE topic_id = ANY($1) AND embedding IS NULL
        """, topic_ids)

    enqueued = 0
    for row in rows:
        await arq_pool.enqueue_job(
            "analyse_content",
            row["id"],
            _queue_name="arq:analyst",
        )
        enqueued += 1

    await arq_pool.close()
    log.info("benchmark.analysis_jobs_enqueued", count=enqueued)
    return enqueued


async def trigger_clustering(pool: asyncpg.Pool, topic_ids: list[str]) -> None:
    """Enqueue clustering jobs for all benchmark topics."""
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    arq_pool = await create_arq_pool(redis_settings)

    for topic_id in topic_ids:
        await arq_pool.enqueue_job(
            "run_clustering",
            topic_id,
            _queue_name="arq:analyst",
        )

    await arq_pool.close()
    log.info("benchmark.clustering_triggered", topics=len(topic_ids))


async def wait_for_clusters(pool: asyncpg.Pool, topic_ids: list[str]) -> bool:
    """Wait until clustering has produced results for benchmark topics."""
    start = time.time()
    timeout = 120  # 2 minutes — clustering is fast once jobs run

    while time.time() - start < timeout:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(DISTINCT topic_id) as topics_with_clusters
                FROM narrative_clusters
                WHERE topic_id = ANY($1) AND archived_at IS NULL
            """, topic_ids)

        if row["topics_with_clusters"] >= 1:
            log.info(
                "benchmark.clustering_complete",
                topics_clustered=row["topics_with_clusters"],
                total_topics=len(topic_ids),
                elapsed_s=int(time.time() - start),
            )
            # Give a bit more time for remaining topics
            await asyncio.sleep(15)
            return True

        await asyncio.sleep(settings.poll_interval_s)

    log.warning("benchmark.clustering_timeout")
    return False


async def run_benchmark(
    events_dir: Path | None = None,
    clean_only: bool = False,
    skip_analyse: bool = False,
) -> None:
    """Run the full benchmark pipeline."""
    corpus_dir = Path(settings.corpus_dir)
    if events_dir:
        corpus_dir = events_dir.parent

    pool = await asyncpg.create_pool(settings.postgres_url)

    # Phase 1: CLEAN
    print("=" * 60)
    print("PHASE 1: CLEANUP")
    print("=" * 60)
    await cleanup(pool)

    if clean_only:
        await pool.close()
        print("Cleanup complete.")
        return

    try:
        # Phase 2: INJECT
        print("\n" + "=" * 60)
        print("PHASE 2: INJECT")
        print("=" * 60)
        injection_results = await inject_all(pool, corpus_dir)
        topic_ids = [r["topic_id"] for r in injection_results]
        total_items = sum(r["items_inserted"] for r in injection_results)
        print(f"  Injected {len(injection_results)} events, {total_items} content items")

        if not skip_analyse:
            # Phase 3: ANALYSE
            print("\n" + "=" * 60)
            print("PHASE 3: ANALYSE (enqueue NLP + embedding jobs)")
            print("=" * 60)
            enqueued = await enqueue_analysis_jobs(pool, topic_ids)
            print(f"  Enqueued {enqueued} analyse_content jobs")
            print(f"  Waiting for embeddings (timeout: {settings.analyse_timeout_s}s)...")
            success = await wait_for_embeddings(pool, topic_ids)
            if not success:
                print("  WARNING: Embedding timeout — results may be incomplete")

            # Phase 4: CLUSTER
            print("\n" + "=" * 60)
            print("PHASE 4: CLUSTER")
            print("=" * 60)
            await trigger_clustering(pool, topic_ids)
            print("  Waiting for clustering...")
            await wait_for_clusters(pool, topic_ids)

            # Phase 5: SIGNAL — wait for signal engine to process new clusters
            # Signal engine runs every 5 min on the scheduler. Wait up to 180s
            # (guaranteed to catch at least one signal engine cycle).
            print("\n" + "=" * 60)
            print("PHASE 5: SIGNAL CHECK (waiting up to 180s)")
            print("=" * 60)
            for i in range(18):
                await asyncio.sleep(10)
                async with pool.acquire() as conn:
                    sig_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM signals WHERE topic_id = ANY($1)",
                        topic_ids,
                    )
                if sig_count > 0:
                    print(f"  {sig_count} signal(s) detected after {(i+1)*10}s")
                    break
            else:
                print("  No signals fired within 180s window")

        # Phase 6: MEASURE
        print("\n" + "=" * 60)
        print("PHASE 6: MEASURE")
        print("=" * 60)
        event_files = sorted((corpus_dir / "events").glob("evt_*.yaml"))
        event_results = []

        for event_path, injection_result in zip(event_files, injection_results):
            with open(event_path) as f:
                event = yaml.safe_load(f)
            result = await evaluate_event(pool, injection_result["topic_id"], event)
            event_results.append(result)
            status = "✓ SIGNAL" if result.signal_fired else "✗ NO SIGNAL"
            print(f"  [{status}] {result.event_name[:50]} (ISC={result.achieved_isc})")

        metrics = compute_metrics(event_results)

        # Phase 7: REPORT
        print("\n" + "=" * 60)
        print("PHASE 7: REPORT")
        print("=" * 60)
        results_path = save_results(metrics)
        template_path = fill_template(metrics)
        print(f"  Results: {results_path}")
        print(f"  Report:  {template_path}")

        # Summary
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"  Events:     {metrics.total_events}")
        print(f"  Precision:  {metrics.precision}%")
        print(f"  Recall:     {metrics.recall}%")
        print(f"  F1 Score:   {metrics.f1_score}%")
        print(f"  Median Time Advantage: {metrics.median_time_advantage_hours} hours")
        print(f"  TP={metrics.true_positives} FP={metrics.false_positives} "
              f"FN={metrics.false_negatives} TN={metrics.true_negatives}")

    finally:
        # Phase 8: CLEANUP — remove all benchmark data from production DB
        print("\n" + "=" * 60)
        print("PHASE 8: CLEANUP")
        print("=" * 60)
        await cleanup(pool)
        await pool.close()


def main():
    parser = argparse.ArgumentParser(description="Anveshak Accuracy Benchmark")
    parser.add_argument("--clean-only", action="store_true", help="Only cleanup benchmark data")
    parser.add_argument("--skip-analyse", action="store_true", help="Skip NLP/embedding phase")
    parser.add_argument("--events", type=Path, help="Custom events directory")
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        events_dir=args.events,
        clean_only=args.clean_only,
        skip_analyse=args.skip_analyse,
    ))


if __name__ == "__main__":
    main()
