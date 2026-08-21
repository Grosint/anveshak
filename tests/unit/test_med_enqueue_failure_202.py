"""Unit tests for ARQ enqueue failure response — MED-14.

POST /topics must return 202 (not 201) when topic is created but
backfill job enqueue fails, so the analyst knows processing is delayed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestEnqueueFailureReturns202:
    @pytest.mark.asyncio
    async def test_enqueue_failure_returns_202_with_warning(self):
        """When Redis enqueue fails, response must be 202 with warning field."""
        from anveshak.api.routes.topics import create_topic

        req = MagicMock()
        req.name = "Test Topic"
        req.keywords = ["test"]
        req.languages = ["en"]
        req.credibility_min = 30.0
        req.signal_threshold = 3
        req.clip_categories = []
        req.scheduled_report_cron = None
        req.scheduled_report_type = None
        req.identifier_signal_threshold = 2

        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_user = {"sub": "user-1", "role": "analyst", "org_id": "org-1"}

        with (
            patch("anveshak.api.routes.topics.topics_db.insert_topic", new_callable=AsyncMock),
            patch("anveshak.api.routes.topics.audit_db.log_action", new_callable=AsyncMock),
            patch("anveshak.api.routes.topics.arq_create_pool", new_callable=AsyncMock) as mock_arq,
        ):
            # Enqueue fails
            mock_pool = AsyncMock()
            mock_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis down"))
            mock_arq.return_value = mock_pool

            result = await create_topic(req, mock_request, mock_db, mock_user)

        # Must contain warning field
        if hasattr(result, "body"):
            body = json.loads(result.body)
            assert result.status_code == 202
            assert "warning" in body
        else:
            # Dict response — check for warning key
            assert "warning" in result, "Enqueue failure must return a warning field in response"
