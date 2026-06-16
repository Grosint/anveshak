"""Unit tests for batched source warnings processing — MED-17.

check_source_warnings must process reports in batches to avoid
loading thousands of reports into memory at once.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestSourceWarningsBatching:

    def test_fetch_reports_has_batch_limit(self):
        """fetch_reports_for_warning_check must accept a limit/offset or batch_size param."""
        from anveshak.reporter import db

        import inspect
        sig = inspect.signature(db.fetch_reports_for_warning_check)
        params = set(sig.parameters.keys())

        assert "batch_size" in params or "limit" in params or "offset" in params, (
            "fetch_reports_for_warning_check must support batching via "
            "batch_size, limit, or offset parameter"
        )
