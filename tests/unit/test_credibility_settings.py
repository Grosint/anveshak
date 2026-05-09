"""Invariant tests for analyst settings that must not defeat each other.

pytest.mark.unit -- no external dependencies.

These tests catch the configuration bug where a threshold/drop setting is
set so that the feature silently never fires. E.g., if credibility_min_auto_drop
exceeds credibility_contradiction_drop, every contradiction drop is silently
skipped by the noise filter.

See: learned/threshold-and-setting-invariants.md
"""
from __future__ import annotations

import pytest

from anveshak.analyst.settings import AnalystSettings


@pytest.mark.unit
class TestCredibilitySettingInvariants:
    """Verify default settings don't silently disable credibility features."""

    def test_contradiction_drop_gte_min_auto_drop(self):
        """credibility_contradiction_drop must be >= credibility_min_auto_drop.

        If drop < min_auto_drop, the `abs(new - old) < min_auto_drop` check
        skips EVERY contradiction penalty, silently disabling the feature.
        """
        s = AnalystSettings()
        assert s.credibility_contradiction_drop >= s.credibility_min_auto_drop, (
            f"contradiction_drop ({s.credibility_contradiction_drop}) < "
            f"min_auto_drop ({s.credibility_min_auto_drop}) -- "
            f"every contradiction drop will be silently skipped"
        )

    def test_deepfake_drop_gte_min_auto_drop(self):
        """credibility_deepfake_drop must be >= credibility_min_auto_drop.

        Otherwise a single-deepfake source penalty (deepfake_drop * 1) gets
        filtered out by the noise guard.
        """
        s = AnalystSettings()
        assert s.credibility_deepfake_drop >= s.credibility_min_auto_drop, (
            f"deepfake_drop ({s.credibility_deepfake_drop}) < "
            f"min_auto_drop ({s.credibility_min_auto_drop}) -- "
            f"single-item deepfake drops will be silently skipped"
        )

    def test_cross_verify_boost_gte_min_auto_boost(self):
        """credibility_cross_verify_boost must be >= credibility_min_auto_boost.

        Otherwise the boost noise filter silently blocks all cross-verification.
        """
        s = AnalystSettings()
        assert s.credibility_cross_verify_boost >= s.credibility_min_auto_boost, (
            f"cross_verify_boost ({s.credibility_cross_verify_boost}) < "
            f"min_auto_boost ({s.credibility_min_auto_boost}) -- "
            f"every cross-verify boost will be silently skipped"
        )

    def test_noise_ratio_threshold_between_0_and_1(self):
        """credibility_noise_ratio_threshold must be in (0, 1.0].

        0.0 would trigger on every source. >1.0 would never trigger.
        """
        s = AnalystSettings()
        assert 0.0 < s.credibility_noise_ratio_threshold <= 1.0, (
            f"noise_ratio_threshold ({s.credibility_noise_ratio_threshold}) "
            f"must be in (0.0, 1.0]"
        )

    def test_sentiment_shift_threshold_positive(self):
        """sentiment_shift_threshold must be > 0.

        Zero or negative would fire on every topic regardless of sentiment.
        """
        s = AnalystSettings()
        assert s.sentiment_shift_threshold > 0, (
            f"sentiment_shift_threshold ({s.sentiment_shift_threshold}) "
            f"must be positive to prevent constant signal firing"
        )
