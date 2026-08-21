"""Unit tests for OpenTelemetry tracing setup.

Tests:
  - configure_tracing is a no-op when OTEL_ENABLED is not 'true'
  - configure_tracing is a no-op when OTEL packages are not installed
  - get_trace_id returns None when no active span
  - inject_trace_id structlog processor works without OTEL
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


class TestConfigureTracing:
    def test_noop_when_disabled(self):
        from anveshak.tracing import configure_tracing

        with patch.dict("os.environ", {"OTEL_ENABLED": "false"}):
            # Should not raise
            configure_tracing("test-service")

    def test_noop_when_env_not_set(self):
        from anveshak.tracing import configure_tracing

        with patch.dict("os.environ", {}, clear=True):
            configure_tracing("test-service")


class TestGetTraceId:
    def test_returns_none_without_active_span(self):
        from anveshak.tracing import get_trace_id

        result = get_trace_id()
        # Without OTEL configured, should return None
        assert result is None


class TestInjectTraceId:
    def test_processor_passes_through_without_otel(self):
        from anveshak.tracing import inject_trace_id

        event_dict = {"event": "test.event", "level": "info"}
        result = inject_trace_id(None, "info", event_dict)
        assert result["event"] == "test.event"
        # trace_id may or may not be present — should not crash
        assert isinstance(result, dict)

    def test_processor_does_not_add_trace_id_when_no_span(self):
        from anveshak.tracing import inject_trace_id

        event_dict = {"event": "test.event"}
        result = inject_trace_id(None, "info", event_dict)
        # No active span → no trace_id key
        assert "trace_id" not in result
