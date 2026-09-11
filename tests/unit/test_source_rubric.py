"""Structural Source credibility rubric - issue #51, ADR 0004.

A Source's baseline comes from verifiable properties of the outlet, never
from a judgement about its editorial line. Two outlets with opposing
politics and the same structural properties get the same baseline, and
these tests are the reason that stays true.

Movement away from the baseline comes only from behaviour observed in the
platform, through the audited drop and boost functions. Nothing here
assigns a score; it computes the number those functions start from.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from anveshak.source_rubric import (
    RubricError,
    baseline_for_handle,
    creation_score,
    declaration_for,
    load_rubric,
)

pytestmark = pytest.mark.unit

# Words that would make a baseline a political judgement rather than a
# structural one. Used on the criteria and on the per-outlet assessments,
# since the assessments are where a preference would actually enter.
VIEWPOINT_WORDS = (
    "left",
    "right-wing",
    "liberal",
    "conservative",
    "nationalist",
    "pro-government",
    "anti-government",
    "opposition",
    "ruling party",
    "communal",
    "secular",
)


@pytest.fixture
def temp_rubric(tmp_path, monkeypatch):
    """Write a rubric file and point the loader at it.

    Returns a writer, so a test states the rubric it is about rather than
    reading one written for a different test.
    """

    def write(document: dict) -> Path:
        path = tmp_path / "source_rubric.yaml"
        path.write_text(yaml.safe_dump(document, allow_unicode=True))
        monkeypatch.setenv("SOURCE_RUBRIC_PATH", str(path))
        load_rubric.cache_clear()
        return path

    yield write
    load_rubric.cache_clear()


def _rubric(**overrides) -> dict:
    document = {
        "version": 1,
        "updated": "2026-09-11",
        "owner": "customer",
        "baseline": 50.0,
        "criteria": [
            {
                "id": "named_editorial_responsibility",
                "label": "Named editorial responsibility",
                "test": "The masthead names an editor and gives a contactable address.",
                "points": 10,
            },
            {
                "id": "no_named_authors",
                "label": "No named authors",
                "test": "Items carry no author, or only a desk name.",
                "points": -8,
            },
        ],
        "outlets": [],
    }
    document.update(overrides)
    return document


class TestTheRubricIsAVersionedFile:
    def test_the_shipped_file_loads(self):
        rubric = load_rubric()
        assert rubric.version >= 1
        assert rubric.criteria

    def test_the_customer_owns_it(self):
        assert load_rubric().owner == "customer"

    def test_the_path_is_a_setting(self):
        from anveshak.source_rubric_settings import SourceRubricSettings

        assert SourceRubricSettings().source_rubric_path

    def test_no_outlet_is_named_in_code(self):
        """The vendor ships the rubric, and the customer owns the list."""
        source = (
            (Path(__file__).resolve().parents[2] / "sdk" / "anveshak" / "source_rubric.py")
            .read_text()
            .lower()
        )
        for outlet_word in ("ndtv", "the hindu", "reuters", "opindia", "altnews"):
            assert outlet_word not in source


class TestCriteriaAreStructural:
    @pytest.fixture
    def rubric(self):
        return load_rubric()

    def test_every_criterion_states_how_it_is_checked(self, rubric):
        """A criterion nobody can check is an opinion with a number on it."""
        for criterion in rubric.criteria:
            assert criterion.test.strip()
            assert criterion.label.strip()

    def test_no_criterion_is_worth_nothing(self, rubric):
        for criterion in rubric.criteria:
            assert criterion.points != 0

    def test_no_criterion_names_a_political_position(self, rubric):
        """A viewpoint criterion makes the baseline a political judgement."""
        for criterion in rubric.criteria:
            text = f"{criterion.id} {criterion.label} {criterion.test}".lower()
            for word in VIEWPOINT_WORDS:
                assert word not in text, f"{criterion.id} scores a viewpoint"

    def test_no_criterion_names_an_outlet_or_a_proprietor(self, rubric):
        for criterion in rubric.criteria:
            text = f"{criterion.id} {criterion.label} {criterion.test}".lower()
            for outlet_word in ("ndtv", "the hindu", "reuters", "opindia", "altnews"):
                assert outlet_word not in text


class TestTheBaselineIsComputed:
    def test_an_outlet_meeting_nothing_sits_at_the_neutral_baseline(self, temp_rubric):
        temp_rubric(_rubric())
        assert load_rubric().baseline_for([]) == 50.0

    def test_points_add_to_the_baseline(self, temp_rubric):
        temp_rubric(_rubric())
        assert load_rubric().baseline_for(["named_editorial_responsibility"]) == 60.0

    def test_a_penalty_subtracts(self, temp_rubric):
        temp_rubric(_rubric())
        assert load_rubric().baseline_for(["no_named_authors"]) == 42.0

    def test_the_order_of_the_properties_does_not_change_the_score(self, temp_rubric):
        temp_rubric(_rubric())
        rubric = load_rubric()
        forwards = rubric.baseline_for(["named_editorial_responsibility", "no_named_authors"])
        backwards = rubric.baseline_for(["no_named_authors", "named_editorial_responsibility"])
        assert forwards == backwards

    def test_the_score_is_clamped_to_the_percentage_range(self, temp_rubric):
        temp_rubric(
            _rubric(
                criteria=[
                    {"id": "huge", "label": "Huge", "test": "x", "points": 400},
                    {"id": "tiny", "label": "Tiny", "test": "x", "points": -400},
                ]
            )
        )
        rubric = load_rubric()
        assert rubric.baseline_for(["huge"]) == 100.0
        assert rubric.baseline_for(["tiny"]) == 0.0

    def test_an_unknown_property_is_refused(self, temp_rubric):
        """Silently ignoring it would score an outlet on fewer properties
        than the file says it has, and the number would still look right."""
        temp_rubric(_rubric())
        with pytest.raises(RubricError, match="not_a_criterion"):
            load_rubric().baseline_for(["not_a_criterion"])


class TestTheShippedFileClaimsNothingAboutAnyOutlet:
    """The neutrality risk is not in the criteria, it is in the list.

    A criterion naming a political position would be obvious. Differential
    point-awarding between structurally similar outlets would not, and that
    lives in `outlets`, which the vendor ships empty and the customer owns.
    """

    def test_the_vendor_ships_no_assessment(self):
        assert load_rubric().outlets == []

    def test_no_declaration_carries_a_viewpoint_word(self):
        """Holds for a customer-edited file too, wherever this runs."""
        for outlet in load_rubric().outlets:
            text = f"{outlet.name} {outlet.note}".lower()
            for word in VIEWPOINT_WORDS:
                assert word not in text, f"{outlet.handle} is assessed on a viewpoint"


class TestCriteriaThatContradictEachOther:
    def test_an_outlet_cannot_both_carry_bylines_and_carry_none(self, temp_rubric):
        temp_rubric(
            _rubric(
                criteria=[
                    {
                        "id": "bylines_on_items",
                        "label": "Bylines",
                        "test": "x",
                        "points": 4,
                        "exclusive_with": ["no_named_authors"],
                    },
                    {
                        "id": "no_named_authors",
                        "label": "No named authors",
                        "test": "x",
                        "points": -6,
                    },
                ]
            )
        )
        with pytest.raises(RubricError, match="contradict"):
            load_rubric().baseline_for(["bylines_on_items", "no_named_authors"])

    def test_a_repeated_property_is_refused_rather_than_counted_twice(self, temp_rubric):
        """A hand-edited file duplicates by copy-paste, and the doubled score
        looks exactly like an assessed one."""
        temp_rubric(_rubric())
        with pytest.raises(RubricError, match="more than once"):
            load_rubric().baseline_for(
                ["named_editorial_responsibility", "named_editorial_responsibility"]
            )

    def test_the_shipped_exclusions_are_the_expected_ones(self):
        """Symmetry alone passes a graph with edges missing, and a missing
        edge is exactly how a contradictory declaration loads and scores."""
        expected = {
            "ownership_disclosed": {"anonymous_ownership"},
            "anonymous_ownership": {
                "ownership_disclosed",
                "named_editorial_responsibility",
                "registered_publishing_entity",
            },
            "named_editorial_responsibility": {"anonymous_ownership", "unidentifiable_operator"},
            "registered_publishing_entity": {"anonymous_ownership"},
            "unidentifiable_operator": {"named_editorial_responsibility"},
            "bylines_on_items": {"no_named_authors"},
            "no_named_authors": {"bylines_on_items"},
            "corrections_policy_published": {"no_corrections_mechanism"},
            "no_corrections_mechanism": {"corrections_policy_published"},
            "original_reporting": {"unattributed_republication"},
            "unattributed_republication": {"original_reporting"},
            "opinion_and_sponsorship_labelled": {"undisclosed_paid_content"},
            "undisclosed_paid_content": {"opinion_and_sponsorship_labelled"},
        }
        actual = {c.id: set(c.exclusive_with) for c in load_rubric().criteria if c.exclusive_with}
        assert actual == expected

    def test_a_criterion_requiring_an_identifiable_person_excludes_anonymity(self):
        """The three combinations that used to load and produce a number."""
        rubric = load_rubric()
        for pair in (
            ["named_editorial_responsibility", "anonymous_ownership"],
            ["registered_publishing_entity", "anonymous_ownership"],
            ["unidentifiable_operator", "named_editorial_responsibility"],
        ):
            with pytest.raises(RubricError, match="contradict"):
                rubric.baseline_for(pair)

    def test_every_shipped_pair_is_declared_on_both_sides(self):
        """A one-sided declaration only catches the order it was written in."""
        rubric = load_rubric()
        by_id = {c.id: c for c in rubric.criteria}
        for criterion in rubric.criteria:
            for other in criterion.exclusive_with:
                assert other in by_id, f"{criterion.id} excludes a criterion that is not defined"
                assert criterion.id in by_id[other].exclusive_with


class TestABadFileFailsAtLoadRatherThanAtFirstUse:
    def test_a_declaration_that_cannot_be_scored_is_refused_when_the_file_loads(self, temp_rubric):
        """Otherwise the first Source naming that outlet fails a request,
        and the file that caused it looks fine."""
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": [
                            "named_editorial_responsibility",
                            "named_editorial_responsibility",
                        ],
                    }
                ]
            )
        )
        with pytest.raises(RubricError, match="more than once"):
            load_rubric()

    def test_a_file_that_is_not_a_mapping_names_itself(self, tmp_path, monkeypatch):
        path = tmp_path / "source_rubric.yaml"
        path.write_text("- just\n- a list\n")
        monkeypatch.setenv("SOURCE_RUBRIC_PATH", str(path))
        load_rubric.cache_clear()
        try:
            with pytest.raises(RubricError, match="source_rubric.yaml"):
                load_rubric()
        finally:
            load_rubric.cache_clear()

    def test_an_unreadable_field_is_a_rubric_error_and_not_a_bare_value_error(
        self, tmp_path, monkeypatch
    ):
        path = tmp_path / "source_rubric.yaml"
        path.write_text("version: 1\nbaseline: fifty\ncriteria: []\noutlets: []\n")
        monkeypatch.setenv("SOURCE_RUBRIC_PATH", str(path))
        load_rubric.cache_clear()
        try:
            with pytest.raises(RubricError, match="cannot be read as a rubric"):
                load_rubric()
        finally:
            load_rubric.cache_clear()


class TestTheScaleLeavesHeadroomForBehaviour:
    """The structural baseline must not reach either end of the range.

    A Source pinned at 100 leaves the cross-verification boost nothing to
    add, and one pinned at 0 makes every later drop invisible. Both defeat
    the part of the credibility system that is actually evidence, and a
    points change that did it would look like an ordinary edit.
    """

    HEADROOM = 10.0

    def test_meeting_every_positive_criterion_stays_below_the_ceiling(self):
        rubric = load_rubric()
        positives = [c.id for c in rubric.criteria if c.points > 0]
        assert rubric.baseline_for(positives) <= 100.0 - self.HEADROOM

    def test_meeting_every_negative_criterion_stays_above_the_floor(self):
        rubric = load_rubric()
        negatives = [c.id for c in rubric.criteria if c.points < 0]
        assert rubric.baseline_for(negatives) >= self.HEADROOM

    def test_no_baseline_is_ever_produced_by_clamping(self):
        """Clamping would silently discard points the file says are there."""
        rubric = load_rubric()
        positives = sum(c.points for c in rubric.criteria if c.points > 0)
        negatives = sum(c.points for c in rubric.criteria if c.points < 0)
        assert rubric.baseline + positives <= 100.0
        assert rubric.baseline + negatives >= 0.0


class TestTwoOutletsWithTheSamePropertiesScoreTheSame:
    def test_structurally_equivalent_outlets_are_equal(self, temp_rubric):
        """User story 4. The names differ, the politics differ, the
        structural properties do not, so the baselines are identical."""
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    },
                    {
                        "handle": "https://second.example.in/feed",
                        "name": "Second Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    },
                ]
            )
        )
        first = baseline_for_handle("https://first.example.in/feed")
        second = baseline_for_handle("https://second.example.in/feed")
        assert first == second == 60.0


class TestOutletDeclarations:
    def test_an_undeclared_outlet_has_no_baseline(self, temp_rubric):
        """None, not the neutral baseline. The caller decides what to do
        about an outlet nobody has assessed, and can say so in a log."""
        temp_rubric(_rubric())
        assert baseline_for_handle("https://unknown.example.in/feed") is None
        assert declaration_for("https://unknown.example.in/feed") is None

    def test_a_declaration_carries_the_properties_that_produced_the_score(self, temp_rubric):
        """User story 2 and 5: the reason has to be readable off the row."""
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    }
                ]
            )
        )
        declaration = declaration_for("https://first.example.in/feed")
        assert declaration is not None
        assert declaration.criteria_met == ["named_editorial_responsibility"]
        assert declaration.name == "First Outlet"

    def test_a_declaration_naming_an_unknown_property_is_refused(self, temp_rubric):
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["invented_property"],
                    }
                ]
            )
        )
        with pytest.raises(RubricError, match="invented_property"):
            load_rubric()

    def test_a_duplicate_handle_is_refused(self, temp_rubric):
        """Two declarations for one outlet means one of them is dead, and
        which one wins is an ordering accident."""
        temp_rubric(
            _rubric(
                outlets=[
                    {"handle": "https://first.example.in/feed", "name": "A", "criteria_met": []},
                    {"handle": "https://first.example.in/feed", "name": "B", "criteria_met": []},
                ]
            )
        )
        with pytest.raises(RubricError, match="first.example.in"):
            load_rubric()

    def test_a_missing_file_disables_the_baseline_rather_than_guessing(self, monkeypatch):
        """The lookup falls back to the checkout, so the absence being
        tested is the one where no copy of the file exists anywhere."""
        import anveshak.source_rubric as module

        monkeypatch.setattr(module, "_resolve_rubric_path", lambda: None)
        load_rubric.cache_clear()
        try:
            rubric = load_rubric()
            assert rubric.version == 0
            assert rubric.criteria == []
            assert baseline_for_handle("https://first.example.in/feed") is None
        finally:
            load_rubric.cache_clear()


class TestTheReasonWrittenToTheAuditLog:
    def test_it_names_the_rubric_version_and_every_property(self, temp_rubric):
        """User story 2: an analyst answering a challenge needs the basis,
        not the word "rubric"."""
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["named_editorial_responsibility", "no_named_authors"],
                    }
                ]
            )
        )
        declaration = declaration_for("https://first.example.in/feed")
        assert declaration is not None
        reason = load_rubric().reason_for(declaration)
        assert "v1" in reason
        assert "named_editorial_responsibility" in reason
        assert "no_named_authors" in reason

    def test_an_outlet_meeting_nothing_still_says_so(self, temp_rubric):
        temp_rubric(
            _rubric(
                outlets=[
                    {"handle": "https://first.example.in/feed", "name": "A", "criteria_met": []}
                ]
            )
        )
        declaration = declaration_for("https://first.example.in/feed")
        assert declaration is not None
        assert load_rubric().reason_for(declaration).strip()


class TestTheScoreASourceIsCreatedAt:
    """One resolution point, so every creation path agrees.

    Three of them exist: the API, the catalog approval route and the corpus
    importer. Each used to hardcode the neutral score independently.
    """

    def test_a_stated_score_wins(self, temp_rubric):
        """An operator who typed a number meant it."""
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    }
                ]
            )
        )
        score, basis, declaration = creation_score("https://first.example.in/feed", stated=71.0)
        assert (score, basis) == (71.0, "stated")
        # The declaration comes back even when it was overridden: overriding
        # an assessment that exists is worth being able to log.
        assert declaration is not None

    def test_a_declared_outlet_starts_at_its_structural_baseline(self, temp_rubric):
        temp_rubric(
            _rubric(
                outlets=[
                    {
                        "handle": "https://first.example.in/feed",
                        "name": "First Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    }
                ]
            )
        )
        score, basis, declaration = creation_score("https://first.example.in/feed")
        assert (score, basis) == (60.0, "rubric")
        assert declaration is not None
        assert declaration.criteria_met == ["named_editorial_responsibility"]

    def test_an_undeclared_outlet_starts_neutral_and_says_so(self, temp_rubric):
        """The basis is returned rather than inferred, so the caller can log
        why a Source was created where it was. A Source quietly created at
        the neutral score looks identical to one assessed as ordinary."""
        temp_rubric(_rubric())
        assert creation_score("https://unknown.example.in/feed") == (50.0, "neutral", None)

    def test_a_stated_score_outside_the_range_is_clamped(self, temp_rubric):
        temp_rubric(_rubric())
        assert creation_score("https://unknown.example.in/feed", stated=140.0)[0] == 100.0

    def test_a_stated_zero_is_a_statement_and_not_an_absence(self):
        """The one input where `if stated:` instead of `is not None` would
        silently reroute a deliberate zero to the rubric."""
        assert creation_score("https://unknown.example.in/feed", stated=0.0) == (
            0.0,
            "stated",
            None,
        )


class TestNoPathChangesAScoreWithoutAnAuditRow:
    """Architectural rule 8, checked across the repository rather than per
    call site. A new writer of credibility_score is exactly the change that
    would forget the audit row, and it would look correct until an analyst
    was asked why a score moved and found nothing.

    The check is per SQL constant rather than per function: it catches a
    module that updates a score and never writes the log at all. It cannot
    see a second unaudited writer added to a module that already writes one,
    which is why the integration test asserts the transaction directly.
    """

    SEARCH_ROOTS = ("services", "scripts", "sdk")

    # `SQL_NAME = """ ... """`, the module-level convention this repo uses.
    SQL_CONSTANT = re.compile(r"^(?P<name>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<quote>\"\"\"|\')", re.M)
    UPDATES_SCORE = re.compile(r"update\s+(public\.)?sources", re.I)

    def _repo_root(self) -> Path:
        root = Path(__file__).resolve().parent
        while not (root / "uv.lock").exists():
            assert root != root.parent, "no uv.lock above this test, cannot locate the repo"
            root = root.parent
        return root

    def _modules(self) -> list[Path]:
        root = self._repo_root()
        modules: list[Path] = []
        for search_root in self.SEARCH_ROOTS:
            for path in (root / search_root).rglob("*.py"):
                if "__pycache__" in path.parts or "migrations" in path.parts:
                    continue
                modules.append(path)
        return modules

    def _writers(self) -> list[Path]:
        writers: list[Path] = []
        for path in self._modules():
            text = path.read_text()
            if self.UPDATES_SCORE.search(text) and "credibility_score" in text:
                writers.append(path)
        return writers

    def test_at_least_the_known_writers_are_found(self):
        """A guard that silently matched nothing would pass forever."""
        root = self._repo_root()
        found = {path.relative_to(root).as_posix() for path in self._writers()}
        assert "services/analyst/anveshak/analyst/credibility.py" in found
        assert "services/api/anveshak/api/db/sources.py" in found
        assert "scripts/apply_source_rubric.py" in found

    def test_every_writer_also_writes_the_audit_log(self):
        root = self._repo_root()
        for path in self._writers():
            text = path.read_text()
            assert "credibility_audit_log" in text, (
                f"{path.relative_to(root)} updates a credibility score and writes no "
                "audit row (architectural rule 8)"
            )

    def test_every_writer_pairs_the_two_statements_in_a_transaction(self):
        """An UPDATE and an INSERT that are not in one transaction leave a
        score moved with no row explaining it when the second one fails."""
        root = self._repo_root()
        for path in self._writers():
            text = path.read_text()
            opens_one = ".transaction()" in text
            # A repository module leaves the transaction to its caller, and
            # says so on the function that writes the pair.
            delegates = re.search(r"caller'?s transaction|open transaction", text) is not None
            assert opens_one or delegates, (
                f"{path.relative_to(root)} writes a score and its audit row outside a "
                "transaction, and does not say that its caller opens one"
            )
