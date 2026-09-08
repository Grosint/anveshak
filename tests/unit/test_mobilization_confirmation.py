"""Mobilization model confirmation and its acceptance bars — issue #34.

The confirmation step runs only on the small candidate set the lexicon
produced, is dispatched as a background job, and validates its output
through a schema before anything is stored or shown.

Two acceptance bars, because the failure costs differ. Detection precision
is weighted over recall, since a false mobilization alert about a political
group is the worst output this system can produce, and the lexicon already
catches the obvious cases. If either bar is missed the step ships disabled
and the lexicon runs alone, which still produces a defensible signal. That
is a planned outcome, not a failure.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from anveshak.analyst.mobilization_confirm import (
    ACCEPTANCE_DATE_PLACE_ACCURACY,
    ACCEPTANCE_PRECISION,
    MobilizationConfirmation,
    describe_confirmation_state,
    meets_acceptance_bars,
    parse_confirmation,
)
from anveshak.analyst.settings import settings

pytestmark = pytest.mark.unit


class TestItShipsDisabled:
    def test_the_flag_defaults_to_off(self):
        """Neither bar has been measured on a real labelled set yet."""
        assert settings.mobilization_confirm_enabled is False

    def test_the_disabled_state_reports_a_reason(self):
        state = describe_confirmation_state(enabled=False)
        assert state["enabled"] is False
        assert state["reason"]

    def test_the_enabled_state_reports_the_bars_it_rests_on(self):
        state = describe_confirmation_state(enabled=True)
        assert state["precision_bar"] == ACCEPTANCE_PRECISION
        assert state["date_place_bar"] == ACCEPTANCE_DATE_PLACE_ACCURACY


class TestAcceptanceBars:
    def test_precision_is_weighted_over_recall(self):
        assert ACCEPTANCE_PRECISION == 0.85
        assert ACCEPTANCE_DATE_PLACE_ACCURACY == 0.70

    def test_both_bars_must_be_met(self):
        assert meets_acceptance_bars(precision=0.90, date_place_accuracy=0.75) is True

    def test_missing_the_precision_bar_fails(self):
        assert meets_acceptance_bars(precision=0.80, date_place_accuracy=0.95) is False

    def test_missing_the_extraction_bar_fails(self):
        assert meets_acceptance_bars(precision=0.99, date_place_accuracy=0.65) is False

    def test_recall_is_not_a_bar(self):
        """The lexicon already catches the obvious cases, so lower recall is
        tolerable and lower precision is not."""
        source = Path("services/analyst/anveshak/analyst/mobilization_confirm.py").read_text()
        assert "ACCEPTANCE_RECALL" not in source


class TestOutputIsValidatedBeforeUse:
    def test_a_well_formed_response_parses(self):
        result = parse_confirmation(
            '{"is_call_to_assemble": true, "date": "2026-03-12", '
            '"place": "the collectorate", "confidence": 0.8, '
            '"labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"}}'
        )
        assert isinstance(result, MobilizationConfirmation)
        assert result.is_call_to_assemble is True
        assert result.date == date(2026, 3, 12)

    def test_a_fenced_response_parses(self):
        result = parse_confirmation(
            '```json\n{"is_call_to_assemble": false, "date": null, "place": null, '
            '"confidence": 0.4, "labels": {"classification": "OPEN", '
            '"domain": "osint", "owner_org": "anveshak"}}\n```'
        )
        assert result.is_call_to_assemble is False

    def test_prose_is_rejected(self):
        """Rule 9: never trust a raw LLM string."""
        assert parse_confirmation("I think this is probably a protest announcement.") is None

    def test_a_missing_field_is_rejected(self):
        assert parse_confirmation('{"date": null}') is None

    def test_an_out_of_range_confidence_is_rejected(self):
        assert (
            parse_confirmation(
                '{"is_call_to_assemble": true, "date": null, "place": null, '
                '"confidence": 1.7, "labels": {"classification": "OPEN", '
                '"domain": "osint", "owner_org": "anveshak"}}'
            )
            is None
        )

    def test_the_model_carries_labels(self):
        assert "labels" in MobilizationConfirmation.model_fields


class TestItRunsOnlyOnCandidates:
    def test_the_job_takes_content_ids_the_lexicon_flagged(self):
        import inspect

        from anveshak.analyst.mobilization_confirm import confirm_candidates

        signature = inspect.signature(confirm_candidates)
        assert "content_item_ids" in signature.parameters

    def test_it_is_never_called_from_a_route(self):
        for path in Path("services/api/anveshak/api/routes").rglob("*.py"):
            assert "confirm_candidates" not in path.read_text(), path

    def test_it_is_registered_as_a_background_job(self):
        from anveshak.analyst.jobs import WorkerSettings

        names = {
            getattr(f, "name", None) or getattr(f, "coroutine", f).__name__
            for f in WorkerSettings.functions
        }
        assert "confirm_mobilization_job" in names


class TestBenchmarkHarness:
    def test_the_labelled_set_exists(self):
        assert Path("benchmark/corpus/mobilization/labelled.yaml").exists()

    def test_the_shipped_set_declares_it_is_not_the_real_one(self):
        import yaml

        data = yaml.safe_load(Path("benchmark/corpus/mobilization/labelled.yaml").read_text())
        assert data["provenance"] == "synthetic"

    def test_the_readme_states_the_real_set_requirement(self):
        readme = Path("benchmark/corpus/mobilization/README.md").read_text()
        assert "100 to 200" in readme
        assert "public reporting" in readme

    def test_scoring_computes_precision_and_extraction_accuracy(self):
        from benchmark.mobilization import score_predictions

        result = score_predictions(
            [
                {"is_call_to_assemble": True, "date": "2026-03-12", "place": "the collectorate"},
                {"is_call_to_assemble": True, "date": None, "place": None},
                {"is_call_to_assemble": False, "date": None, "place": None},
            ],
            [
                {
                    "is_call_to_assemble": True,
                    "expected_date": "2026-03-12",
                    "expected_place": "the collectorate",
                },
                {"is_call_to_assemble": False, "expected_date": None, "expected_place": None},
                {"is_call_to_assemble": False, "expected_date": None, "expected_place": None},
            ],
        )
        # One true positive, one false positive.
        assert result["precision"] == pytest.approx(0.5)
        # Extraction is scored only where the truth is a call.
        assert result["date_place_accuracy"] == pytest.approx(1.0)

    def test_perfect_predictions_score_one(self):
        from benchmark.mobilization import score_predictions

        result = score_predictions(
            [{"is_call_to_assemble": True, "date": "2026-03-12", "place": "square"}],
            [
                {
                    "is_call_to_assemble": True,
                    "expected_date": "2026-03-12",
                    "expected_place": "square",
                }
            ],
        )
        assert result["precision"] == pytest.approx(1.0)
        assert result["date_place_accuracy"] == pytest.approx(1.0)

    def test_no_prediction_of_a_call_yields_zero_precision_not_a_crash(self):
        from benchmark.mobilization import score_predictions

        result = score_predictions(
            [{"is_call_to_assemble": False, "date": None, "place": None}],
            [{"is_call_to_assemble": True, "expected_date": None, "expected_place": None}],
        )
        assert result["precision"] == 0.0
