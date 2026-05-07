"""Regression tests for known historical bugs.

Each test reproduces a specific bug that was fixed. If the bug regresses,
the corresponding test will fail immediately.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.regression


def test_content_hash_normalisation_consistency():
    """Bug: scraper and social used different normalisation for content_hash.

    Fix: both use lowercase + strip before SHA-256.
    Regression: if normalisation diverges, dedup breaks across services.
    """
    from anveshak.scraper.normalise import compute_content_hash

    text = "  Breaking News: IAF Deploys Rafale  "
    # Must be case-insensitive and whitespace-normalized
    hash1 = compute_content_hash(text)
    hash2 = compute_content_hash(text.upper())
    hash3 = compute_content_hash("  " + text + "  ")
    assert hash1 == hash2 == hash3, "content_hash must be case/whitespace insensitive"
    assert len(hash1) == 64, "content_hash must be SHA-256 (64 hex chars)"


def test_deepfake_score_is_float_not_bool():
    """Bug: early vision code returned is_deepfake: bool instead of float score.

    Fix: architectural rule 7 — always return float 0.0–1.0.
    Regression: any code path that returns bool for deepfake detection.
    """
    # Verify the detector base class enforces float output
    try:
        from anveshak.vision.detectors.base import DeepfakeDetector
        import inspect
        sig = inspect.signature(DeepfakeDetector.score)
        ret = sig.return_annotation
        if ret != inspect.Parameter.empty:
            assert ret in (float, "float"), (
                f"DeepfakeDetector.score must return float, got {ret}"
            )
    except ImportError:
        pytest.skip("Vision module not importable in this environment")


def test_paywall_detection_does_not_reject_short_articles():
    """Bug: paywall detector rejected legitimate short articles.

    Fix: paywall indicators must exceed threshold count, not just exist.
    """
    from anveshak.scraper.clean import is_paywall_page

    # Legitimate short article
    short_article = (
        "The Indian Air Force conducted exercises in the eastern sector. "
        "The deployment included Rafale and Su-30MKI aircraft. "
        "Southern Air Command confirmed the schedule."
    )
    assert is_paywall_page(short_article) is False, (
        "Short legitimate article should NOT be flagged as paywall"
    )

    # Real paywall content
    paywall = (
        "Subscribe to continue reading. "
        "Already a subscriber? Log in. "
        "Create a free account to read this article. "
        "This content is for subscribers only. "
        "Sign up now to access premium content. "
        "Unlock this story with a subscription."
    )
    assert is_paywall_page(paywall) is True, (
        "Obvious paywall content should be detected"
    )
