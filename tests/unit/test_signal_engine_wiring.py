"""Unit tests for signal_engine_loop Engine C wiring.

Verifies that signal_engine_loop calls all 4 check functions:
  1. check_signals (narrative multi-source convergence)
  2. check_sentiment_shifts
  3. check_identifier_signals (Engine C)
  4. check_template_signals (Engine C)

pytest.mark.unit -- no external dependencies, no DB, no network.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MOD = "anveshak.analyst.signal_engine"


async def _run_one_cycle(mock_pool, mock_broadcast, patches_dict):
    """Run signal_engine_loop for exactly one cycle then cancel."""
    from anveshak.analyst.signal_engine import signal_engine_loop

    task = asyncio.create_task(signal_engine_loop(mock_pool, mock_broadcast))
    # Let one cycle complete
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.unit
class TestSignalEngineLoopCallsIdentifierSignals:
    """signal_engine_loop must call check_identifier_signals each cycle."""

    @pytest.mark.asyncio
    async def test_check_identifier_signals_called(self):
        mock_pool = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch(f"{_MOD}.check_signals", new_callable=AsyncMock, return_value=0),
            patch(f"{_MOD}.check_sentiment_shifts", new_callable=AsyncMock, return_value=0),
            patch(
                f"{_MOD}.check_identifier_signals", new_callable=AsyncMock, return_value=2
            ) as mock_id_signals,
            patch(f"{_MOD}.check_template_signals", new_callable=AsyncMock, return_value=0),
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.signal_check_interval_s = 0.01
            await _run_one_cycle(mock_pool, mock_broadcast, {})

        mock_id_signals.assert_called_with(mock_pool, mock_broadcast)


@pytest.mark.unit
class TestSignalEngineLoopCallsTemplateSignals:
    """signal_engine_loop must call check_template_signals each cycle."""

    @pytest.mark.asyncio
    async def test_check_template_signals_called(self):
        mock_pool = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch(f"{_MOD}.check_signals", new_callable=AsyncMock, return_value=0),
            patch(f"{_MOD}.check_sentiment_shifts", new_callable=AsyncMock, return_value=0),
            patch(f"{_MOD}.check_identifier_signals", new_callable=AsyncMock, return_value=0),
            patch(
                f"{_MOD}.check_template_signals", new_callable=AsyncMock, return_value=1
            ) as mock_tpl_signals,
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.signal_check_interval_s = 0.01
            await _run_one_cycle(mock_pool, mock_broadcast, {})

        mock_tpl_signals.assert_called_with(mock_pool, mock_broadcast)


@pytest.mark.unit
class TestSignalEngineLoopCountsAllSignalTypes:
    """Log output must include identifier + template signal counts."""

    @pytest.mark.asyncio
    async def test_total_includes_all_signal_types(self):
        mock_pool = MagicMock()
        mock_broadcast = AsyncMock()

        with (
            patch(f"{_MOD}.check_signals", new_callable=AsyncMock, return_value=1),
            patch(f"{_MOD}.check_sentiment_shifts", new_callable=AsyncMock, return_value=1),
            patch(f"{_MOD}.check_identifier_signals", new_callable=AsyncMock, return_value=2),
            patch(f"{_MOD}.check_template_signals", new_callable=AsyncMock, return_value=3),
            patch(f"{_MOD}.settings") as mock_settings,
            patch(f"{_MOD}.log") as mock_log,
        ):
            mock_settings.signal_check_interval_s = 0.01
            await _run_one_cycle(mock_pool, mock_broadcast, {})

        # Log should be called since total > 0
        mock_log.info.assert_called()
        # Find the cycle_complete log call
        cycle_calls = [
            c for c in mock_log.info.call_args_list if c.args and "cycle_complete" in str(c.args[0])
        ]
        assert len(cycle_calls) >= 1, "signal_engine.cycle_complete not logged"
        kwargs = cycle_calls[0].kwargs
        assert kwargs.get("identifier_signals") == 2, (
            f"identifier_signals count missing or wrong: {kwargs}"
        )
        assert kwargs.get("template_signals") == 3, (
            f"template_signals count missing or wrong: {kwargs}"
        )


@pytest.mark.unit
class TestSignalEngineImportsExist:
    """Verify check_identifier_signals and check_template_signals are importable from signal_engine."""

    def test_imports_exist(self):
        from anveshak.analyst.signal_engine import check_identifier_signals, check_template_signals

        assert callable(check_identifier_signals)
        assert callable(check_template_signals)
