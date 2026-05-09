"""Unit tests for social service Prometheus metrics completeness.

Verifies all required metrics are registered in the social REGISTRY.
pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSocialMetricsRegistered:
    """All required social metrics must be registered."""

    def test_items_collected_total_exists(self):
        from anveshak.social.metrics import social_items_collected_total
        assert social_items_collected_total is not None

    def test_adapter_errors_total_exists(self):
        from anveshak.social.metrics import social_adapter_errors_total
        assert social_adapter_errors_total is not None

    def test_arq_jobs_failed_total_exists(self):
        from anveshak.social.metrics import arq_jobs_failed_total
        assert arq_jobs_failed_total is not None

    def test_api_calls_total_exists(self):
        """social_api_calls_total must track per-platform API call count."""
        from anveshak.social.metrics import social_api_calls_total
        assert social_api_calls_total is not None

    def test_rate_limit_total_exists(self):
        """social_rate_limit_total must track rate limit events."""
        from anveshak.social.metrics import social_rate_limit_total
        assert social_rate_limit_total is not None

    def test_poll_duration_seconds_exists(self):
        """social_poll_duration_seconds must track adapter poll duration."""
        from anveshak.social.metrics import social_poll_duration_seconds
        assert social_poll_duration_seconds is not None

    def test_quota_remaining_gauge_exists(self):
        """social_quota_remaining must show remaining quota per adapter."""
        from anveshak.social.metrics import social_quota_remaining
        assert social_quota_remaining is not None


class TestSocialMetricsLabels:
    """Metrics must have correct label sets."""

    def test_api_calls_has_platform_label(self):
        from anveshak.social.metrics import social_api_calls_total
        # Verify it accepts the platform label
        social_api_calls_total.labels(platform="bluesky")

    def test_rate_limit_has_platform_label(self):
        from anveshak.social.metrics import social_rate_limit_total
        social_rate_limit_total.labels(platform="x")

    def test_poll_duration_has_platform_label(self):
        from anveshak.social.metrics import social_poll_duration_seconds
        social_poll_duration_seconds.labels(platform="telegram")

    def test_quota_remaining_has_adapter_label(self):
        from anveshak.social.metrics import social_quota_remaining
        social_quota_remaining.labels(adapter="bluesky-v1")
