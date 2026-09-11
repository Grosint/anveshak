"""What the demonstration run is asserted on - issue #54.

The run is the test, so these are the tests of the test. Each one pins a way an
assertion could pass while the demonstration was wrong: a Signal of the right
type in the wrong phase, three reports sharing one generation timestamp, a
timeline with a hole in the middle of the arc, and a query that forgot to scope
itself to an organisation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.assert_demo_run import (
    SQL_EMPTY_SURFACES,
    SQL_PROMOTED_CANDIDATES,
    SQL_REPORTS,
    SQL_SIGNALS,
    SQL_TIMELINE_BUCKETS,
    SQL_TIMELINE_EXCLUDED,
    check_empty_surfaces,
    check_expected_signals,
    check_promotion,
    check_reports,
    check_timeline,
    report,
)
from scripts.corpus_plan import DEFAULT_PLAN_PATH, load_plan

pytestmark = pytest.mark.unit

PLAN = load_plan(DEFAULT_PLAN_PATH)


def _signal(signal_type: str, when: datetime) -> dict[str, Any]:
    return {"signal_type": signal_type, "created_at": when}


def _every_expected_signal() -> list[dict[str, Any]]:
    """One Signal per expectation, dated in the middle of its phase."""
    rows = []
    for expected in PLAN.expected_signals:
        phase = PLAN.phase(expected.phase)
        middle = phase.start + (phase.end - phase.start) / 2
        rows.append(
            _signal(expected.signal_type, datetime.combine(middle, datetime.min.time(), UTC))
        )
    return rows


# ---------------------------------------------------------------------------
# Organisation scope
# ---------------------------------------------------------------------------


class TestOrgScope:
    def test_every_query_filters_by_organisation(self) -> None:
        # An unscoped query reads another organisation's run, and on a shared
        # host that is a demonstration asserted against somebody else's data.
        queries = [
            SQL_PROMOTED_CANDIDATES,
            SQL_SIGNALS,
            SQL_TIMELINE_BUCKETS,
            SQL_TIMELINE_EXCLUDED,
            SQL_REPORTS,
            *SQL_EMPTY_SURFACES.values(),
        ]
        for sql in queries:
            assert "org_id = $1" in sql

    def test_every_query_is_scoped_to_one_topic(self) -> None:
        # An organisation holds other Topics, and a Signal, a report or a day
        # of content belonging to one of them would otherwise satisfy an
        # expectation about this arc.
        for sql in (
            SQL_SIGNALS,
            SQL_TIMELINE_BUCKETS,
            SQL_TIMELINE_EXCLUDED,
            SQL_REPORTS,
            *SQL_EMPTY_SURFACES.values(),
        ):
            assert "$2" in sql

    def test_the_quality_gate_is_applied_to_the_timeline(self) -> None:
        # The gate is applied at every consumption point, and an assertion is
        # one: counting boilerplate here would pass an arc the workbench does
        # not show.
        assert "content_quality" in SQL_TIMELINE_BUCKETS
        assert "content_quality" in SQL_TIMELINE_EXCLUDED


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


class TestPromotion:
    def test_a_promoted_candidate_passes(self) -> None:
        check = check_promotion([{"watch_space": "Youth Grievance", "run_count": 3}])
        assert check.passed
        assert "Youth Grievance" in check.detail
        # The run count is the persistence gate the promotion passed, and the
        # run sheet narrates it.
        assert "3 detection run(s)" in check.detail

    def test_no_promoted_candidate_fails(self) -> None:
        check = check_promotion([])
        assert not check.passed

    def test_the_query_requires_a_watch_space_and_a_promoted_topic(self) -> None:
        # A candidate raised from an ordinary Topic is not the unaided
        # discovery claim, and one still pending was never promoted.
        assert "is_watch_space = TRUE" in SQL_PROMOTED_CANDIDATES
        assert "promoted_topic_id IS NOT NULL" in SQL_PROMOTED_CANDIDATES
        assert "status = 'accepted'" in SQL_PROMOTED_CANDIDATES


# ---------------------------------------------------------------------------
# Expected Signals
# ---------------------------------------------------------------------------


class TestExpectedSignals:
    def test_every_expectation_met_passes(self) -> None:
        checks = check_expected_signals(_every_expected_signal(), PLAN)
        assert checks
        assert all(check.passed for check in checks)

    def test_a_signal_in_the_wrong_phase_fails_and_says_where_it_fired(self) -> None:
        # The detector working and the evidence landing elsewhere in the arc is
        # a different finding from the detector never firing, and tuning the
        # second when it was the first is how a demonstration measures itself.
        rows = [_signal("mobilization_call", datetime(2026, 8, 15, tzinfo=UTC))]
        checks = {check.name: check for check in check_expected_signals(rows, PLAN)}
        failed = checks["phase 3 mobilization_call"]
        assert not failed.passed
        assert "2026-08-15" in failed.detail

    def test_a_signal_that_never_fired_carries_the_reason_it_was_expected(self) -> None:
        checks = {check.name: check for check in check_expected_signals([], PLAN)}
        failed = checks["phase 4 hostility_shift"]
        assert not failed.passed
        assert "never fired" in failed.detail
        assert "sharpest week" in failed.detail


# ---------------------------------------------------------------------------
# Sentiment Timeline
# ---------------------------------------------------------------------------


class TestTimeline:
    def _bucket(self, when: datetime) -> dict[str, Any]:
        return {"bucket": when, "items": 3}

    def _across_the_arc(self) -> list[dict[str, Any]]:
        return [
            self._bucket(datetime.combine(phase.start, datetime.min.time(), UTC))
            for phase in PLAN.phases
        ]

    def test_buckets_across_every_phase_pass(self) -> None:
        check = check_timeline(self._across_the_arc(), 4, PLAN)
        assert check.passed
        assert "4 item(s) excluded" in check.detail

    def test_a_phase_with_no_bucket_fails(self) -> None:
        buckets = self._across_the_arc()[:-1]
        check = check_timeline(buckets, 0, PLAN)
        assert not check.passed
        assert "phase(s) 7" in check.detail

    def test_an_unknown_excluded_count_fails(self) -> None:
        # An excluded count nobody can state is a chart nobody can judge.
        check = check_timeline(self._across_the_arc(), None, PLAN)
        assert not check.passed


# ---------------------------------------------------------------------------
# Report points
# ---------------------------------------------------------------------------


class TestReports:
    def _rows(self, offset_days: int = 1) -> list[dict[str, Any]]:
        from datetime import timedelta

        rows = []
        for index, report_type in enumerate(PLAN.report_types):
            for reported in PLAN.report_dates:
                generated = datetime.combine(reported, datetime.min.time(), UTC) + timedelta(
                    days=offset_days, hours=index
                )
                rows.append({"report_type": report_type, "generated_at": generated})
        return rows

    def test_both_formats_at_all_three_points_pass(self) -> None:
        checks = check_reports(self._rows(), PLAN)
        assert all(check.passed for check in checks)

    def test_a_missing_format_fails_and_names_the_date(self) -> None:
        rows = [row for row in self._rows() if row["report_type"] == "intelligence_brief"]
        checks = {check.name: check for check in check_reports(rows, PLAN)}
        assert not checks["report points, research_summary"].passed
        assert "2026-05-29" in checks["report points, research_summary"].detail

    def test_two_formats_at_one_point_may_share_a_timestamp(self) -> None:
        # A Replay generates every requested format at one stage's reference
        # time, so the brief and the full report at a point share a
        # generated_at by construction. They are the same moment assessed
        # twice, which is what rule 4 means by a point-in-time snapshot.
        rows = []
        for reported in PLAN.report_dates:
            when = datetime.combine(reported, datetime.min.time(), UTC)
            rows.append({"report_type": "intelligence_brief", "generated_at": when})
            rows.append({"report_type": "research_summary", "generated_at": when})
        checks = {check.name: check for check in check_reports(rows, PLAN)}
        assert all(check.passed for check in checks.values())

    def test_report_points_that_do_not_differ_in_time_fail(self) -> None:
        # Three reports at one moment demonstrate a snapshot rather than an
        # assessment changing over the life of the narrative.
        when = datetime(2026, 5, 30, tzinfo=UTC)
        rows = [{"report_type": "intelligence_brief", "generated_at": when} for _ in range(3)]
        checks = {check.name: check for check in check_reports(rows, PLAN)}
        assert not checks["report points differ in time, intelligence_brief"].passed

    def test_a_report_generated_long_after_its_point_does_not_count(self) -> None:
        # A report generated outside its stage is not the assessment that point
        # in the arc would have produced.
        checks = {check.name: check for check in check_reports(self._rows(offset_days=30), PLAN)}
        assert not checks["report points, intelligence_brief"].passed


# ---------------------------------------------------------------------------
# Empty surfaces
# ---------------------------------------------------------------------------


class TestEmptySurfaces:
    def test_an_empty_surface_passes(self) -> None:
        checks = check_empty_surfaces({"vision_results": 0, "media_assets": 0}, PLAN)
        assert all(check.passed for check in checks)

    def test_every_surface_the_plan_may_declare_has_a_query(self) -> None:
        # Without the pairing, a surface named in a plan and absent here would
        # pass having counted nothing.
        from scripts.corpus_plan import KNOWN_EMPTY_SURFACES

        assert set(SQL_EMPTY_SURFACES) == set(KNOWN_EMPTY_SURFACES)

    def test_a_populated_surface_fails(self) -> None:
        # Asserted rather than ignored: a surface the plan said would be empty
        # and is not means the corpus is not what the plan describes.
        checks = {
            check.name: check
            for check in check_empty_surfaces({"vision_results": 2, "media_assets": 0}, PLAN)
        }
        assert not checks["vision_results is empty"].passed


# ---------------------------------------------------------------------------
# Exit code
# ---------------------------------------------------------------------------


class TestReporting:
    def test_all_passing_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert report([check_promotion([{"watch_space": "Youth Grievance", "run_count": 2}])]) == 0

    def test_any_failure_exits_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert report([check_promotion([])]) == 1
        assert "tuning_history" in capsys.readouterr().out
