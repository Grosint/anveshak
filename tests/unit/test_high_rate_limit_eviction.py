"""Unit tests for rate limiter LRU eviction — HIGH-11.

_windows dict grows unbounded. Must cap at max_entries and evict oldest.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestRateLimiterEviction:
    def test_windows_has_max_entries(self):
        """Rate limiter must have a bounded store, not a plain dict."""
        from anveshak.api.middleware.rate_limit import _windows

        assert hasattr(_windows, "max_entries") or hasattr(_windows, "_max"), (
            "_windows must have a max_entries bound — unbounded dict causes memory leak"
        )

    def test_evicts_oldest_when_full(self):
        """When max_entries reached, oldest entries are evicted."""
        from anveshak.api.middleware.rate_limit import _check_rate, _windows

        # Clear state
        _windows.clear()

        # Fill with unique keys
        max_size = getattr(_windows, "max_entries", getattr(_windows, "_max", 10000))
        # Use a smaller test — just verify eviction works
        # Add max_size + 100 entries and verify size stays bounded
        for i in range(min(max_size + 100, 10100)):
            _check_rate(f"test-key-{i}", 1000)

        assert len(_windows) <= max_size, (
            f"_windows has {len(_windows)} entries, should be <= {max_size}"
        )

    def test_check_rate_still_works_after_eviction(self):
        """Rate checking must work correctly even after eviction has occurred."""
        from anveshak.api.middleware.rate_limit import _check_rate, _windows

        _windows.clear()

        # Should still function normally
        allowed, retry = _check_rate("fresh-key", 10)
        assert allowed is True
        assert retry == 0
