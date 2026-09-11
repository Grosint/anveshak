"""Detection runs at a reference time — issue #46, ADR 0003.

The parameter is the seam. These tests call detection with a fixed reference
time and assert the window boundary and the written timestamp directly, and
assert that omitting the parameter takes the current-time path.

No system clock is frozen anywhere here, which is the point.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.clock import ClockOverrideRefusedError, ClockSettings

pytestmark = pytest.mark.unit

# 16 May 2026: the day the narrative in #39 began.
REPLAY_TIME = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)


@pytest.fixture
def clock_on(monkeypatch):
    """Permit the override, as a Replay run does: the flag on, in an
    environment the allowlist names."""
    monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")


def _pool(conn):
    pool = MagicMock()
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acquire
    return pool


def _args_of(call):
    return list(call.args)


# ---------------------------------------------------------------------------
# No detection SQL reads the database's own clock
# ---------------------------------------------------------------------------


class TestEveryDetectorDeclaresTheParameter:
    """The gap this catches: a detector that writes a Signal but was never
    threaded keeps reading the wall clock, and nothing else notices. Cross
    topic convergence shipped that way once."""

    @pytest.mark.parametrize(
        ("module", "function"),
        [
            ("anveshak.analyst.clustering", "run_clustering"),
            ("anveshak.analyst.signal_engine", "check_signals"),
            ("anveshak.analyst.signal_engine", "check_hostility_shifts"),
            ("anveshak.analyst.identifier_signals", "check_identifier_signals"),
            ("anveshak.analyst.template_signals", "check_template_signals"),
            ("anveshak.analyst.manufactured", "check_manufactured_narratives"),
            ("anveshak.analyst.mobilization", "check_mobilization_calls"),
            ("anveshak.analyst.convergence", "check_cross_topic_convergence"),
            ("anveshak.analyst.detection", "detect_candidate_topics"),
            ("anveshak.analyst.credibility", "run_credibility_update"),
            ("anveshak.analyst.credibility", "run_cross_verification_update"),
            ("anveshak.analyst.credibility", "run_contradiction_update"),
        ],
    )
    def test_the_entry_point_takes_a_reference_time_that_defaults_to_none(self, module, function):
        import importlib
        import inspect

        parameters = inspect.signature(
            getattr(importlib.import_module(module), function)
        ).parameters

        assert "reference_time" in parameters, f"{function} still runs on the wall clock only"
        assert parameters["reference_time"].default is None, (
            f"{function} must default to the live path"
        )


class TestDetectionSQLTakesTheClockAsAParameter:
    """A NOW() left in a detection query defeats the whole parameter: the pass
    would read one moment and write another."""

    @pytest.mark.parametrize(
        "module",
        [
            "anveshak.analyst.clustering",
            "anveshak.analyst.signal_engine",
            "anveshak.analyst.signal_writer",
            "anveshak.analyst.template_signals",
            "anveshak.analyst.identifier_signals",
            "anveshak.analyst.mobilization",
            "anveshak.analyst.detection",
            "anveshak.analyst.credibility",
            "anveshak.analyst.convergence",
            "anveshak.analyst.manufactured",
        ],
    )
    def test_no_window_or_write_sql_calls_now(self, module):
        import importlib

        mod = importlib.import_module(module)
        offenders = [
            name
            for name in dir(mod)
            if name.startswith("SQL_") and "NOW()" in (getattr(mod, name) or "")
        ]
        assert offenders == []


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


class TestClusteringWindow:
    @pytest.mark.asyncio
    async def test_the_window_is_measured_from_the_pass_moment(self):
        from anveshak.analyst.clustering import (
            SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED,
            load_unclustered_embeddings,
        )

        conn = AsyncMock()
        conn.fetch.return_value = []

        # `now` is already resolved here: the guard runs once, at the entry
        # point, and a second guard on the way down would refuse the value
        # the entry point just produced.
        await load_unclustered_embeddings(
            "topic-1",
            _pool(conn),
            window_days=30,
            now=REPLAY_TIME,
        )

        conn.fetch.assert_called_once_with(
            SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED,
            "topic-1",
            0.0,
            30,
            REPLAY_TIME,
        )

    @pytest.mark.asyncio
    async def test_omitting_it_uses_the_current_time(self):
        from anveshak.analyst.clustering import load_unclustered_embeddings

        conn = AsyncMock()
        conn.fetch.return_value = []
        before = datetime.now(UTC)

        await load_unclustered_embeddings("topic-1", _pool(conn), window_days=30)

        passed = _args_of(conn.fetch.call_args)[-1]
        assert before <= passed <= datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_an_override_without_the_flag_is_refused(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_CLOCK_ENABLED", raising=False)
        from anveshak.analyst.clustering import run_clustering

        conn = AsyncMock()
        conn.fetchval.return_value = None
        conn.fetch.return_value = []

        with pytest.raises(ClockOverrideRefusedError):
            await run_clustering("topic-1", _pool(conn), reference_time=REPLAY_TIME)

    @pytest.mark.asyncio
    async def test_the_flag_admits_the_override_at_the_entry_point(self, clock_on):
        from anveshak.analyst.clustering import (
            SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED,
            run_clustering,
        )

        conn = AsyncMock()
        conn.fetchval.return_value = None
        conn.fetch.return_value = []

        assert await run_clustering("topic-1", _pool(conn), reference_time=REPLAY_TIME) == []

        window = next(
            c for c in conn.fetch.call_args_list if c.args[0] == SQL_UNCLUSTERED_EMBEDDINGS_WINDOWED
        )
        assert window.args[-1] == REPLAY_TIME

    @pytest.mark.asyncio
    async def test_a_cluster_is_stamped_with_the_reference_time(self, clock_on):
        import numpy as np
        from anveshak.analyst.clustering import (
            SQL_UPSERT_CLUSTER,
            ClusterData,
            upsert_cluster,
        )

        conn = AsyncMock()
        cluster_data = ClusterData(
            content_item_ids=["item-1"],
            source_ids=["source-1"],
            centroid=np.ones(4, dtype=np.float32),
        )

        await upsert_cluster(
            conn=conn,
            topic_id="topic-1",
            cluster_id="cluster-1",
            cluster_data=cluster_data,
            label="Cluster 1",
            now=REPLAY_TIME,
        )

        upsert = next(c for c in conn.execute.call_args_list if c.args[0] == SQL_UPSERT_CLUSTER)
        assert upsert.args[-1] == REPLAY_TIME


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class TestSignalDedupWindow:
    @pytest.mark.asyncio
    async def test_dedup_is_anchored_to_the_reference_time(self):
        from anveshak.analyst.signal_writer import SQL_DUPLICATE_SIGNAL_CHECK, is_duplicate_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await is_duplicate_signal(conn, "cluster-1", "multi_source_convergence", REPLAY_TIME)

        conn.fetchrow.assert_called_once_with(
            SQL_DUPLICATE_SIGNAL_CHECK,
            "cluster-1",
            "multi_source_convergence",
            REPLAY_TIME,
        )

    @pytest.mark.asyncio
    async def test_omitting_it_uses_the_current_time(self):
        from anveshak.analyst.signal_writer import is_duplicate_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None
        before = datetime.now(UTC)

        await is_duplicate_signal(conn, "cluster-1", "multi_source_convergence")

        passed = _args_of(conn.fetchrow.call_args)[-1]
        assert before <= passed <= datetime.now(UTC)


class TestSignalCarriesTheDateItsEvidenceExisted:
    @pytest.mark.asyncio
    async def test_a_fired_signal_is_written_at_the_reference_time(self, clock_on):
        from anveshak.analyst.signal_engine import check_signals

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "cluster_id": "cluster-1",
                "topic_id": "topic-1",
                "label": "A narrative",
                "independent_source_count": 3,
                "signal_threshold": 2,
            }
        ]
        conn.fetchrow.return_value = None  # not a duplicate
        broadcast = AsyncMock()

        fired = await check_signals(_pool(conn), broadcast, reference_time=REPLAY_TIME)

        assert fired == 1
        assert _args_of(conn.execute.call_args)[-1] == REPLAY_TIME

    @pytest.mark.asyncio
    async def test_the_default_path_writes_the_current_time(self):
        from anveshak.analyst.signal_engine import check_signals

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "cluster_id": "cluster-1",
                "topic_id": "topic-1",
                "label": "A narrative",
                "independent_source_count": 3,
                "signal_threshold": 2,
            }
        ]
        conn.fetchrow.return_value = None
        before = datetime.now(UTC)

        await check_signals(_pool(conn), AsyncMock())

        written = _args_of(conn.execute.call_args)[-1]
        assert before <= written <= datetime.now(UTC)


class TestHostilityShiftWindows:
    """Story 2: the shift is measured against the period that preceded it,
    which for a Replay is a period in the past."""

    @pytest.mark.asyncio
    async def test_both_windows_are_measured_from_the_reference_time(self, clock_on):
        from anveshak.analyst.signal_engine import (
            SQL_HOSTILITY_BASELINE,
            SQL_HOSTILITY_RECENT,
            check_hostility_shifts,
        )

        conn = AsyncMock()
        conn.fetch.return_value = [{"id": "topic-1"}]
        # dedup check, then baseline, then recent
        conn.fetchrow.side_effect = [
            None,
            {"baseline_avg": 0.10, "sample_count": 40},
            {"recent_avg": 0.90, "sample_count": 12},
        ]

        fired = await check_hostility_shifts(_pool(conn), AsyncMock(), reference_time=REPLAY_TIME)

        assert fired == 1
        by_sql = {c.args[0]: c.args for c in conn.fetchrow.call_args_list}
        assert by_sql[SQL_HOSTILITY_BASELINE][-1] == REPLAY_TIME
        assert by_sql[SQL_HOSTILITY_RECENT][-1] == REPLAY_TIME
        assert _args_of(conn.execute.call_args)[-1] == REPLAY_TIME


# ---------------------------------------------------------------------------
# Candidate topics
# ---------------------------------------------------------------------------


class TestCandidateTopicDate:
    @pytest.mark.asyncio
    async def test_a_candidate_is_stamped_with_the_reference_time(self, clock_on):
        from anveshak.analyst.detection import SQL_UPSERT_CANDIDATE, detect_candidate_topics

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "cluster_id": "cluster-1",
                "topic_id": "watch-1",
                "watch_space_id": "watch-1",
                "org_id": "org-1",
                "label": "A narrative",
                "centroid_text": "[0.1,0.2]",
                "independent_source_count": 5,
                "item_count": 40,
                "contributing_account_count": 12,
            }
        ]
        # novelty lookup, then the existing-candidate lookup, then the upsert
        conn.fetchrow.side_effect = [
            {"similarity": 0.0},
            None,
            {"id": "candidate-1", "run_count": 3, "status": "pending"},
        ]

        with patch("anveshak.analyst.detection.evaluate_gates") as gates:
            gates.return_value = MagicMock(passed=True, failed_gates=[], measurements={})
            await detect_candidate_topics(_pool(conn), reference_time=REPLAY_TIME)

        upsert = next(
            c for c in conn.fetchrow.call_args_list if c.args and c.args[0] == SQL_UPSERT_CANDIDATE
        )
        assert upsert.args[-1] == REPLAY_TIME


# ---------------------------------------------------------------------------
# Credibility audit log
# ---------------------------------------------------------------------------


class TestCredibilityAuditEntryDate:
    @pytest.mark.asyncio
    async def test_the_deepfake_window_and_audit_row_share_the_reference_time(self, clock_on):
        from anveshak.analyst.credibility import (
            SQL_DEEPFAKE_AMPLIFIERS,
            SQL_INSERT_AUDIT_LOG,
            run_credibility_update,
        )

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "source_id": "source-1",
                "source_name": "An outlet",
                "credibility_score": 80.0,
                "org_id": "org-1",
                "deepfake_count": 3,
            }
        ]
        conn.transaction = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=None)
            )
        )

        updated = await run_credibility_update(_pool(conn), reference_time=REPLAY_TIME)

        assert updated == 1
        window = next(c for c in conn.fetch.call_args_list if c.args[0] == SQL_DEEPFAKE_AMPLIFIERS)
        assert window.args[-1] == REPLAY_TIME
        audit = next(c for c in conn.execute.call_args_list if c.args[0] == SQL_INSERT_AUDIT_LOG)
        # created_at sits before org_id in the audit insert
        assert REPLAY_TIME in audit.args


# ---------------------------------------------------------------------------
# Job arguments
# ---------------------------------------------------------------------------


class TestJobsCarryTheReferenceTime:
    @pytest.mark.asyncio
    async def test_the_clustering_job_passes_a_parsed_reference_time(self, clock_on):
        from anveshak.analyst import jobs

        with (
            patch.object(jobs, "_run_clustering", AsyncMock(return_value=[])) as run,
            patch("arq.create_pool", AsyncMock(return_value=AsyncMock())),
        ):
            await jobs.run_clustering(
                {"db_pool": MagicMock()}, "topic-1", "2026-05-16T09:30:00+00:00"
            )

        assert run.await_args.kwargs["reference_time"] == REPLAY_TIME

    @pytest.mark.asyncio
    async def test_a_live_dispatch_passes_none(self):
        from anveshak.analyst import jobs

        with (
            patch.object(jobs, "_run_clustering", AsyncMock(return_value=[])) as run,
            patch("arq.create_pool", AsyncMock(return_value=AsyncMock())),
        ):
            await jobs.run_clustering({"db_pool": MagicMock()}, "topic-1")

        assert run.await_args.kwargs["reference_time"] is None

    @pytest.mark.asyncio
    async def test_a_typo_in_the_job_argument_is_refused(self, clock_on):
        from anveshak.analyst import jobs

        with pytest.raises(ClockOverrideRefusedError):
            await jobs.detect_candidate_topics_job({"db_pool": MagicMock()}, "16-05-2026")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TestReportGenerationTimestamp:
    @pytest.mark.asyncio
    async def test_generated_at_is_the_moment_generation_ran_at(self, clock_on):
        from anveshak.reporter import db as reporter_db

        conn = AsyncMock()
        conn.execute.return_value = "UPDATE 1"

        stored = await reporter_db.set_report_generated(
            _pool(conn),
            report_id="report-1",
            content_md="# A report",
            confidence_score=0.7,
            geojson={},
            source_snapshot={},
            content_item_count=12,
            now=REPLAY_TIME,
        )

        assert stored is True
        assert _args_of(conn.execute.call_args)[-1] == REPLAY_TIME

    @pytest.mark.asyncio
    async def test_a_refused_override_is_written_onto_the_report(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_CLOCK_ENABLED", raising=False)
        from anveshak.reporter import worker

        pool = MagicMock()
        with patch.object(worker.db, "set_report_failed", AsyncMock()) as failed:
            with pytest.raises(ClockOverrideRefusedError):
                await worker.generate_report({"db": pool}, "report-1", "2026-05-16T09:30:00+00:00")

        # Raising alone would leave generated_at NULL and generation_error
        # NULL, which the API reads as "queued" forever.
        failed.assert_awaited_once()
        assert failed.await_args.args[1] == "report-1"
        assert "VIRTUAL_CLOCK_ENABLED" in failed.await_args.args[2]

    @pytest.mark.asyncio
    async def test_it_defaults_to_the_current_time(self):
        from anveshak.reporter import db as reporter_db

        conn = AsyncMock()
        conn.execute.return_value = "UPDATE 1"
        before = datetime.now(UTC)

        await reporter_db.set_report_generated(
            _pool(conn),
            report_id="report-1",
            content_md="# A report",
            confidence_score=0.7,
            geojson={},
            source_snapshot={},
            content_item_count=12,
        )

        written = _args_of(conn.execute.call_args)[-1]
        assert before <= written <= datetime.now(UTC)


# ---------------------------------------------------------------------------
# One pass, one moment
# ---------------------------------------------------------------------------


class TestOnePassReadsAndWritesOneMoment:
    @pytest.mark.asyncio
    async def test_every_signal_in_a_pass_carries_the_same_timestamp(self, clock_on):
        """A clock read per loop iteration would date rows from the same pass
        differently, which is the drift the parameter exists to remove."""
        from anveshak.analyst.signal_engine import check_signals

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "cluster_id": f"cluster-{n}",
                "topic_id": "topic-1",
                "label": f"Narrative {n}",
                "independent_source_count": 3,
                "signal_threshold": 2,
            }
            for n in range(3)
        ]
        conn.fetchrow.return_value = None

        await check_signals(_pool(conn), AsyncMock(), reference_time=REPLAY_TIME)

        written = {c.args[-1] for c in conn.execute.call_args_list}
        assert written == {REPLAY_TIME}

    def test_the_settings_flag_is_off_without_configuration(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_CLOCK_ENABLED", raising=False)
        assert ClockSettings().virtual_clock_enabled is False

    def test_a_replay_stage_is_a_past_moment(self):
        assert REPLAY_TIME < datetime.now(UTC) - timedelta(days=1)
