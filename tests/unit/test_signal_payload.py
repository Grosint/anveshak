"""Unit tests for build_signal_payload — severity classification and field completeness.

Bug caught: boundary condition at ISC == 3. The code uses `>= 3` so ISC=3 is HIGH.
If someone changes to `> 3`, ISC=3 would silently become MEDIUM — weakening alert
sensitivity for the most common convergence threshold.

pytest.mark.unit — pure function, no DB, no network.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestBuildSignalPayload:
    def test_high_severity_when_isc_above_threshold(self):
        """ISC >= 3 → severity HIGH (3+ independent platforms confirm a narrative)."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-1",
            topic_id="topic-1",
            cluster_id="cluster-1",
            independent_source_count=5,
            label="PLA border buildup",
        )
        assert payload["severity"] == "HIGH"

    def test_medium_severity_when_isc_below_threshold(self):
        """ISC < 3 → severity MEDIUM (fewer than 3 independent platforms)."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-2",
            topic_id="topic-1",
            cluster_id="cluster-2",
            independent_source_count=2,
            label="Routine patrol report",
        )
        assert payload["severity"] == "MEDIUM"

    def test_exact_boundary_isc_3_is_high(self):
        """Bug boundary: ISC == 3 must be HIGH, not MEDIUM.

        The threshold `>= 3` means 3 is the first HIGH value.
        If someone changes to `> 3`, this test catches the regression.
        """
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-3",
            topic_id="topic-1",
            cluster_id="cluster-3",
            independent_source_count=3,
            label="Multi-source cluster",
        )
        assert payload["severity"] == "HIGH"

    def test_isc_1_is_medium(self):
        """Single source convergence → MEDIUM."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-4",
            topic_id="topic-1",
            cluster_id="cluster-4",
            independent_source_count=1,
            label="Single source",
        )
        assert payload["severity"] == "MEDIUM"

    def test_all_required_fields_present(self):
        """WebSocket consumers depend on these keys — missing any breaks the frontend."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-5",
            topic_id="topic-1",
            cluster_id="cluster-5",
            independent_source_count=4,
            label="Test cluster",
        )
        required_keys = {
            "type",
            "signal_id",
            "topic_id",
            "cluster_id",
            "cluster_label",
            "severity",
            "independent_source_count",
        }
        assert set(payload.keys()) == required_keys

    def test_type_field_is_signal(self):
        """The type field must always be 'signal' — WebSocket router uses this for dispatch."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="sig-6",
            topic_id="topic-1",
            cluster_id="cluster-6",
            independent_source_count=1,
            label="Test",
        )
        assert payload["type"] == "signal"

    def test_passthrough_fields_not_mutated(self):
        """signal_id, topic_id, cluster_id, label must pass through unchanged."""
        from anveshak.analyst.signal_engine import build_signal_payload

        payload = build_signal_payload(
            signal_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            topic_id="topic-uuid-123",
            cluster_id="cluster-uuid-456",
            independent_source_count=2,
            label="Exact Label Here",
        )
        assert payload["signal_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert payload["topic_id"] == "topic-uuid-123"
        assert payload["cluster_id"] == "cluster-uuid-456"
        assert payload["cluster_label"] == "Exact Label Here"
        assert payload["independent_source_count"] == 2
