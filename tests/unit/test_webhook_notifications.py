"""Unit tests for webhook signal notifications.

Tests:
  - send_webhook returns False when disabled
  - send_webhook returns True on successful POST
  - send_webhook returns False on HTTP error
  - send_webhook returns False on network error
  - Webhook never raises (always returns bool)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


SAMPLE_PAYLOAD = {
    "type": "signal",
    "signal_id": "sig-123",
    "topic_id": "top-1",
    "cluster_id": "cl-1",
    "signal_type": "multi_source_convergence",
    "severity": "HIGH",
    "independent_source_count": 3,
    "description": "Test signal",
}


class TestSendWebhook:
    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self):
        from anveshak.api.notifications import send_webhook

        with patch("anveshak.api.notifications.settings") as mock_settings:
            mock_settings.signal_webhook_enabled = False
            mock_settings.signal_webhook_url = "https://hook.example.com"
            result = await send_webhook(SAMPLE_PAYLOAD)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_url(self):
        from anveshak.api.notifications import send_webhook

        with patch("anveshak.api.notifications.settings") as mock_settings:
            mock_settings.signal_webhook_enabled = True
            mock_settings.signal_webhook_url = None
            result = await send_webhook(SAMPLE_PAYLOAD)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        from anveshak.api.notifications import send_webhook

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("anveshak.api.notifications.settings") as mock_settings,
            patch("anveshak.api.notifications.httpx.AsyncClient") as MockClient,  # noqa: N806 - binds a class, PascalCase is correct
        ):
            mock_settings.signal_webhook_enabled = True
            mock_settings.signal_webhook_url = "https://hook.example.com"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await send_webhook(SAMPLE_PAYLOAD)

        assert result is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "https://hook.example.com" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_returns_false_on_http_error(self):
        from anveshak.api.notifications import send_webhook

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with (
            patch("anveshak.api.notifications.settings") as mock_settings,
            patch("anveshak.api.notifications.httpx.AsyncClient") as MockClient,  # noqa: N806 - binds a class, PascalCase is correct
        ):
            mock_settings.signal_webhook_enabled = True
            mock_settings.signal_webhook_url = "https://hook.example.com"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await send_webhook(SAMPLE_PAYLOAD)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_network_error(self):
        from anveshak.api.notifications import send_webhook

        with (
            patch("anveshak.api.notifications.settings") as mock_settings,
            patch("anveshak.api.notifications.httpx.AsyncClient") as MockClient,  # noqa: N806 - binds a class, PascalCase is correct
        ):
            mock_settings.signal_webhook_enabled = True
            mock_settings.signal_webhook_url = "https://hook.example.com"

            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await send_webhook(SAMPLE_PAYLOAD)

        assert result is False

    @pytest.mark.asyncio
    async def test_sends_correct_headers(self):
        from anveshak.api.notifications import send_webhook

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("anveshak.api.notifications.settings") as mock_settings,
            patch("anveshak.api.notifications.httpx.AsyncClient") as MockClient,  # noqa: N806 - binds a class, PascalCase is correct
        ):
            mock_settings.signal_webhook_enabled = True
            mock_settings.signal_webhook_url = "https://hook.example.com"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            await send_webhook(SAMPLE_PAYLOAD)

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("X-Anveshak-Event") == "signal"
