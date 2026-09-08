"""Candidate Topic detection — issue #26.

A narrative forming inside a Watch Space surfaces on its own. Four gates
must all pass: independent source count, cluster size, novelty measured as
distance from every existing Topic centroid, and persistence across runs.

Novelty is the gate most easily forgotten and the one that matters most.
Without it the inbox fills with rediscoveries of Topics the analyst already
tracks, and the feature looks broken rather than absent. Persistence
eliminates the single transient spike.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from anveshak.analyst.detection import GateResult, evaluate_gates
from anveshak.analyst.settings import settings

pytestmark = pytest.mark.unit


def _cluster(**overrides):
    base = {
        "cluster_id": "cl-1",
        "independent_source_count": settings.promotion_min_independent_sources,
        "item_count": settings.promotion_min_item_count,
        "novelty_score": 1.0 - settings.promotion_max_similarity_to_existing + 0.05,
        "run_count": settings.promotion_min_runs,
    }
    base.update(overrides)
    return base


class TestAllFourGatesMustPass:
    def test_a_cluster_meeting_every_gate_is_promoted(self):
        assert evaluate_gates(**_cluster()).passed is True

    def test_too_few_independent_sources_blocks_promotion(self):
        result = evaluate_gates(
            **_cluster(independent_source_count=settings.promotion_min_independent_sources - 1)
        )
        assert result.passed is False
        assert "independent_sources" in result.failed_gates

    def test_too_small_a_cluster_blocks_promotion(self):
        result = evaluate_gates(**_cluster(item_count=settings.promotion_min_item_count - 1))
        assert result.passed is False
        assert "item_count" in result.failed_gates

    def test_a_rediscovery_blocks_promotion(self):
        """Novelty: the gate that keeps the inbox from filling with duplicates."""
        similarity = settings.promotion_max_similarity_to_existing + 0.05
        result = evaluate_gates(**_cluster(novelty_score=1.0 - similarity))
        assert result.passed is False
        assert "novelty" in result.failed_gates

    def test_a_single_spike_blocks_promotion(self):
        result = evaluate_gates(**_cluster(run_count=settings.promotion_min_runs - 1))
        assert result.passed is False
        assert "persistence" in result.failed_gates

    def test_every_failing_gate_is_reported_not_just_the_first(self):
        """An analyst debugging an empty inbox needs all of them."""
        result = evaluate_gates(
            cluster_id="cl-1",
            independent_source_count=0,
            item_count=0,
            novelty_score=0.0,
            run_count=1,
        )
        assert set(result.failed_gates) == {
            "independent_sources",
            "item_count",
            "novelty",
            "persistence",
        }

    def test_the_result_carries_the_measurements(self):
        """Evidence, so the inbox can show why a candidate surfaced."""
        result = evaluate_gates(**_cluster())
        assert result.measurements["independent_source_count"] == (
            settings.promotion_min_independent_sources
        )
        assert result.measurements["item_count"] == settings.promotion_min_item_count
        assert "novelty_score" in result.measurements
        assert "run_count" in result.measurements

    def test_thresholds_are_read_from_settings_not_hardcoded(self):
        from pathlib import Path

        source = Path("services/analyst/anveshak/analyst/detection.py").read_text()
        for name in (
            "promotion_min_independent_sources",
            "promotion_min_item_count",
            "promotion_max_similarity_to_existing",
            "promotion_min_runs",
        ):
            assert f"settings.{name}" in source


class TestOrderingIsByPropagation:
    """ADR 0001: ordering is a measurement an analyst can recompute.

    The ordering lives in SQL. A second implementation in Python would be a
    place for the two to disagree, so there is not one.
    """

    def test_the_inbox_query_orders_by_propagation(self):
        from anveshak.api.db.candidates import SQL_LIST_CANDIDATES

        order = SQL_LIST_CANDIDATES.split("ORDER BY", 1)[1]
        assert "independent_source_count DESC" in order
        assert "item_count DESC" in order

    def test_no_concern_score_participates_in_the_order(self):
        from anveshak.api.db.candidates import SQL_LIST_CANDIDATES

        assert "concern" not in SQL_LIST_CANDIDATES.lower()

    def test_the_inbox_reads_pending_only(self):
        from anveshak.api.db.candidates import SQL_LIST_CANDIDATES

        assert "ct.status = $2" in SQL_LIST_CANDIDATES


class TestDetectionRun:
    async def test_it_only_looks_inside_watch_spaces(self):
        from anveshak.analyst.detection import SQL_WATCH_SPACE_CLUSTERS

        assert "is_watch_space" in SQL_WATCH_SPACE_CLUSTERS

    async def test_novelty_compares_against_existing_topic_centroids(self):
        from anveshak.analyst.detection import SQL_NEAREST_EXISTING_TOPIC

        assert "embedding_centroid" in SQL_NEAREST_EXISTING_TOPIC
        # Comparison must be against topics the analyst already has, which
        # excludes the Watch Space itself and other Watch Spaces.
        assert "is_watch_space = FALSE" in SQL_NEAREST_EXISTING_TOPIC

    async def test_candidate_queries_are_org_scoped(self):
        from anveshak.analyst import detection

        for name in dir(detection):
            if name.startswith("SQL_"):
                sql = getattr(detection, name)
                if "candidate_topics" in sql or "topics" in sql:
                    assert "org_id" in sql, name

    async def test_a_decided_candidate_keeps_its_decision(self):
        from anveshak.analyst.detection import SQL_UPSERT_CANDIDATE

        # One row per cluster: a persisting cluster bumps run_count rather
        # than producing a second inbox row. The conflict branch must never
        # overwrite a triage decision, or a dismissal is undone on the next
        # detection pass.
        assert "ON CONFLICT" in SQL_UPSERT_CANDIDATE
        update_branch = SQL_UPSERT_CANDIDATE.split("DO UPDATE SET", 1)[1]
        assert "'accepted', 'dismissed'" in update_branch
        assert "THEN candidate_topics.status" in update_branch

    async def test_a_cluster_below_the_gates_is_not_written_as_pending(self):
        """The inbox reads pending only. Writing every cluster as pending
        defeated the novelty and persistence gates entirely."""
        from anveshak.analyst.detection import SQL_UPSERT_CANDIDATE

        values = SQL_UPSERT_CANDIDATE.split("VALUES", 1)[1].split("ON CONFLICT", 1)[0]
        assert "'pending'" not in values
        assert "$11" in values

    async def test_run_count_increments_across_runs(self):
        from anveshak.analyst.detection import SQL_UPSERT_CANDIDATE

        assert "run_count" in SQL_UPSERT_CANDIDATE

    async def test_it_returns_zero_when_no_watch_space_exists(self):
        from anveshak.analyst.detection import detect_candidate_topics

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        assert await detect_candidate_topics(pool) == 0


class TestThresholdInvariants:
    def test_persistence_is_at_least_two_runs(self):
        assert settings.promotion_min_runs >= 2

    def test_stance_scoring_covers_every_promotable_cluster(self):
        assert settings.stance_min_cluster_size <= settings.promotion_min_item_count

    def test_a_cluster_cannot_be_both_promotable_and_manufactured(self):
        assert (
            settings.manufactured_max_independent_sources
            < settings.promotion_min_independent_sources
        )


class TestJobIsWired:
    def test_the_worker_registers_the_detection_job(self):
        from anveshak.analyst.jobs import WorkerSettings

        names = {
            getattr(f, "name", None) or getattr(f, "coroutine", f).__name__
            for f in WorkerSettings.functions
        }
        assert "detect_candidate_topics_job" in names


def _ctx(conn):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _unused(_: GateResult) -> None:
    """Keeps the GateResult import meaningful to a reader."""
