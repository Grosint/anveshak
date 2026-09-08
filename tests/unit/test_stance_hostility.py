"""Stance and hostility scoring — issue #28.

Two measures, two models, because they are independent. Stance is direction
toward the cluster; hostility is intensity. A furious post supporting a
narrative and a calm post opposing it are opposite in stance and easily
confused by any single sentiment score.

Stance needs a target and the target is the cluster label, unknown at ingest
time, so scoring runs chained from clustering rather than in the ingest
enrichment sequence.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anveshak.analyst.settings import settings
from anveshak.analyst.stance import (
    STANCE_NEUTRAL,
    STANCE_OPPOSING,
    STANCE_SUPPORTING,
    STANCE_UNSUPPORTED_LANGUAGE,
    is_language_supported,
    score_hostility,
    score_stance,
)

pytestmark = pytest.mark.unit


class TestSettingsAreHardwareIndependent:
    """Rule 6: no model name, device string or batch size in service code."""

    def test_models_are_settings(self):
        assert settings.stance_model
        assert settings.hostility_model

    def test_devices_default_to_cpu(self):
        assert settings.stance_device == "cpu"
        assert settings.hostility_device == "cpu"

    def test_batch_sizes_are_settings(self):
        assert settings.stance_batch_size >= 1
        assert settings.hostility_batch_size >= 1

    def test_no_device_string_is_hardcoded_in_the_module(self):
        from pathlib import Path

        source = Path("services/analyst/anveshak/analyst/stance.py").read_text()
        assert '"cuda"' not in source
        assert "'cuda'" not in source

    def test_no_model_name_is_hardcoded_in_the_module(self):
        from pathlib import Path

        source = Path("services/analyst/anveshak/analyst/stance.py").read_text()
        assert "xlm-roberta" not in source.replace("settings.", "")


class TestLanguageSupport:
    def test_english_and_hindi_are_supported(self):
        assert is_language_supported("en")
        assert is_language_supported("hi")

    def test_an_unlisted_language_is_not_supported(self):
        assert not is_language_supported("bo")

    def test_an_unknown_language_code_is_not_supported(self):
        assert not is_language_supported("")
        assert not is_language_supported(None)

    def test_the_supported_set_is_a_setting(self):
        assert isinstance(settings.stance_supported_languages, list)
        assert "en" in settings.stance_supported_languages


class TestStanceScoring:
    def test_unsupported_language_is_marked_not_scored(self):
        """Marked rather than silently scored, so an analyst knows to distrust it."""
        result = score_stance("कुछ पाठ", "cluster label", language="bo")
        assert result == STANCE_UNSUPPORTED_LANGUAGE

    def test_supporting_content_scores_supporting(self):
        """The pipeline returns the hypothesis sentences, not short labels."""
        classifier = MagicMock(return_value=_ranked(STANCE_SUPPORTING, 0.8))
        with patch("anveshak.analyst.stance._get_stance_classifier", return_value=classifier):
            assert score_stance("text", "label", language="en") == STANCE_SUPPORTING

    def test_opposing_content_scores_opposing(self):
        classifier = MagicMock(return_value=_ranked(STANCE_OPPOSING, 0.7))
        with patch("anveshak.analyst.stance._get_stance_classifier", return_value=classifier):
            assert score_stance("text", "label", language="en") == STANCE_OPPOSING

    def test_a_low_confidence_result_is_neutral(self):
        """Below the confidence floor the model is guessing, so say nothing."""
        classifier = MagicMock(return_value=_ranked(STANCE_SUPPORTING, 0.34))
        with patch("anveshak.analyst.stance._get_stance_classifier", return_value=classifier):
            assert score_stance("text", "label", language="en") == STANCE_NEUTRAL

    def test_a_model_failure_returns_none(self):
        """None on error, never a default value that looks like a real score."""
        classifier = MagicMock(side_effect=RuntimeError("model exploded"))
        with patch("anveshak.analyst.stance._get_stance_classifier", return_value=classifier):
            assert score_stance("text", "label", language="en") is None

    def test_empty_text_returns_none(self):
        assert score_stance("", "label", language="en") is None

    def test_empty_cluster_label_returns_none(self):
        """Stance without a target is meaningless."""
        assert score_stance("text", "", language="en") is None


class TestHostilityScoring:
    def test_returns_a_probability(self):
        classifier = MagicMock(return_value=[{"label": "toxic", "score": 0.73}])
        with patch("anveshak.analyst.stance._get_hostility_classifier", return_value=classifier):
            score = score_hostility("text", language="en")
        assert score == pytest.approx(0.73)

    def test_a_non_toxic_label_inverts_the_score(self):
        classifier = MagicMock(return_value=[{"label": "neutral", "score": 0.9}])
        with patch("anveshak.analyst.stance._get_hostility_classifier", return_value=classifier):
            score = score_hostility("text", language="en")
        assert score == pytest.approx(0.1)

    def test_a_model_failure_returns_none_not_zero(self):
        """0.0 means 'measured as not hostile'. None means 'not measured'."""
        classifier = MagicMock(side_effect=RuntimeError("boom"))
        with patch("anveshak.analyst.stance._get_hostility_classifier", return_value=classifier):
            assert score_hostility("text", language="en") is None

    def test_unsupported_language_returns_none(self):
        assert score_hostility("text", language="bo") is None

    def test_the_score_stays_within_zero_and_one(self):
        classifier = MagicMock(return_value=[{"label": "toxic", "score": 1.4}])
        with patch("anveshak.analyst.stance._get_hostility_classifier", return_value=classifier):
            score = score_hostility("text", language="en")
        assert 0.0 <= score <= 1.0


class TestScoringRunsAfterClustering:
    async def test_it_skips_clusters_below_the_size_threshold(self):
        """A timeline is only drawn where there is something to draw."""
        from anveshak.analyst.stance import score_cluster

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"label": "some narrative", "item_count": 1})
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        scored = await score_cluster(pool, "cluster-1")
        assert scored == 0

    async def test_it_scores_items_in_a_large_enough_cluster(self):
        from anveshak.analyst.stance import score_cluster

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={
                "label": "some narrative",
                "item_count": settings.stance_min_cluster_size + 5,
            }
        )
        conn.fetch = AsyncMock(
            return_value=[
                {"id": "ci-1", "work_text": "a post about it", "language": "en"},
                {"id": "ci-2", "work_text": "another post", "language": "en"},
            ]
        )
        conn.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        with (
            patch("anveshak.analyst.stance.score_stance", return_value=STANCE_SUPPORTING),
            patch("anveshak.analyst.stance.score_hostility", return_value=0.2),
        ):
            scored = await score_cluster(pool, "cluster-1")

        assert scored == 2
        # Written in one batch, outside the inference loop, so no pool
        # connection is held across CPU-bound model calls.
        conn.executemany.assert_awaited_once()
        assert len(conn.executemany.await_args.args[1]) == 2

    async def test_a_scoring_failure_does_not_crash_the_pipeline(self):
        """Fail open: clustering to signals still produces valid output."""
        from anveshak.analyst.stance import score_cluster

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={
                "label": "some narrative",
                "item_count": settings.stance_min_cluster_size + 5,
            }
        )
        conn.fetch = AsyncMock(return_value=[{"id": "ci-1", "work_text": "post", "language": "en"}])
        conn.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        with (
            patch("anveshak.analyst.stance.score_stance", side_effect=RuntimeError("boom")),
            patch("anveshak.analyst.stance.score_hostility", return_value=0.2),
        ):
            scored = await score_cluster(pool, "cluster-1")

        assert scored == 0

    async def test_a_missing_cluster_returns_zero(self):
        from anveshak.analyst.stance import score_cluster

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        assert await score_cluster(pool, "missing") == 0


class TestJobIsWiredIntoClustering:
    def test_the_worker_registers_the_job(self):
        from anveshak.analyst.jobs import WorkerSettings

        names = {
            getattr(f, "name", None) or getattr(f, "coroutine", f).__name__
            for f in WorkerSettings.functions
        }
        assert "score_cluster_stance" in names

    def test_clustering_enqueues_it(self):
        from pathlib import Path

        source = Path("services/analyst/anveshak/analyst/jobs.py").read_text()
        assert "score_cluster_stance" in source


class TestThresholdInvariants:
    def test_stance_min_cluster_size_does_not_starve_promotion(self):
        """A promoted Topic with no stance data renders an empty timeline."""
        assert settings.stance_min_cluster_size <= settings.promotion_min_item_count


def _ranked(winner: str, top_score: float, target: str = "label") -> dict:
    """Build a zero-shot result in the shape transformers actually returns.

    The pipeline echoes back the candidate_labels it was given, which here
    are full hypothesis sentences rather than the short stance names.
    """
    from anveshak.analyst.stance import _STANCE_HYPOTHESES

    remainder = (1.0 - top_score) / 2
    others = [s for s in _STANCE_HYPOTHESES if s != winner]
    return {
        "labels": [_STANCE_HYPOTHESES[winner].format(target=target)]
        + [_STANCE_HYPOTHESES[s].format(target=target) for s in others],
        "scores": [top_score, remainder, remainder],
    }


def _ctx(conn):
    """Async context manager wrapper for a mocked pool.acquire()."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx
