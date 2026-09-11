"""Applying the structural baseline to Sources that already exist - issue #51.

Every score change is a row in credibility_audit_log (architectural rule 8),
so this script writes through the same audited pair of statements the analyst
service uses and never updates a score on its own.

The decision of whether to change a score at all is a pure function, because
the interesting cases are the ones where the answer is no: a Source whose
score behaviour has already moved must not be reset to its baseline by a
re-run, and a Source already sitting at its baseline must not write an audit
row saying nothing changed.
"""

from __future__ import annotations

import pytest

from scripts.apply_source_rubric import (
    CHANGED_BY_PREFIX,
    changed_by,
    decide,
)

pytestmark = pytest.mark.unit


class TestDecidingWhetherToChangeAScore:
    def test_a_source_at_the_neutral_default_takes_its_baseline(self):
        decision = decide(old_score=50.0, new_score=72.0, already_baselined=False)
        assert decision.apply is True
        assert decision.reason_skipped == ""

    def test_a_source_already_at_its_baseline_is_left_alone(self):
        """An audit row recording a change of zero is noise in the one place
        an analyst goes to answer a challenge."""
        decision = decide(old_score=72.0, new_score=72.0, already_baselined=False)
        assert decision.apply is False
        assert "already" in decision.reason_skipped

    def test_a_hair_of_floating_point_is_not_a_change(self):
        decision = decide(old_score=72.0, new_score=72.004, already_baselined=False)
        assert decision.apply is False

    def test_a_source_the_baseline_already_reached_is_not_reset(self):
        """The score has moved since, and it moved because this platform
        observed the outlet behave. Resetting it to the structural number
        would throw that away silently on the next run."""
        decision = decide(old_score=61.0, new_score=72.0, already_baselined=True)
        assert decision.apply is False
        assert "rebaseline" in decision.reason_skipped

    def test_rebaselining_is_possible_but_deliberate(self):
        decision = decide(old_score=61.0, new_score=72.0, already_baselined=True, rebaseline=True)
        assert decision.apply is True


class TestTheAuditRowIsAttributable:
    def test_the_author_names_the_rubric_version(self):
        """`changed_by` is what tells an analyst that a row came from the
        rubric rather than from observed behaviour."""
        assert changed_by(3) == f"{CHANGED_BY_PREFIX}3"

    def test_a_rubric_row_is_recognisable_by_prefix(self):
        """The re-run guard reads this prefix to find Sources that have
        already been baselined, so the shape is load-bearing."""
        assert changed_by(1).startswith(CHANGED_BY_PREFIX)
        assert CHANGED_BY_PREFIX != "analyst.auto_credibility"
