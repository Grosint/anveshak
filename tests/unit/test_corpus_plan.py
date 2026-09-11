"""The corpus plan a demonstration run is measured against - issue #54.

The plan file records what the run is expected to produce before the run
produces anything. That is the whole mechanism: a Signal that does not fire is
a finding only if the expectation was written down first, and an expectation
written down loosely is no expectation at all.

So the rules here are about the file being answerable rather than plausible. A
phase gap loses a week of the arc with nothing to show it went missing, a
report date outside every phase produces an artifact nobody planned for, and a
misspelled Signal type is an expectation that can never fail.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.corpus_plan import DEFAULT_PLAN_PATH, PlanError, load_plan

pytestmark = pytest.mark.unit


def _plan_dict() -> dict[str, Any]:
    return yaml.safe_load(DEFAULT_PLAN_PATH.read_text())


def _write(tmp_path: Path, plan: dict[str, Any]) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False))
    return path


def _loads_with(tmp_path: Path, **changes: Any) -> Any:
    plan = _plan_dict()
    plan.update(changes)
    return load_plan(_write(tmp_path, plan))


def _refuses(tmp_path: Path, fragment: str, **changes: Any) -> None:
    with pytest.raises(PlanError) as exc:
        _loads_with(tmp_path, **changes)
    assert fragment in str(exc.value)


# ---------------------------------------------------------------------------
# The committed plan
# ---------------------------------------------------------------------------


class TestCommittedPlan:
    """The file in the repository is the one the run reads, so it is tested."""

    def test_it_loads(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert plan.name == "Cockroach Janta Party"
        assert plan.start_date == date(2026, 5, 15)

    def test_it_covers_the_arc_in_seven_phases(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert [phase.number for phase in plan.phases] == [1, 2, 3, 4, 5, 6, 7]
        assert plan.phases[0].start == plan.start_date
        assert plan.phases[-1].end == plan.freeze_date

    def test_it_reports_at_three_points_in_both_formats(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert len(plan.report_dates) == 3
        assert plan.report_types == ("intelligence_brief", "research_summary")

    def test_every_expected_signal_names_a_phase_and_a_reason(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert plan.expected_signals
        for expected in plan.expected_signals:
            assert plan.phase(expected.phase).number == expected.phase
            assert expected.reasoning

    def test_its_collection_targets_are_not_pinned_yet(self) -> None:
        # Recorded rather than asserted the other way: the identifiers come
        # from a verification pass against the movement's own site, and this
        # test exists so that pinning them is a visible change to the plan
        # rather than something that happens on a build machine.
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert "collection.canonical_domain" in plan.unpinned()


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


class TestPhases:
    def test_a_gap_between_phases_is_refused(self, tmp_path: Path) -> None:
        # A week nothing claims is a week the run cannot be asked about.
        plan = _plan_dict()
        plan["phases"][1]["start"] = date(2026, 6, 3)
        _refuses(tmp_path, "2026-06-01", phases=plan["phases"])

    def test_overlapping_phases_are_refused(self, tmp_path: Path) -> None:
        # A date in two phases makes "the Signal fired in its phase" ambiguous.
        plan = _plan_dict()
        plan["phases"][1]["start"] = date(2026, 5, 30)
        _refuses(tmp_path, "overlap", phases=plan["phases"])

    def test_a_phase_ending_before_it_starts_is_refused(self, tmp_path: Path) -> None:
        plan = _plan_dict()
        plan["phases"][0]["end"] = date(2026, 5, 14)
        _refuses(tmp_path, "ends before", phases=plan["phases"])

    def test_the_last_phase_must_end_at_the_freeze_date(self, tmp_path: Path) -> None:
        # Otherwise the corpus claims an arc it does not cover.
        plan = _plan_dict()
        plan["phases"][-1]["end"] = date(2026, 9, 6)
        _refuses(tmp_path, "freeze date", phases=plan["phases"])

    def test_phase_lookup_by_date(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert plan.phase_on(date(2026, 7, 20)).number == 4
        assert plan.phase_on(date(2026, 5, 1)) is None


# ---------------------------------------------------------------------------
# Report points
# ---------------------------------------------------------------------------


class TestReportPoints:
    def test_a_report_date_outside_the_arc_is_refused(self, tmp_path: Path) -> None:
        _refuses(tmp_path, "2026-10-01", report_dates=[date(2026, 10, 1)])

    def test_an_unknown_report_type_is_refused(self, tmp_path: Path) -> None:
        # A format the reporter does not know fails hours into a run, at the
        # report point, having already spent the whole Replay getting there.
        _refuses(tmp_path, "executive_summary", report_types=["executive_summary"])

    def test_at_least_one_report_type_is_required(self, tmp_path: Path) -> None:
        _refuses(tmp_path, "report_types", report_types=[])


# ---------------------------------------------------------------------------
# Expectations
# ---------------------------------------------------------------------------


class TestExpectedSignals:
    def test_an_unknown_signal_type_is_refused(self, tmp_path: Path) -> None:
        # An expectation naming a type nothing fires can never fail, so it
        # reads as a passing assertion for the life of the demonstration.
        _refuses(
            tmp_path,
            "amplification_detected",
            expected_signals=[
                {"phase": 1, "signal_type": "amplification_detected", "reasoning": "x"}
            ],
        )

    def test_an_expectation_for_a_phase_that_does_not_exist_is_refused(
        self, tmp_path: Path
    ) -> None:
        _refuses(
            tmp_path,
            "phase 9",
            expected_signals=[{"phase": 9, "signal_type": "new_cluster", "reasoning": "x"}],
        )

    def test_an_expectation_without_a_reason_is_refused(self, tmp_path: Path) -> None:
        # The reason is what a reader uses to decide whether a miss is a defect
        # or a corpus that never contained the evidence.
        _refuses(
            tmp_path,
            "reasoning",
            expected_signals=[{"phase": 1, "signal_type": "new_cluster", "reasoning": ""}],
        )

    def test_no_expected_signal_at_all_is_refused(self, tmp_path: Path) -> None:
        _refuses(tmp_path, "expected_signals", expected_signals=[])


# ---------------------------------------------------------------------------
# Languages and impostor domains
# ---------------------------------------------------------------------------


class TestCollection:
    def test_an_analysed_language_that_is_not_collected_is_refused(self, tmp_path: Path) -> None:
        # Analysis cannot read what collection never brought in, and the
        # mismatch otherwise shows up as a language with no content.
        _refuses(tmp_path, "ta", languages={"collected": ["en", "hi"], "analysed": ["en", "ta"]})

    def test_the_canonical_domain_cannot_also_be_an_impostor(self, tmp_path: Path) -> None:
        plan = _plan_dict()
        plan["collection"]["canonical_domain"] = "movement.example"
        plan["collection"]["impostor_domains"] = ["movement.example"]
        _refuses(tmp_path, "movement.example", collection=plan["collection"])

    def test_unpinned_names_every_identifier_still_to_be_filled(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        unpinned = plan.unpinned()
        assert "collection.social.youtube.channel_id" in unpinned
        assert "collection.social.telegram.channel" in unpinned
        assert "collection.news.outlets" in unpinned
        assert "collection.keywords" in unpinned

    def test_the_build_gate_and_the_social_report_are_separate(self) -> None:
        # A news build refuses on what it reads, and reports what it does not:
        # blocking it on a channel identifier the adapters collect with would
        # be a refusal nobody can act on from the build.
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert "collection.news.outlets" in plan.unpinned_for_build()
        assert "collection.impostor_domains" in plan.unpinned_for_build()
        assert "collection.social.youtube.channel_id" in plan.unpinned_for_social()
        assert not set(plan.unpinned_for_build()) & set(plan.unpinned_for_social())

    def test_a_fully_pinned_plan_reports_nothing_unpinned(self, tmp_path: Path) -> None:
        plan = _plan_dict()
        collection = plan["collection"]
        collection["canonical_domain"] = "movement.example"
        collection["impostor_domains"] = ["movement-official.example"]
        collection["keywords"] = ["the movement"]
        collection["news"]["outlets"] = [
            {"host": "outlet.example", "name": "Outlet", "handle": "https://outlet.example/feed"}
        ]
        collection["social"]["youtube"]["channel_id"] = "UC0000000000000000000000"
        collection["social"]["telegram"]["channel"] = "@movement"
        collection["social"]["x"]["handle"] = "@movement"
        collection["social"]["counter_narrative"]["handles"] = ["@satire"]
        assert _loads_with(tmp_path, collection=collection).unpinned() == []


# ---------------------------------------------------------------------------
# Deny by default
# ---------------------------------------------------------------------------


class TestNewsOutlets:
    def test_one_host_declared_twice_is_refused(self, tmp_path: Path) -> None:
        # Two entries for one host discover the same URLs twice and land the
        # same article under two Sources, which inflates the independent source
        # count a Signal fires on.
        plan = _plan_dict()
        outlet = {"host": "outlet.example", "name": "Outlet", "handle": "https://outlet.example/f"}
        plan["collection"]["news"]["outlets"] = [outlet, dict(outlet, name="Outlet Again")]
        _refuses(tmp_path, "outlet.example", collection=plan["collection"])

    def test_an_outlet_without_a_handle_is_refused(self, tmp_path: Path) -> None:
        # The ingest path looks a Source up by handle and skips an item whose
        # Source it cannot find, so a handle-less outlet collects into nothing.
        plan = _plan_dict()
        plan["collection"]["news"]["outlets"] = [{"host": "outlet.example", "name": "Outlet"}]
        _refuses(tmp_path, "handle", collection=plan["collection"])


class TestPathsAndSurfaces:
    def test_an_empty_surface_nothing_can_count_is_refused(self, tmp_path: Path) -> None:
        # An unknown surface would report empty having queried nothing, which
        # is an expectation that cannot fail.
        _refuses(tmp_path, "deepfake_scores", empty_surfaces=["deepfake_scores"])

    def test_a_declared_path_outside_the_repository_is_refused(self, tmp_path: Path) -> None:
        # The plan is the one input these scripts treat as authoritative, and
        # it names files that are read and a file that is written.
        plan = _plan_dict()
        plan["output"]["corpus_file"] = "../../../tmp/corpus.jsonl"
        _refuses(tmp_path, "outside the repository", output=plan["output"])

    def test_declared_paths_are_absolute_after_loading(self) -> None:
        plan = load_plan(DEFAULT_PLAN_PATH)
        assert plan.corpus_file.is_absolute()
        assert all(path.is_absolute() for path in plan.hand_placed_files)


class TestUnknownKeys:
    def test_an_unknown_top_level_key_is_refused(self, tmp_path: Path) -> None:
        # The same rule the corpus format uses: a key nobody declared is a
        # typo, and a typo read permissively is a field that silently never
        # arrives.
        _refuses(tmp_path, "report_date", report_date=["2026-05-29"])

    def test_an_unknown_phase_key_is_refused(self, tmp_path: Path) -> None:
        plan = _plan_dict()
        plan["phases"][0]["ends"] = date(2026, 5, 31)
        _refuses(tmp_path, "ends", phases=plan["phases"])

    def test_a_missing_required_key_is_refused(self, tmp_path: Path) -> None:
        plan = _plan_dict()
        del plan["freeze_date"]
        with pytest.raises(PlanError) as exc:
            load_plan(_write(tmp_path, plan))
        assert "freeze_date" in str(exc.value)
