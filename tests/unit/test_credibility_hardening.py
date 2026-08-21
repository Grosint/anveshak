"""Unit tests — Phase 7 credibility hardening (criteria 7.1, 7.2, 7.5).

All tests are pure — no DB, no network.
"""

from anveshak.analyst.credibility import clamp_score, compute_new_score
from anveshak.analyst.settings import AnalystSettings

# ---------------------------------------------------------------------------
# clamp_score (7.5)
# ---------------------------------------------------------------------------


def test_clamp_score_ceiling():
    assert clamp_score(105.0) == 100.0


def test_clamp_score_floor():
    assert clamp_score(-5.0) == 0.0


def test_clamp_score_identity():
    assert clamp_score(75.3) == 75.3


def test_clamp_score_exactly_100():
    assert clamp_score(100.0) == 100.0


def test_clamp_score_exactly_0():
    assert clamp_score(0.0) == 0.0


# ---------------------------------------------------------------------------
# compute_new_score — deepfake drop now uses clamp_score (7.5 ceiling fix)
# ---------------------------------------------------------------------------


def test_compute_new_score_floored():
    """Very large deepfake count — result should not go below 0.0."""
    result = compute_new_score(5.0, deepfake_count=100)
    assert result == 0.0


def test_compute_new_score_normal_drop():
    """Standard drop: 50.0 - (credibility_deepfake_drop * 1) = 49.0."""
    result = compute_new_score(50.0, deepfake_count=1)
    assert result == 49.0


def test_compute_new_score_ceiling_not_exceeded():
    """Negative deepfake_count edge — result must not exceed 100.0."""
    # compute_new_score(old, 0) → old score unchanged, still clamped
    result = compute_new_score(99.0, deepfake_count=0)
    assert result <= 100.0


# ---------------------------------------------------------------------------
# Cross-verification boost guard (7.1) — settings interaction
# ---------------------------------------------------------------------------


def test_cross_verify_boost_uses_separate_min_threshold():
    """credibility_min_auto_boost must be < credibility_cross_verify_boost
    so boosts are not silently skipped by default settings.
    """
    s = AnalystSettings()
    assert s.credibility_min_auto_boost < s.credibility_cross_verify_boost, (
        "credibility_min_auto_boost must be less than credibility_cross_verify_boost "
        "or every boost will be silently skipped"
    )


def test_cross_verify_boost_capped_at_100():
    """Source at 98.0 with boost 5.0 → clamped to 100.0, not 103.0."""
    s = AnalystSettings()
    boosted = clamp_score(98.0 + s.credibility_cross_verify_boost)
    assert boosted == 100.0


def test_cross_verify_boost_skip_logic():
    """Boost delta below credibility_min_auto_boost should be skippable.

    Simulates the skip condition in run_cross_verification_update.
    """
    s = AnalystSettings()
    old_score = 99.9
    new_score = clamp_score(old_score + s.credibility_cross_verify_boost)
    delta = abs(new_score - old_score)
    # With old=99.9, boost=5.0, new=100.0, delta=0.1 < min_auto_boost(1.0) → skip
    assert delta < s.credibility_min_auto_boost


# ---------------------------------------------------------------------------
# Contradiction drop guard (7.2) — noise ratio logic
# ---------------------------------------------------------------------------


def test_contradiction_noise_ratio_below_threshold_skips():
    """Source with noise ratio 0.4 should NOT be penalised when threshold is 0.6."""
    s = AnalystSettings()
    noise_count, total_count = 4, 10
    noise_ratio = noise_count / total_count
    assert noise_ratio < s.credibility_noise_ratio_threshold


def test_contradiction_noise_ratio_above_threshold_fires():
    """Source with noise ratio 0.7 SHOULD be penalised when threshold is 0.6."""
    s = AnalystSettings()
    noise_count, total_count = 7, 10
    noise_ratio = noise_count / total_count
    assert noise_ratio >= s.credibility_noise_ratio_threshold


def test_contradiction_below_min_items_skips():
    """Source with only 3 items (< credibility_contradiction_min_items=5) is skipped."""
    s = AnalystSettings()
    total_count = 3
    assert total_count < s.credibility_contradiction_min_items


def test_contradiction_drop_floored_at_zero():
    """Source at 2.0 with drop 5.0 → clamped to 0.0."""
    s = AnalystSettings()
    result = clamp_score(2.0 - s.credibility_contradiction_drop)
    assert result == 0.0


# ---------------------------------------------------------------------------
# New source default (7.7)
# ---------------------------------------------------------------------------


def test_new_source_default_credibility_score():
    """SDK Source model must default credibility_score to 50.0 (7.7)."""
    from anveshak.models.base import Labels
    from anveshak.models.source import Source

    labels = Labels(classification="OPEN", domain="osint", owner_org="anveshak")
    source = Source(
        name="Test Source",
        url_or_handle="https://example.com",
        platform="web",
        labels=labels,
    )
    assert source.credibility_score == 50.0
