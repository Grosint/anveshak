"""Wall-clock detection is suspended on a Replay host - issue #47.

A Replay stage writes detection rows dated months ago. A live pass running
beside it writes rows dated today, and the two corrupt each other in ways that
are silent:

  - The 24h Signal dedup window is measured back from the pass's reference
    time and has no upper bound, so one Signal fired today suppresses every
    stage Signal for that cluster for the rest of the Replay.
  - The persistence gate counts detection passes, so an hourly live pass
    promotes a Candidate Topic the Replay's own stages never promoted.
  - A re-run after a reset would not reproduce the first run, because the
    number of live passes that landed between stages differs.

So every loop and cron that writes detection output at the wall clock stops
where VIRTUAL_CLOCK_ENABLED is on, and says why.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from anveshak.clock import ClockSettings, live_detection_suspended

pytestmark = pytest.mark.unit


def _settings(*, enabled: bool) -> ClockSettings:
    return ClockSettings(virtual_clock_enabled=enabled, environment="replay")


class TestLiveDetectionSuspended:
    def test_not_suspended_on_a_normal_deployment(self) -> None:
        assert live_detection_suspended(_settings(enabled=False)) is None

    def test_suspended_where_the_clock_override_is_on(self) -> None:
        reason = live_detection_suspended(_settings(enabled=True))
        assert reason is not None
        assert "VIRTUAL_CLOCK_ENABLED" in reason


class TestSchedulerLoops:
    """Each loop returns rather than sleeping, so the task ends at startup."""

    @pytest.fixture(autouse=True)
    def clock_on(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
        monkeypatch.setenv("ENVIRONMENT", "replay")

    async def test_cluster_loop_stops(self) -> None:
        from anveshak.analyst.scheduler import cluster_loop

        pool, redis = MagicMock(), MagicMock()
        await cluster_loop(pool, redis)
        pool.acquire.assert_not_called()

    async def test_signal_check_loop_stops(self) -> None:
        from anveshak.analyst.scheduler import signal_check_loop

        pool = MagicMock()
        await signal_check_loop(pool)
        pool.acquire.assert_not_called()

    async def test_convergence_loop_stops(self) -> None:
        from anveshak.analyst.scheduler import convergence_loop

        pool = MagicMock()
        await convergence_loop(pool)
        pool.acquire.assert_not_called()


class TestCronJobs:
    """A live dispatch carries no reference time. That is what identifies it."""

    @pytest.fixture(autouse=True)
    def clock_on(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
        monkeypatch.setenv("ENVIRONMENT", "replay")

    async def test_candidate_detection_skips_a_live_dispatch(self, monkeypatch) -> None:
        from anveshak.analyst import jobs

        detect = AsyncMock(return_value=1)
        monkeypatch.setattr(jobs, "detect_candidate_topics", detect)
        written = await jobs.detect_candidate_topics_job({"db_pool": MagicMock()})
        assert written == 0
        detect.assert_not_awaited()

    async def test_candidate_detection_still_runs_for_a_replay_stage(self, monkeypatch) -> None:
        from anveshak.analyst import jobs

        detect = AsyncMock(return_value=3)
        monkeypatch.setattr(jobs, "detect_candidate_topics", detect)
        written = await jobs.detect_candidate_topics_job(
            {"db_pool": MagicMock()}, "2026-05-23T00:00:00+00:00"
        )
        assert written == 3
        detect.assert_awaited_once()

    async def test_contradiction_scoring_skips_a_live_dispatch(self, monkeypatch) -> None:
        from anveshak.analyst import jobs

        update = AsyncMock(return_value=2)
        monkeypatch.setattr(jobs, "run_contradiction_update", update)
        await jobs.run_contradiction_scoring({"db_pool": MagicMock()})
        update.assert_not_awaited()

    async def test_credibility_update_skips_a_live_dispatch(self, monkeypatch) -> None:
        from anveshak.analyst import jobs

        update = AsyncMock()
        monkeypatch.setattr(jobs, "run_credibility_update", update)
        await jobs.update_source_credibility({"db_pool": MagicMock()})
        update.assert_not_awaited()


class TestScheduledReports:
    """A Replay generates its own reports, one at a time, at a stage's clock."""

    @pytest.fixture(autouse=True)
    def clock_on(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
        monkeypatch.setenv("ENVIRONMENT", "replay")

    async def test_the_cron_skips_a_replay_host(self) -> None:
        from anveshak.reporter.worker import check_scheduled_reports

        pool = MagicMock()
        await check_scheduled_reports({"db": pool})
        pool.acquire.assert_not_called()


class TestLiveDeploymentUnchanged:
    """The flag is off everywhere else, and nothing here fires then."""

    @pytest.fixture(autouse=True)
    def clock_off(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_CLOCK_ENABLED", raising=False)

    async def test_candidate_detection_runs(self, monkeypatch) -> None:
        from anveshak.analyst import jobs

        detect = AsyncMock(return_value=4)
        monkeypatch.setattr(jobs, "detect_candidate_topics", detect)
        written = await jobs.detect_candidate_topics_job({"db_pool": MagicMock()})
        assert written == 4
        detect.assert_awaited_once()
