"""Replay staging, refusal and reset logic - issue #47.

A Replay's whole claim is that detection unfolded in the order the story did.
That claim rests on three things this file pins: an item lands in the stage its
Publication Time belongs to, a stage runs at its own reference time rather than
the wall clock, and a re-run starts from the same state the last one did.

The database seam is covered by tests/integration/test_replay_driver.py. These
are the pure parts, so they run without Docker.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from anveshak.clock import ClockSettings

from scripts.import_corpus import CorpusItem, CorpusSource, ImportSummary
from scripts.replay_corpus import (
    RESET_STATEMENTS,
    DetectionCounts,
    ReplayRefusedError,
    Stage,
    plan_stages,
    run_stage,
    verify_replay_permitted,
)

pytestmark = pytest.mark.unit

# The Cockroach Janta Party arc in #39: founded 16 May 2026.
FOUNDED = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
SOURCE = CorpusSource(handle="https://outlet-a.example/feed", name="Outlet A", platform="web")


def _item(published_at: datetime | None, url: str = "https://outlet-a.example/a") -> CorpusItem:
    return CorpusItem(
        url=url,
        text="Body text of the article.",
        source=SOURCE,
        published_at=published_at,
    )


def _settings(*, enabled: bool = True, environment: str = "replay") -> ClockSettings:
    return ClockSettings(virtual_clock_enabled=enabled, environment=environment)


# ---------------------------------------------------------------------------
# The environment guard
# ---------------------------------------------------------------------------


class TestReplayPermission:
    """A Replay writes backdated detection output, so it is gated like one."""

    def test_permitted_when_flag_on_in_an_allowed_environment(self) -> None:
        verify_replay_permitted(_settings())

    def test_refused_when_the_flag_is_off(self) -> None:
        with pytest.raises(ReplayRefusedError) as exc:
            verify_replay_permitted(_settings(enabled=False))
        assert "VIRTUAL_CLOCK_ENABLED" in str(exc.value)

    def test_refused_outside_the_allowlist_even_with_the_flag_on(self) -> None:
        # The second layer: a Replay .env copied onto a production host is
        # refused because the environment is not on the allowlist.
        with pytest.raises(ReplayRefusedError) as exc:
            verify_replay_permitted(_settings(environment="production"))
        assert "production" in str(exc.value)


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


class TestPlanStages:
    def test_one_week_of_items_is_one_stage(self) -> None:
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=2))]
        stages = plan_stages(items, now=FOUNDED + timedelta(days=30))
        assert len(stages) == 1
        assert stages[0].index == 1
        assert len(stages[0].items) == 2

    def test_stages_are_weekly_and_anchored_on_the_first_publication_day(self) -> None:
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=8))]
        stages = plan_stages(items, now=FOUNDED + timedelta(days=60))
        assert len(stages) == 2
        # Anchored at UTC midnight of the first Publication Time, not at its
        # time of day: a stage boundary an analyst reads is a date.
        assert stages[0].start == datetime(2026, 5, 16, tzinfo=UTC)
        assert stages[0].end == datetime(2026, 5, 23, tzinfo=UTC)
        assert stages[1].start == datetime(2026, 5, 23, tzinfo=UTC)

    def test_an_item_lands_in_the_stage_its_publication_time_belongs_to(self) -> None:
        first = _item(FOUNDED, url="https://outlet-a.example/first")
        second = _item(FOUNDED + timedelta(days=8), url="https://outlet-a.example/second")
        stages = plan_stages([second, first], now=FOUNDED + timedelta(days=60))
        assert [i.url for i in stages[0].items] == ["https://outlet-a.example/first"]
        assert [i.url for i in stages[1].items] == ["https://outlet-a.example/second"]

    def test_items_inside_a_stage_are_ordered_by_publication_time(self) -> None:
        late = _item(FOUNDED + timedelta(days=3), url="https://outlet-a.example/late")
        early = _item(FOUNDED, url="https://outlet-a.example/early")
        stages = plan_stages([late, early], now=FOUNDED + timedelta(days=30))
        assert [i.url for i in stages[0].items] == [
            "https://outlet-a.example/early",
            "https://outlet-a.example/late",
        ]

    def test_a_stage_with_no_items_still_exists(self) -> None:
        # A quiet week is evidence. Dropping it would compress the timeline and
        # make a gap in the story look like a gap in the corpus.
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=15))]
        stages = plan_stages(items, now=FOUNDED + timedelta(days=60))
        assert len(stages) == 3
        assert stages[1].items == ()

    def test_reference_time_is_the_end_of_the_stage(self) -> None:
        stages = plan_stages([_item(FOUNDED)], now=FOUNDED + timedelta(days=60))
        assert stages[0].reference_time == datetime(2026, 5, 23, tzinfo=UTC)
        assert stages[0].clamped is False

    def test_a_reference_time_past_now_is_clamped_rather_than_refused(self) -> None:
        # The clock refuses a reference time in the future, and the last stage
        # of a still-running narrative ends after today. Clamping keeps the
        # Replay runnable; it is reported so the stage is not read as a full
        # week of detection.
        now = FOUNDED + timedelta(days=3)
        stages = plan_stages([_item(FOUNDED)], now=now)
        assert stages[0].reference_time == now
        assert stages[0].clamped is True

    def test_undated_items_run_in_the_first_stage(self) -> None:
        # An undated item cannot sit on a timeline, but its Source still counts
        # toward the independent source count. Dropping it would silently
        # shrink the corpus.
        stages = plan_stages(
            [_item(FOUNDED), _item(None, url="https://outlet-a.example/undated")],
            now=FOUNDED + timedelta(days=30),
        )
        assert len(stages[0].items) == 2
        assert stages[0].undated == 1

    def test_an_item_published_after_now_is_refused(self) -> None:
        # Every stage past today clamps onto the same reference time, which
        # merges their Capture Times and lets the 24 hour Signal dedup swallow
        # the later stage. A future date is a corpus error either way.
        with pytest.raises(ReplayRefusedError) as exc:
            plan_stages(
                [_item(FOUNDED), _item(FOUNDED + timedelta(days=40))],
                now=FOUNDED + timedelta(days=30),
            )
        assert "after now" in str(exc.value)

    def test_a_corpus_with_no_publication_time_at_all_is_refused(self) -> None:
        with pytest.raises(ReplayRefusedError) as exc:
            plan_stages([_item(None)], now=FOUNDED)
        assert "Publication Time" in str(exc.value)

    def test_an_empty_corpus_is_refused(self) -> None:
        with pytest.raises(ReplayRefusedError):
            plan_stages([], now=FOUNDED)

    def test_stage_days_is_configurable(self) -> None:
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=2))]
        stages = plan_stages(items, stage_days=1, now=FOUNDED + timedelta(days=30))
        assert len(stages) == 3

    def test_every_stage_carries_the_total_for_progress_output(self) -> None:
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=8))]
        stages = plan_stages(items, now=FOUNDED + timedelta(days=60))
        assert [s.total for s in stages] == [2, 2]


class TestReportStages:
    def test_a_report_date_attaches_to_the_stage_containing_it(self) -> None:
        items = [_item(FOUNDED), _item(FOUNDED + timedelta(days=8))]
        stages = plan_stages(
            items,
            report_dates=[date(2026, 5, 24)],
            now=FOUNDED + timedelta(days=60),
        )
        assert stages[0].report_dates == ()
        assert stages[1].report_dates == (date(2026, 5, 24),)

    def test_a_report_date_outside_the_corpus_is_refused(self) -> None:
        # Silently generating no report would leave an operator waiting for an
        # artifact that was never going to exist.
        with pytest.raises(ReplayRefusedError) as exc:
            plan_stages(
                [_item(FOUNDED)],
                report_dates=[date(2026, 8, 1)],
                now=FOUNDED + timedelta(days=120),
            )
        assert "2026-08-01" in str(exc.value)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestResetStatements:
    """FK-safe order, org-scoped, and nothing the Replay did not produce."""

    def _index_of(self, fragment: str) -> int:
        for position, (_, sql) in enumerate(RESET_STATEMENTS):
            if fragment in sql:
                return position
        raise AssertionError(f"no reset statement contains {fragment!r}")

    def test_every_statement_is_scoped_by_org(self) -> None:
        for label, sql in RESET_STATEMENTS:
            assert "org_id" in sql, f"{label} deletes across organisations"

    def test_the_cluster_fk_is_nulled_before_clusters_are_deleted(self) -> None:
        # content_items.narrative_cluster_id -> narrative_clusters.id is a
        # cycle. Deleting either side first violates the constraint.
        nulled = self._index_of("SET narrative_cluster_id = NULL")
        clusters = self._index_of("DELETE FROM narrative_clusters")
        assert nulled < clusters

    def test_children_are_deleted_before_their_parents(self) -> None:
        order = [
            "DELETE FROM vision_results",
            "DELETE FROM media_assets",
            "DELETE FROM extracted_entities",
            "DELETE FROM content_items",
        ]
        positions = [self._index_of(fragment) for fragment in order]
        assert positions == sorted(positions)

    def test_report_warnings_are_deleted_before_reports(self) -> None:
        assert self._index_of("DELETE FROM report_source_warnings") < self._index_of(
            "DELETE FROM reports"
        )

    def test_candidate_topics_are_deleted_before_clusters(self) -> None:
        assert self._index_of("DELETE FROM candidate_topics") < self._index_of(
            "DELETE FROM narrative_clusters"
        )

    def test_credibility_is_restored_before_its_audit_trail_is_deleted(self) -> None:
        # Rule 8 says no silent credibility change. The restore reverses changes
        # whose audit rows are deleted in the same transaction, so the log and
        # the score still agree afterwards. Deleting first would strip the
        # evidence of what the score was before the Replay touched it.
        assert self._index_of("UPDATE sources") < self._index_of(
            "DELETE FROM credibility_audit_log"
        )

    def test_topics_and_sources_survive_a_reset(self) -> None:
        # A Watch Space is configuration the Replay imports into, not output it
        # produced, and a Source is global to every organisation.
        for label, sql in RESET_STATEMENTS:
            assert "DELETE FROM topics" not in sql, label
            assert "DELETE FROM sources" not in sql, label

    def test_the_credibility_restore_touches_only_sources_this_org_owns(self) -> None:
        # A Source is global, and the audit row carries the owning organisation
        # rather than the one whose Replay moved the score. A wider restore
        # would overwrite a value another organisation's assessment produced
        # and leave their audit rows describing a score that no longer exists.
        _, sql = RESET_STATEMENTS[self._index_of("UPDATE sources")]
        assert "s.org_id = $1" in sql


# ---------------------------------------------------------------------------
# Report formats
# ---------------------------------------------------------------------------


class TestStageReportTypes:
    """A report point is two artifacts, the brief and the full report - #54.

    The demonstration shows the same Topic reported on at three points, each in
    both formats, and both have to come out of the one Replay: a second run to
    collect the other format would be a second reset, so the first run's
    reports would no longer exist to compare against.
    """

    @staticmethod
    def _stage() -> Stage:
        return plan_stages(
            [_item(FOUNDED), _item(FOUNDED + timedelta(days=8), url="https://outlet-a.example/b")],
            report_dates=[date(2026, 5, 24)],
        )[1]

    async def _run(self, monkeypatch: pytest.MonkeyPatch, report_types: tuple[str, ...]) -> list:
        generated: list[str] = []

        async def fake_import(*args: object, **kwargs: object) -> ImportSummary:
            return ImportSummary(items=1, imported=1, duplicates=0, undated=0, sources_created=1)

        async def fake_detection(*args: object, **kwargs: object) -> DetectionCounts:
            return DetectionCounts(clusters=1, signals=0, candidates=0)

        async def fake_report(*args: object, report_type: str = "", **kwargs: object) -> str:
            generated.append(report_type)
            return f"report-{report_type}"

        async def fake_embed(*args: object, **kwargs: object) -> int:
            return 0

        monkeypatch.setattr("scripts.replay_corpus.import_corpus", fake_import)
        monkeypatch.setattr("scripts.replay_corpus.run_detection", fake_detection)
        monkeypatch.setattr("scripts.replay_corpus.generate_stage_report", fake_report)

        await run_stage(
            self._stage(),
            topic_id="topic",
            org_id="org-demo",
            pool=None,  # type: ignore[arg-type]
            arq_pool=None,  # type: ignore[arg-type]
            corpus_start=FOUNDED,
            embed=fake_embed,
            report_types=report_types,
        )
        return generated

    async def test_both_formats_are_generated_at_a_report_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        generated = await self._run(monkeypatch, ("intelligence_brief", "research_summary"))
        assert generated == ["intelligence_brief", "research_summary"]

    async def test_a_repeated_format_is_generated_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Report immutability (rule 4) means a second generation of the same
        # format at the same moment is either a duplicate row or a silently
        # returned cached one. Neither is what an operator who typed the flag
        # twice meant, and both cost a language model run on CPU.
        generated = await self._run(monkeypatch, ("intelligence_brief", "intelligence_brief"))
        assert generated == ["intelligence_brief"]
