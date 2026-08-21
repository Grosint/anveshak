"""Unit tests for Telegram adapter — _normalise_handle edge cases.

pytest.mark.unit — no Telethon client, no network.
Tests the static handle normalisation method and documents the t.me/s/ edge case.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestNormaliseHandle:
    """TelegramAdapter._normalise_handle converts various handle formats to @channel."""

    def test_normalise_handle_t_me_prefix(self):
        """'t.me/defencenews' → '@defencenews'."""
        from anveshak.social.adapters.telegram import TelegramAdapter

        assert TelegramAdapter._normalise_handle("t.me/defencenews") == "@defencenews"

    def test_normalise_handle_at_prefix(self):
        """'@defencenews' → '@defencenews' (unchanged)."""
        from anveshak.social.adapters.telegram import TelegramAdapter

        assert TelegramAdapter._normalise_handle("@defencenews") == "@defencenews"

    def test_normalise_handle_bare_name(self):
        """'defencenews' → '@defencenews' (@ added)."""
        from anveshak.social.adapters.telegram import TelegramAdapter

        assert TelegramAdapter._normalise_handle("defencenews") == "@defencenews"

    def test_normalise_handle_t_me_s_prefix(self):
        """'t.me/s/defencenews' → '@s/defencenews' — the /s/ share prefix is NOT stripped.

        This is a known edge case: t.me/s/channel is Telegram's web share URL format.
        The code strips 't.me/' (first 5 chars) leaving 's/defencenews', then prepends '@'.
        Result '@s/defencenews' will fail in Telethon — this documents the gap.
        """
        from anveshak.social.adapters.telegram import TelegramAdapter

        result = TelegramAdapter._normalise_handle("t.me/s/defencenews")
        # The code does: handle[5:] → "s/defencenews", then prepends "@"
        assert result == "@s/defencenews"
        # This is NOT the correct channel ID — documents a real edge case
        assert result != "@defencenews"
