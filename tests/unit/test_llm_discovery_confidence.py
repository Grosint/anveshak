"""Unit tests for the LLM-discovery confidence setting.

Rule 6 (hardware independence) and the "one setting, one purpose" rule:
the confidence assigned to an LLM-suggested source is tuning, so it belongs
in settings.py and in the compose environment block, not inline in
llm_discovery.py.

Distinct from templates._CONFIDENCE_THRESHOLD, which is an accept floor for
a template match. Same value today, different purpose.

Compose forwarding is not asserted here: tests/unit/test_env_forwarding.py
already gates every .env.example var against compose, and catches dead vars
too.

pytest.mark.unit -- no external dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MOD = "anveshak.analyst.llm_discovery"

VALID_LLM_RESPONSE = """{"suggestions": [
  {"platform": "telegram", "description": "Border trade channels",
   "search_terms": ["moreh", "tamu"], "reasoning": "Local traders post here"}
]}"""


@pytest.mark.unit
class TestLlmDiscoveryConfidenceSetting:
    """AnalystSettings must expose the confidence as a bounded tunable."""

    def test_default_preserves_todays_value(self):
        """Assert the declared default, not the singleton: an operator with
        LLM_DISCOVERY_CONFIDENCE set in .env must not fail make test-unit."""
        from anveshak.analyst.settings import AnalystSettings

        field = AnalystSettings.model_fields.get("llm_discovery_confidence")
        assert field is not None, "Missing llm_discovery_confidence setting"
        assert field.default == 0.5, "Default should preserve today's 0.5"

    def test_configured_value_is_a_probability(self):
        """Runtime invariant, checked against whatever the environment set."""
        from anveshak.analyst.settings import settings

        assert 0.0 <= settings.llm_discovery_confidence <= 1.0

    @pytest.mark.parametrize("bad", [-0.1, 1.5])
    def test_out_of_range_value_fails_startup(self, bad: float):
        """A bad env var must crash at construction, not stamp a bogus score.

        discovered_sources.confidence_score is a bare REAL with no CHECK, so
        an unbounded setting would silently skew discovery ranking.
        """
        from anveshak.analyst.settings import AnalystSettings
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AnalystSettings(llm_discovery_confidence=bad)


@pytest.mark.unit
class TestLlmDiscoveryConfidenceIsWired:
    """suggest_source_types must read the setting, not a literal."""

    @pytest.mark.asyncio
    async def test_upsert_uses_the_configured_confidence(self):
        from anveshak.analyst.llm_discovery import suggest_source_types

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"name": "Border", "keywords": ["moreh"]})
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(f"{_MOD}.call_ollama", return_value=VALID_LLM_RESPONSE),
            patch(f"{_MOD}.settings") as mock_settings,
        ):
            mock_settings.llm_discovery_confidence = 0.77
            count = await suggest_source_types(pool, "topic-1")

        assert count == 1
        args = conn.execute.call_args.args
        assert 0.77 in args, f"confidence not read from settings; execute args were {args}"
