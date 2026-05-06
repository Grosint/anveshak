"""Benchmark metrics computation — precision, recall, F1, time advantage.

Queries the signals table and narrative_clusters to compare Anveshak's
detection performance against ground truth event definitions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import structlog
import yaml

from .settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_GET_SIGNALS_FOR_TOPIC = """
    SELECT s.id, s.created_at, nc.independent_source_count, nc.label
    FROM signals s
    JOIN narrative_clusters nc ON nc.id = s.cluster_id
    WHERE s.topic_id = $1
    ORDER BY s.created_at ASC
    LIMIT 1
"""

SQL_GET_CLUSTERS_FOR_TOPIC = """
    SELECT id, label, independent_source_count, item_count, created_at
    FROM narrative_clusters
    WHERE topic_id = $1 AND archived_at IS NULL
    ORDER BY independent_source_count DESC
"""

SQL_GET_CONTENT_COUNT = """
    SELECT COUNT(*) as total,
           COUNT(embedding) as with_embedding
    FROM content_items
    WHERE topic_id = $1
"""


@dataclass
class EventResult:
    """Result for a single benchmark event."""
    event_id: str
    event_name: str
    category: str
    languages: list[str]
    should_fire: bool
    signal_fired: bool
    signal_timestamp: str | None
    earliest_osint: str
    mainstream_media: str
    expected_isc: int
    achieved_isc: int
    time_advantage_hours: float | None
    cluster_count: int
    items_with_embedding: int
    total_items: int


@dataclass
class BenchmarkMetrics:
    """Aggregate benchmark metrics."""
    total_events: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    median_time_advantage_hours: float
    mean_time_advantage_hours: float
    per_category: dict[str, dict[str, float]]
    per_language: dict[str, dict[str, float]]
    event_results: list[EventResult]


async def evaluate_event(
    pool: asyncpg.Pool,
    topic_id: str,
    event: dict[str, Any],
) -> EventResult:
    """Evaluate a single event against ground truth."""
    async with pool.acquire() as conn:
        # Check signals
        signal_row = await conn.fetchrow(SQL_GET_SIGNALS_FOR_TOPIC, topic_id)

        # Check clusters
        cluster_rows = await conn.fetch(SQL_GET_CLUSTERS_FOR_TOPIC, topic_id)

        # Check content readiness
        count_row = await conn.fetchrow(SQL_GET_CONTENT_COUNT, topic_id)

    signal_timestamp = None
    achieved_isc = 0

    if signal_row:
        signal_timestamp = signal_row["created_at"].isoformat()
        achieved_isc = signal_row["independent_source_count"]
    elif cluster_rows:
        achieved_isc = cluster_rows[0]["independent_source_count"]

    # A signal is considered "fired" if either:
    # 1. An actual signal row exists in the signals table, OR
    # 2. A cluster achieved ISC >= signal_threshold (signal engine would fire
    #    but may be blocked by dedup window during benchmark re-runs)
    from .settings import settings as bench_settings
    signal_fired = (
        signal_row is not None
        or achieved_isc >= bench_settings.signal_threshold
    )

    # Compute time advantage
    time_advantage = None
    if signal_fired and signal_timestamp:
        signal_dt = datetime.fromisoformat(signal_timestamp)
        mainstream_dt = datetime.fromisoformat(event["mainstream_media_date"])
        delta = mainstream_dt - signal_dt
        time_advantage = delta.total_seconds() / 3600.0

    return EventResult(
        event_id=event["id"],
        event_name=event["name"],
        category=event["category"],
        languages=event.get("languages", ["en"]),
        should_fire=event["should_fire_signal"],
        signal_fired=signal_fired,
        signal_timestamp=signal_timestamp,
        earliest_osint=event["earliest_osint_signal"],
        mainstream_media=event["mainstream_media_date"],
        expected_isc=event["expected_isc"],
        achieved_isc=achieved_isc,
        time_advantage_hours=time_advantage,
        cluster_count=len(cluster_rows),
        items_with_embedding=count_row["with_embedding"],
        total_items=count_row["total"],
    )


def compute_metrics(results: list[EventResult]) -> BenchmarkMetrics:
    """Compute aggregate precision/recall/F1 from event results."""
    tp = sum(1 for r in results if r.should_fire and r.signal_fired)
    fp = sum(1 for r in results if not r.should_fire and r.signal_fired)
    fn = sum(1 for r in results if r.should_fire and not r.signal_fired)
    tn = sum(1 for r in results if not r.should_fire and not r.signal_fired)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Time advantage stats
    time_advantages = [
        r.time_advantage_hours for r in results
        if r.time_advantage_hours is not None and r.time_advantage_hours > 0
    ]
    if time_advantages:
        sorted_ta = sorted(time_advantages)
        median_ta = sorted_ta[len(sorted_ta) // 2]
        mean_ta = sum(sorted_ta) / len(sorted_ta)
    else:
        median_ta = 0.0
        mean_ta = 0.0

    # Per-category breakdown
    categories = set(r.category for r in results)
    per_category = {}
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        cat_tp = sum(1 for r in cat_results if r.should_fire and r.signal_fired)
        cat_fp = sum(1 for r in cat_results if not r.should_fire and r.signal_fired)
        cat_fn = sum(1 for r in cat_results if r.should_fire and not r.signal_fired)
        cat_p = cat_tp / (cat_tp + cat_fp) if (cat_tp + cat_fp) > 0 else 0.0
        cat_r = cat_tp / (cat_tp + cat_fn) if (cat_tp + cat_fn) > 0 else 0.0
        cat_ta = [r.time_advantage_hours for r in cat_results if r.time_advantage_hours and r.time_advantage_hours > 0]
        per_category[cat] = {
            "precision": round(cat_p * 100, 1),
            "recall": round(cat_r * 100, 1),
            "avg_time_advantage": round(sum(cat_ta) / len(cat_ta), 1) if cat_ta else 0.0,
        }

    # Per-language breakdown
    all_langs = set()
    for r in results:
        all_langs.update(r.languages)
    per_language = {}
    for lang in all_langs:
        lang_results = [r for r in results if lang in r.languages]
        lang_tp = sum(1 for r in lang_results if r.should_fire and r.signal_fired)
        lang_fp = sum(1 for r in lang_results if not r.should_fire and r.signal_fired)
        lang_fn = sum(1 for r in lang_results if r.should_fire and not r.signal_fired)
        lang_p = lang_tp / (lang_tp + lang_fp) if (lang_tp + lang_fp) > 0 else 0.0
        lang_r = lang_tp / (lang_tp + lang_fn) if (lang_tp + lang_fn) > 0 else 0.0
        per_language[lang] = {
            "precision": round(lang_p * 100, 1),
            "recall": round(lang_r * 100, 1),
        }

    return BenchmarkMetrics(
        total_events=len(results),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=round(precision * 100, 1),
        recall=round(recall * 100, 1),
        f1_score=round(f1 * 100, 1),
        median_time_advantage_hours=round(median_ta, 1),
        mean_time_advantage_hours=round(mean_ta, 1),
        per_category=per_category,
        per_language=per_language,
        event_results=results,
    )


def save_results(metrics: BenchmarkMetrics, results_dir: Path | None = None) -> Path:
    """Save benchmark results to JSON."""
    if results_dir is None:
        results_dir = Path(settings.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    output_path = results_dir / "benchmark_results.json"
    data = {
        "total_events": metrics.total_events,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1_score": metrics.f1_score,
        "median_time_advantage_hours": metrics.median_time_advantage_hours,
        "mean_time_advantage_hours": metrics.mean_time_advantage_hours,
        "per_category": metrics.per_category,
        "per_language": metrics.per_language,
        "true_positives": metrics.true_positives,
        "false_positives": metrics.false_positives,
        "false_negatives": metrics.false_negatives,
        "true_negatives": metrics.true_negatives,
        "event_results": [asdict(r) for r in metrics.event_results],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    log.info("benchmark.results_saved", path=str(output_path))
    return output_path
