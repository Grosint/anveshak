"""Unit tests for Engine C Step 4a — Identifier Convergence Signals.

Tests that identifier clusters crossing source thresholds fire signals
with correct severity, evidence, dedup, and broadcast.

Bugs this test suite catches:
  1. Severity boundary: source_count=3 must be HIGH (not MEDIUM)
  2. Severity boundary: source_count=5 must be CRITICAL (not HIGH)
  3. Dedup: same identifier_cluster_id must not fire twice in 24h
  4. Evidence JSONB must contain all required keys for audit trail
  5. cluster_id on signals table must be NULL (FK is narrative_clusters)
  6. Broadcast failure must not crash check cycle or reduce fired count
  7. source_count below threshold must not fire

pytest.mark.unit — no DB, no Redis, no external dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool_and_conn():
    """Create mock asyncpg pool + connection with async context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm
    return pool, conn


def _cluster_row(
    cluster_id: str = "ic-1",
    topic_id: str = "t-1",
    identifier_type: str = "PHONE_IN",
    identifier_value: str = "9876543210",
    source_count: int = 3,
    content_item_count: int = 5,
    threshold: int = 2,
):
    """Fake row from SQL_BREACHING_IDENTIFIER_CLUSTERS."""
    return {
        "identifier_cluster_id": cluster_id,
        "topic_id": topic_id,
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "source_count": source_count,
        "content_item_count": content_item_count,
        "identifier_signal_threshold": threshold,
    }


def _source_row(name: str, platform: str):
    """Fake row from SQL_IDENTIFIER_CLUSTER_SOURCES."""
    return {"name": name, "platform": platform}


# ===========================================================================
# Pure functions
# ===========================================================================


class TestComputeIdentifierSeverity:
    """Severity: MEDIUM < 3 sources, HIGH >= 3, CRITICAL >= 5."""

    def test_source_count_1_medium(self):
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(1) == "MEDIUM"

    def test_source_count_2_medium(self):
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(2) == "MEDIUM"

    def test_source_count_3_high(self):
        """Boundary: exactly 3 sources → HIGH."""
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(3) == "HIGH"

    def test_source_count_4_high(self):
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(4) == "HIGH"

    def test_source_count_5_critical(self):
        """Boundary: exactly 5 sources → CRITICAL."""
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(5) == "CRITICAL"

    def test_source_count_10_critical(self):
        from anveshak.analyst.identifier_signals import compute_identifier_severity

        assert compute_identifier_severity(10) == "CRITICAL"


class TestBuildIdentifierEvidence:
    """Evidence JSONB must contain all required fields from plan."""

    def test_all_required_keys(self):
        from anveshak.analyst.identifier_signals import build_identifier_evidence

        evidence = build_identifier_evidence(
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
            sources=["telegram:easy_money", "telegram:account_service"],
            content_item_count=5,
        )
        assert evidence["identifier_cluster_id"] == "ic-1"
        assert evidence["identifier_type"] == "PHONE_IN"
        assert evidence["identifier_value"] == "9876543210"
        assert evidence["source_count"] == 3
        assert evidence["sources"] == ["telegram:easy_money", "telegram:account_service"]
        assert evidence["content_item_count"] == 5

    def test_returns_dict(self):
        from anveshak.analyst.identifier_signals import build_identifier_evidence

        evidence = build_identifier_evidence(
            identifier_cluster_id="ic-1",
            identifier_type="UPI",
            identifier_value="fraud@ybl",
            source_count=2,
            sources=["rss:feed1"],
            content_item_count=3,
        )
        assert isinstance(evidence, dict)

    def test_exactly_six_keys(self):
        from anveshak.analyst.identifier_signals import build_identifier_evidence

        evidence = build_identifier_evidence(
            identifier_cluster_id="ic-1",
            identifier_type="CRYPTO_BTC",
            identifier_value="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            source_count=4,
            sources=["s1", "s2", "s3", "s4"],
            content_item_count=8,
        )
        assert len(evidence) == 6

    def test_json_serializable(self):
        from anveshak.analyst.identifier_signals import build_identifier_evidence

        evidence = build_identifier_evidence(
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=2,
            sources=["s1"],
            content_item_count=2,
        )
        serialized = json.dumps(evidence)
        assert isinstance(serialized, str)


class TestBuildIdentifierDescription:
    """Human-readable signal description."""

    def test_contains_type_and_count(self):
        from anveshak.analyst.identifier_signals import build_identifier_description

        desc = build_identifier_description(
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
        )
        assert "PHONE_IN" in desc
        assert "3" in desc

    def test_contains_identifier_value(self):
        from anveshak.analyst.identifier_signals import build_identifier_description

        desc = build_identifier_description(
            identifier_type="UPI",
            identifier_value="fraud@ybl",
            source_count=5,
        )
        assert "fraud@ybl" in desc

    def test_returns_string(self):
        from anveshak.analyst.identifier_signals import build_identifier_description

        desc = build_identifier_description(
            identifier_type="CRYPTO_BTC",
            identifier_value="1A1zP1",
            source_count=2,
        )
        assert isinstance(desc, str)


class TestBuildIdentifierSignalPayload:
    """WebSocket push message for identifier convergence."""

    def test_has_signal_type_field(self):
        from anveshak.analyst.identifier_signals import build_identifier_signal_payload

        payload = build_identifier_signal_payload(
            signal_id="sig-1",
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
        )
        assert payload["type"] == "signal"
        assert payload["signal_type"] == "identifier_convergence"

    def test_severity_from_source_count(self):
        from anveshak.analyst.identifier_signals import build_identifier_signal_payload

        payload = build_identifier_signal_payload(
            signal_id="sig-1",
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=5,
        )
        assert payload["severity"] == "CRITICAL"

    def test_all_required_fields(self):
        from anveshak.analyst.identifier_signals import build_identifier_signal_payload

        payload = build_identifier_signal_payload(
            signal_id="sig-1",
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="UPI",
            identifier_value="fraud@ybl",
            source_count=3,
        )
        assert payload["signal_id"] == "sig-1"
        assert payload["topic_id"] == "t-1"
        assert payload["identifier_cluster_id"] == "ic-1"
        assert payload["identifier_type"] == "UPI"
        assert payload["identifier_value"] == "fraud@ybl"
        assert payload["source_count"] == 3

    def test_medium_severity(self):
        from anveshak.analyst.identifier_signals import build_identifier_signal_payload

        payload = build_identifier_signal_payload(
            signal_id="sig-1",
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=2,
        )
        assert payload["severity"] == "MEDIUM"


# ===========================================================================
# Async DB functions
# ===========================================================================


class TestIsDuplicateIdentifierSignal:
    """24h dedup window via evidence JSONB query."""

    @pytest.mark.asyncio
    async def test_existing_signal_returns_true(self):
        from anveshak.analyst.identifier_signals import is_duplicate_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": "existing-signal"}

        result = await is_duplicate_identifier_signal(conn, "ic-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_existing_signal_returns_false(self):
        from anveshak.analyst.identifier_signals import is_duplicate_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        result = await is_duplicate_identifier_signal(conn, "ic-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_queries_with_cluster_id(self):
        """Must pass identifier_cluster_id to dedup query."""
        from anveshak.analyst.identifier_signals import is_duplicate_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await is_duplicate_identifier_signal(conn, "ic-42")

        call_args = conn.fetchrow.call_args[0]
        # identifier_cluster_id should appear in query params
        assert "ic-42" in call_args


class TestFireIdentifierSignal:
    """Insert identifier_convergence signal row."""

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_dedup_returns_none(self, mock_metric):
        """Duplicate signal → return None, no INSERT."""
        from anveshak.analyst.identifier_signals import fire_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = {"id": "existing"}  # dedup hit

        result = await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
            sources=["s1", "s2", "s3"],
            content_item_count=5,
            now=datetime.now(timezone.utc),
        )
        assert result is None
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_inserts_and_returns_uuid(self, mock_metric):
        """No duplicate → INSERT called, returns UUID string."""
        from anveshak.analyst.identifier_signals import fire_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None  # no dedup hit

        result = await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
            sources=["s1", "s2", "s3"],
            content_item_count=5,
            now=datetime.now(timezone.utc),
        )
        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_evidence_json_correct(self, mock_metric):
        """Evidence contains all identifier convergence fields."""
        from anveshak.analyst.identifier_signals import fire_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=5,
            sources=["telegram:ch1", "telegram:ch2"],
            content_item_count=14,
            now=datetime.now(timezone.utc),
        )

        call_args = conn.execute.call_args[0]
        # Evidence is the JSON string arg — find it
        evidence_str = None
        for arg in call_args:
            if isinstance(arg, str) and "identifier_cluster_id" in arg:
                evidence_str = arg
                break
        assert evidence_str is not None
        evidence = json.loads(evidence_str)
        assert evidence["identifier_cluster_id"] == "ic-1"
        assert evidence["identifier_type"] == "PHONE_IN"
        assert evidence["source_count"] == 5
        assert evidence["content_item_count"] == 14

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_cluster_id_column_is_none(self, mock_metric):
        """signals.cluster_id FK is for narrative_clusters — must be NULL for identifier signals."""
        from anveshak.analyst.identifier_signals import fire_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
            sources=["s1"],
            content_item_count=3,
            now=datetime.now(timezone.utc),
        )

        call_args = conn.execute.call_args[0]
        # The SQL_INSERT_SIGNAL has cluster_id as 3rd param (0-indexed: position 3)
        # signal_id=$1, topic_id=$2, cluster_id=$3, signal_type=$4, ...
        # cluster_id should be None
        assert None in call_args

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_signal_type_is_identifier_convergence(self, mock_metric):
        """signal_type must be 'identifier_convergence'."""
        from anveshak.analyst.identifier_signals import (
            SIGNAL_TYPE_IDENTIFIER_CONVERGENCE,
            fire_identifier_signal,
        )

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=3,
            sources=["s1"],
            content_item_count=3,
            now=datetime.now(timezone.utc),
        )

        call_args = conn.execute.call_args[0]
        assert SIGNAL_TYPE_IDENTIFIER_CONVERGENCE in call_args

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.analyst_signals_fired_total")
    async def test_severity_metric_incremented(self, mock_metric):
        """Prometheus counter incremented with correct severity label."""
        from anveshak.analyst.identifier_signals import fire_identifier_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await fire_identifier_signal(
            conn=conn,
            topic_id="t-1",
            identifier_cluster_id="ic-1",
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            source_count=5,
            sources=["s1", "s2", "s3", "s4", "s5"],
            content_item_count=10,
            now=datetime.now(timezone.utc),
        )

        mock_metric.labels.assert_called_with(severity="CRITICAL")
        mock_metric.labels.return_value.inc.assert_called_once()


# ===========================================================================
# check_identifier_signals — orchestrator
# ===========================================================================


class TestCheckIdentifierSignals:
    """Full check cycle: query breaching clusters, fire signals, broadcast."""

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_no_breaching_clusters(self, mock_fire):
        """No clusters above threshold → 0 fired."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.return_value = []  # no breaching clusters

        broadcast = AsyncMock()
        fired = await check_identifier_signals(pool, broadcast)

        assert fired == 0
        mock_fire.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.build_identifier_signal_payload")
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_one_breaching_cluster_fires(self, mock_fire, mock_payload):
        """One cluster above threshold → 1 signal fired + broadcast."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_cluster_row("ic-1", "t-1", "PHONE_IN", "9876543210", 3, 5, 2)],
            [_source_row("easy_money", "telegram"), _source_row("fraud_reports", "rss")],
        ]
        mock_fire.return_value = "signal-id-1"
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock()
        fired = await check_identifier_signals(pool, broadcast)

        assert fired == 1
        mock_fire.assert_awaited_once()
        broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_dedup_skips_duplicate(self, mock_fire):
        """fire_identifier_signal returns None (dedup) → not counted, no broadcast."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_cluster_row()],
            [_source_row("ch1", "telegram")],
        ]
        mock_fire.return_value = None  # dedup hit

        broadcast = AsyncMock()
        fired = await check_identifier_signals(pool, broadcast)

        assert fired == 0
        broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.build_identifier_signal_payload")
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_broadcast_failure_no_crash(self, mock_fire, mock_payload):
        """Broadcast raises → fired count still 1, no crash."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_cluster_row()],
            [_source_row("ch1", "telegram")],
        ]
        mock_fire.return_value = "signal-id-1"
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock(side_effect=RuntimeError("WebSocket closed"))
        fired = await check_identifier_signals(pool, broadcast)

        assert fired == 1

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.build_identifier_signal_payload")
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_multiple_clusters_multiple_signals(self, mock_fire, mock_payload):
        """Three breaching clusters → 3 signals fired."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            # First call: breaching clusters
            [
                _cluster_row("ic-1", "t-1", "PHONE_IN", "9876543210", 3, 5, 2),
                _cluster_row("ic-2", "t-1", "UPI", "fraud@ybl", 4, 8, 2),
                _cluster_row("ic-3", "t-2", "CRYPTO_BTC", "1A1zP1", 5, 12, 2),
            ],
            # Source queries for each cluster
            [_source_row("ch1", "telegram")],
            [_source_row("ch2", "rss")],
            [_source_row("ch3", "reddit")],
        ]
        mock_fire.side_effect = ["sig-1", "sig-2", "sig-3"]
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock()
        fired = await check_identifier_signals(pool, broadcast)

        assert fired == 3
        assert mock_fire.await_count == 3
        assert broadcast.await_count == 3

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.build_identifier_signal_payload")
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_sources_passed_to_fire(self, mock_fire, mock_payload):
        """Source names from DB query must be passed to fire_identifier_signal."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_cluster_row("ic-1", "t-1", "PHONE_IN", "9876543210", 3, 5, 2)],
            [
                _source_row("easy_money", "telegram"),
                _source_row("fraud_alerts", "rss"),
                _source_row("scam_watch", "reddit"),
            ],
        ]
        mock_fire.return_value = "sig-1"
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock()
        await check_identifier_signals(pool, broadcast)

        fire_kwargs = mock_fire.call_args.kwargs
        sources = fire_kwargs["sources"]
        assert len(sources) == 3
        assert "telegram:easy_money" in sources

    @pytest.mark.asyncio
    @patch("anveshak.analyst.identifier_signals.build_identifier_signal_payload")
    @patch("anveshak.analyst.identifier_signals.fire_identifier_signal", new_callable=AsyncMock)
    async def test_payload_broadcast_matches_fire_result(self, mock_fire, mock_payload):
        """Payload built with signal_id from fire_identifier_signal."""
        from anveshak.analyst.identifier_signals import check_identifier_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.side_effect = [
            [_cluster_row("ic-1", "t-1", "PHONE_IN", "9876543210", 3, 5, 2)],
            [_source_row("ch1", "telegram")],
        ]
        mock_fire.return_value = "signal-uuid-123"
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock()
        await check_identifier_signals(pool, broadcast)

        # build_identifier_signal_payload called with signal_id from fire result
        payload_kwargs = mock_payload.call_args.kwargs
        assert payload_kwargs["signal_id"] == "signal-uuid-123"


# ===========================================================================
# Signal type constant
# ===========================================================================


class TestSignalTypeConstant:
    def test_constant_value(self):
        from anveshak.analyst.identifier_signals import SIGNAL_TYPE_IDENTIFIER_CONVERGENCE

        assert SIGNAL_TYPE_IDENTIFIER_CONVERGENCE == "identifier_convergence"

    def test_sql_constants_exist(self):
        """Module must export SQL constants for testability."""
        from anveshak.analyst.identifier_signals import (
            SQL_BREACHING_IDENTIFIER_CLUSTERS,
            SQL_DUPLICATE_IDENTIFIER_SIGNAL_CHECK,
            SQL_IDENTIFIER_CLUSTER_SOURCES,
        )

        assert "identifier_clusters" in SQL_BREACHING_IDENTIFIER_CLUSTERS
        assert "identifier_convergence" in SQL_DUPLICATE_IDENTIFIER_SIGNAL_CHECK
        assert "identifier_cluster_items" in SQL_IDENTIFIER_CLUSTER_SOURCES
