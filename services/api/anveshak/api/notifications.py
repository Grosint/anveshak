"""Webhook notification dispatcher for signal delivery.

Sends signal payloads to a configured webhook URL when signals are delivered.
Non-blocking — webhook failures never prevent signal delivery via WebSocket.
"""
from __future__ import annotations

import json

import httpx
import structlog

from .settings import settings

log = structlog.get_logger(__name__)

# Timeout for webhook POST — short to avoid blocking delivery loop
_WEBHOOK_TIMEOUT = 10.0


async def send_webhook(payload: dict) -> bool:
    """POST signal payload to configured webhook URL.

    Returns True on success, False on any failure (never raises).
    """
    webhook_url = settings.signal_webhook_url
    if not webhook_url or not settings.signal_webhook_enabled:
        return False

    try:
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Anveshak-Signal-Webhook/1.0",
                    "X-Anveshak-Event": "signal",
                },
            )
            if resp.status_code < 300:
                log.info(
                    "webhook.delivered",
                    signal_id=payload.get("signal_id"),
                    status=resp.status_code,
                )
                return True
            log.warning(
                "webhook.http_error",
                signal_id=payload.get("signal_id"),
                status=resp.status_code,
                body=resp.text[:200],
            )
            return False
    except Exception as exc:
        log.warning(
            "webhook.failed",
            signal_id=payload.get("signal_id"),
            error=str(exc),
        )
        return False
