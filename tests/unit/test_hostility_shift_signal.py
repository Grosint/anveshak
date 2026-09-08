"""Rebase the sentiment-shift signal onto hostility — issue #30.

The signal fired on an English lexicon reading machine-translated text, and
raised a live alert from the result. For discourse in Hindi and other Indian
languages that is a false positive waiting to happen, and it would be raised
to an intelligence customer.

The lexicon score survives as a content filter, where a rough value is
acceptable because nothing alerts on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from anveshak.analyst.settings import settings

pytestmark = pytest.mark.unit

SIGNAL_ENGINE = Path("services/analyst/anveshak/analyst/signal_engine.py")


class TestTheSignalReadsHostility:
    def test_the_baseline_query_reads_the_hostility_column(self):
        from anveshak.analyst.signal_engine import SQL_HOSTILITY_BASELINE

        assert "hostility" in SQL_HOSTILITY_BASELINE
        assert "labels->'sentiment'" not in SQL_HOSTILITY_BASELINE

    def test_the_recent_query_reads_the_hostility_column(self):
        from anveshak.analyst.signal_engine import SQL_HOSTILITY_RECENT

        assert "hostility" in SQL_HOSTILITY_RECENT
        assert "labels->'sentiment'" not in SQL_HOSTILITY_RECENT

    def test_null_hostility_is_excluded_rather_than_read_as_zero(self):
        """None means not measured. Averaging it as 0.0 would invent calm."""
        from anveshak.analyst.signal_engine import SQL_HOSTILITY_BASELINE, SQL_HOSTILITY_RECENT

        for sql in (SQL_HOSTILITY_BASELINE, SQL_HOSTILITY_RECENT):
            assert "hostility IS NOT NULL" in sql

    def test_the_signal_type_names_the_measure(self):
        from anveshak.analyst.signal_engine import _SIGNAL_TYPE_HOSTILITY_SHIFT

        assert _SIGNAL_TYPE_HOSTILITY_SHIFT == "hostility_shift"


class TestNothingAlertsOnTheLexiconScore:
    def test_no_signal_query_reads_the_lexicon_sentiment(self):
        source = SIGNAL_ENGINE.read_text()
        assert "labels->'sentiment'" not in source

    def test_no_module_fires_a_signal_from_the_lexicon_score(self):
        analyst = Path("services/analyst/anveshak/analyst")
        for path in analyst.glob("*.py"):
            source = path.read_text()
            if "SQL_INSERT_SIGNAL" not in source:
                continue
            assert "labels->'sentiment'" not in source, path.name

    def test_the_lexicon_score_is_still_computed(self):
        """It stays as a content filter, where a rough value is acceptable."""
        from anveshak.analyst.sentiment import analyse_sentiment

        assert analyse_sentiment("this is a terrible outcome").compound < 0

    def test_the_lexicon_score_is_still_written_to_labels(self):
        source = Path("services/analyst/anveshak/analyst/jobs.py").read_text()
        assert "sentiment" in source


class TestThreshold:
    def test_the_threshold_is_a_setting(self):
        assert settings.hostility_shift_threshold > 0

    def test_it_is_read_from_settings_not_hardcoded(self):
        source = SIGNAL_ENGINE.read_text()
        assert "settings.hostility_shift_threshold" in source

    def test_the_window_settings_survive_the_rebase(self):
        assert settings.hostility_shift_window_hours > 0
        assert settings.hostility_shift_baseline_days > 0


class TestDedupBehaviourIsPreserved:
    def test_it_still_dedups_per_topic_within_the_existing_window(self):
        from anveshak.analyst.signal_engine import SQL_DUPLICATE_TOPIC_SIGNAL_CHECK

        assert "24 hours" in SQL_DUPLICATE_TOPIC_SIGNAL_CHECK
        assert "topic_id" in SQL_DUPLICATE_TOPIC_SIGNAL_CHECK

    def test_the_check_loop_still_runs_in_the_engine(self):
        source = SIGNAL_ENGINE.read_text()
        assert "check_hostility_shifts" in source


class TestDirectionIsExplicit:
    def test_a_rise_in_hostility_is_what_fires(self):
        """Hostility rising is escalation. Sentiment dropping was the old proxy."""
        from anveshak.analyst.signal_engine import hostility_shift_delta

        assert hostility_shift_delta(baseline=0.2, recent=0.5) == pytest.approx(0.3)

    def test_a_fall_in_hostility_is_a_negative_delta(self):
        from anveshak.analyst.signal_engine import hostility_shift_delta

        assert hostility_shift_delta(baseline=0.5, recent=0.2) == pytest.approx(-0.3)

    def test_a_fall_never_crosses_the_threshold(self):
        from anveshak.analyst.signal_engine import hostility_shift_delta

        assert hostility_shift_delta(baseline=0.9, recent=0.1) < settings.hostility_shift_threshold
