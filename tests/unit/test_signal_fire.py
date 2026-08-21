"""Unit tests for signal engine fire_signal and check_signals.

Bugs caught:
  1. Duplicate signal returns None but must NOT insert — dedup guard
  2. Broadcast failure must not crash the check cycle or reduce fired count
  3. Null cluster label must fallback to "Cluster {id[:8]}"
  4. isc=threshold must fire (>= not >) — boundary condition
  5. Evidence JSON must contain correct keys for audit trail

pytest.mark.unit — no DB, no Redis, no external dependencies.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_pool_and_conn():
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acm
    return pool, conn


def _cluster_row(cluster_id: str, topic_id: str, label, isc: int, threshold: int):
    return {
        "cluster_id": cluster_id,
        "topic_id": topic_id,
        "label": label,
        "independent_source_count": isc,
        "signal_threshold": threshold,
    }


# ---------------------------------------------------------------------------
# fire_signal
# ---------------------------------------------------------------------------


class TestFireSignal:
    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.analyst_signals_fired_total")
    async def test_dedup_returns_none(self, mock_metric):
        """Existing signal in 24h window → return None, no INSERT."""
        from anveshak.analyst.signal_engine import fire_signal

        conn = AsyncMock()
        # is_duplicate_signal does conn.fetchrow → returns a row (truthy)
        conn.fetchrow.return_value = {"id": "existing-signal-id"}

        from datetime import UTC, datetime

        result = await fire_signal(conn, "t1", "c1", "Test cluster", 3, datetime.now(UTC))

        assert result is None
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.analyst_signals_fired_total")
    async def test_inserts_and_returns_id(self, mock_metric):
        """No duplicate → INSERT called, returns UUID string."""
        from anveshak.analyst.signal_engine import fire_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None  # no duplicate

        from datetime import UTC, datetime

        result = await fire_signal(conn, "t1", "c1", "Test cluster", 3, datetime.now(UTC))

        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.analyst_signals_fired_total")
    async def test_correct_evidence_json(self, mock_metric):
        """Evidence JSON must have cluster_id and independent_source_count keys."""
        from anveshak.analyst.signal_engine import fire_signal

        conn = AsyncMock()
        conn.fetchrow.return_value = None

        from datetime import UTC, datetime

        await fire_signal(conn, "t1", "c1", "Test cluster", 5, datetime.now(UTC))

        # SQL_INSERT_SIGNAL args: signal_id, topic_id, cluster_id, signal_type, description, evidence, now
        call_args = conn.execute.call_args[0]
        evidence_json = call_args[6]  # 7th positional arg (0-indexed: 6)
        evidence = json.loads(evidence_json)
        assert evidence["cluster_id"] == "c1"
        assert evidence["independent_source_count"] == 5


# ---------------------------------------------------------------------------
# check_signals
# ---------------------------------------------------------------------------


class TestCheckSignals:
    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.fire_signal", new_callable=AsyncMock)
    @patch("anveshak.analyst.signal_engine.build_signal_payload")
    async def test_broadcast_failure_no_block(self, mock_payload, mock_fire):
        """broadcast raises RuntimeError → fired count still 1, no crash."""
        from anveshak.analyst.signal_engine import check_signals

        pool, conn = _make_pool_and_conn()
        conn.fetch.return_value = [_cluster_row("c1", "t1", "Test", 3, 2)]
        mock_fire.return_value = "signal-id-1"
        mock_payload.return_value = {"type": "signal"}

        broadcast = AsyncMock(side_effect=RuntimeError("WebSocket closed"))

        fired = await check_signals(pool, broadcast)

        assert fired == 1  # still counted despite broadcast failure

    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.fire_signal", new_callable=AsyncMock)
    async def test_null_label_fallback(self, mock_fire):
        """Cluster with label=None → fire_signal receives 'Cluster {id[:8]}'."""
        from anveshak.analyst.signal_engine import check_signals

        cluster_id = "abcdef1234567890abcdef1234567890"
        pool, conn = _make_pool_and_conn()
        conn.fetch.return_value = [_cluster_row(cluster_id, "t1", None, 3, 2)]
        mock_fire.return_value = "signal-id-1"

        broadcast = AsyncMock()
        await check_signals(pool, broadcast)

        # fire_signal's cluster_label arg should be the fallback
        call_kwargs = mock_fire.call_args.kwargs
        assert call_kwargs["cluster_label"] == f"Cluster {cluster_id[:8]}"

    @pytest.mark.asyncio
    @patch("anveshak.analyst.signal_engine.fire_signal", new_callable=AsyncMock)
    async def test_isc_boundary(self, mock_fire):
        """Cluster with isc == threshold → signal fires (>= not >).

        Bug: SQL uses >= but if check_signals added a Python-side > guard,
        boundary clusters would be silently dropped.
        """
        from anveshak.analyst.signal_engine import check_signals

        # isc=2, threshold=2 → should appear in SQL_BREACHING_CLUSTERS result
        pool, conn = _make_pool_and_conn()
        conn.fetch.return_value = [_cluster_row("c1", "t1", "Boundary", 2, 2)]
        mock_fire.return_value = "signal-id-1"

        broadcast = AsyncMock()
        fired = await check_signals(pool, broadcast)

        assert fired == 1
        mock_fire.assert_awaited_once()
