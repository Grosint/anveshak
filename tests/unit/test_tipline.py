"""Tip-Line Ingestion Endpoint — Engine C Step 6.

Tests for POST /api/v1/tipline/ingest:
  - Request validation (Pydantic model)
  - API key authentication (X-Api-Key header)
  - Content creation + dedup (content_hash)
  - ARQ job enqueue (analyse_content)
  - Rate limiting (100 req/min per API key)
  - Error handling (missing fields, invalid topic, etc.)
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Import targets
# ---------------------------------------------------------------------------

from services.api.anveshak.api.routes.tipline import (
    TiplineIngestRequest,
    TiplineIngestResponse,
    _normalise,
    _compute_hash,
)
from services.api.anveshak.api.db.tipline import (
    SQL_LOOKUP_API_KEY,
    SQL_INSERT_TIPLINE_CONTENT,
    SQL_GET_TIPLINE_SOURCE,
    lookup_api_key,
    insert_tipline_content,
    get_or_create_tipline_source,
)


# ---------------------------------------------------------------------------
# TiplineIngestRequest validation
# ---------------------------------------------------------------------------

class TestTiplineRequestValidation:
    """Pydantic request model enforces required fields."""

    def test_valid_request(self):
        req = TiplineIngestRequest(
            text="Got a scam call from +919876543210 asking for bank details",
            topic_id="topic-001",
        )
        assert req.text == "Got a scam call from +919876543210 asking for bank details"
        assert req.topic_id == "topic-001"
        assert req.media_url is None
        assert req.source_phone is None
        assert req.forwarded_from is None

    def test_all_fields(self):
        req = TiplineIngestRequest(
            text="Scam message content",
            topic_id="topic-002",
            media_url="https://example.com/scam-screenshot.jpg",
            source_phone="+911234567890",
            forwarded_from="unknown_sender",
        )
        assert req.media_url == "https://example.com/scam-screenshot.jpg"
        assert req.source_phone == "+911234567890"
        assert req.forwarded_from == "unknown_sender"

    def test_text_required(self):
        with pytest.raises(Exception):
            TiplineIngestRequest(topic_id="topic-001")

    def test_topic_id_required(self):
        with pytest.raises(Exception):
            TiplineIngestRequest(text="some text")

    def test_empty_text_rejected(self):
        with pytest.raises(Exception):
            TiplineIngestRequest(text="", topic_id="topic-001")

    def test_labels_field_exists(self):
        """CLAUDE.md: every Pydantic model MUST have labels field."""
        req = TiplineIngestRequest(
            text="Test", topic_id="t-001",
        )
        assert hasattr(req, "labels")


class TestTiplineResponseModel:
    """Response model shape."""

    def test_response_shape(self):
        resp = TiplineIngestResponse(
            id="ci-001",
            content_hash="abc123",
            status="queued",
            duplicate=False,
        )
        assert resp.id == "ci-001"
        assert resp.status == "queued"
        assert resp.duplicate is False

    def test_duplicate_response(self):
        resp = TiplineIngestResponse(
            id="ci-002",
            content_hash="abc123",
            status="duplicate",
            duplicate=True,
        )
        assert resp.duplicate is True
        assert resp.status == "duplicate"


# ---------------------------------------------------------------------------
# Normalisation + hashing helpers
# ---------------------------------------------------------------------------

class TestNormalisationHelpers:
    """Same normalisation logic as social/ingest.py — lowercase + collapse whitespace."""

    def test_normalise_lowercase(self):
        assert _normalise("HELLO World") == "hello world"

    def test_normalise_collapse_whitespace(self):
        assert _normalise("hello   \n  world") == "hello world"

    def test_normalise_strip(self):
        assert _normalise("  padded  ") == "padded"

    def test_compute_hash_deterministic(self):
        h1 = _compute_hash("Some scam message")
        h2 = _compute_hash("Some scam message")
        assert h1 == h2

    def test_compute_hash_is_sha256(self):
        h = _compute_hash("Test content")
        assert re.fullmatch(r"[0-9a-f]{64}", h)

    def test_compute_hash_normalises_before_hash(self):
        """Same text with different whitespace → same hash."""
        h1 = _compute_hash("Hello  World")
        h2 = _compute_hash("hello world")
        assert h1 == h2


# ---------------------------------------------------------------------------
# DB: API key lookup
# ---------------------------------------------------------------------------

class TestApiKeyLookup:
    """lookup_api_key returns org_id if key exists, None otherwise."""

    @pytest.mark.asyncio
    async def test_valid_key_returns_org(self, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value={
            "org_id": "org-001",
            "name": "Police Tipline",
        })
        result = await lookup_api_key(mock_conn, "valid-api-key-123")
        assert result is not None
        assert result["org_id"] == "org-001"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await lookup_api_key(mock_conn, "bad-key")
        assert result is None

    def test_sql_uses_parameterised_query(self):
        """SQL must use $1, not f-string."""
        assert "$1" in SQL_LOOKUP_API_KEY
        assert "api_key" in SQL_LOOKUP_API_KEY.lower() or "api_keys" in SQL_LOOKUP_API_KEY.lower()


# ---------------------------------------------------------------------------
# DB: tipline source get-or-create
# ---------------------------------------------------------------------------

class TestTiplineSource:
    """Auto-create a 'tipline' source for the org if not exists."""

    @pytest.mark.asyncio
    async def test_existing_source_returned(self, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value={"id": "src-001", "credibility_score": 50.0})
        result = await get_or_create_tipline_source(mock_conn, "org-001")
        assert result["id"] == "src-001"

    @pytest.mark.asyncio
    async def test_creates_source_if_not_exists(self, mock_conn):
        # First call (lookup) returns None, second call (insert) returns new row
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                None,  # lookup
                {"id": "src-new", "credibility_score": 50.0},  # insert returning
            ]
        )
        result = await get_or_create_tipline_source(mock_conn, "org-001")
        assert result is not None
        assert mock_conn.fetchrow.call_count == 2


# ---------------------------------------------------------------------------
# DB: content insertion
# ---------------------------------------------------------------------------

class TestTiplineContentInsert:
    """insert_tipline_content creates content_item with ON CONFLICT dedup."""

    @pytest.mark.asyncio
    async def test_new_item_inserted(self, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value={"id": "ci-001"})
        result = await insert_tipline_content(
            mock_conn,
            content_item_id="ci-001",
            topic_id="topic-001",
            source_id="src-001",
            raw_text="Scam call from +919876543210",
            content_hash="abc123",
            credibility_score=50.0,
            org_id="org-001",
            source_phone="+911234567890",
            forwarded_from="unknown",
        )
        assert result is not None
        assert result["id"] == "ci-001"

    @pytest.mark.asyncio
    async def test_duplicate_returns_none(self, mock_conn):
        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await insert_tipline_content(
            mock_conn,
            content_item_id="ci-002",
            topic_id="topic-001",
            source_id="src-001",
            raw_text="Same content",
            content_hash="abc123",
            credibility_score=50.0,
            org_id="org-001",
        )
        assert result is None

    def test_sql_has_on_conflict(self):
        assert "ON CONFLICT" in SQL_INSERT_TIPLINE_CONTENT
        assert "content_hash" in SQL_INSERT_TIPLINE_CONTENT

    def test_sql_platform_is_tipline(self):
        """Platform='tipline' is set on the source row, not in content insert SQL.
        Content inherits platform via source_id FK. Verify source SQL has it."""
        assert "tipline" in SQL_GET_TIPLINE_SOURCE.lower()


# ---------------------------------------------------------------------------
# Route: full ingest flow (mocked deps)
# ---------------------------------------------------------------------------

class TestTiplineIngestRoute:
    """Integration-style unit tests for the ingest route handler."""

    @pytest.fixture
    def mock_deps(self):
        """Standard mocked dependencies for route handler."""
        conn = AsyncMock()
        arq_pool = AsyncMock()
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"x-api-key": "valid-key-001"}
        return conn, arq_pool, request

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self, mock_deps):
        """No X-Api-Key header → 401."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline
        from fastapi import HTTPException

        conn, arq_pool, request = mock_deps
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await ingest_tipline(
                body=TiplineIngestRequest(text="test", topic_id="t-001"),
                request=request,
                db=conn,
                arq_pool=arq_pool,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, mock_deps):
        """Invalid API key → 401."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline
        from fastapi import HTTPException

        conn, arq_pool, request = mock_deps
        request.headers = {"x-api-key": "bad-key"}

        with patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.lookup_api_key",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await ingest_tipline(
                    body=TiplineIngestRequest(text="test", topic_id="t-001"),
                    request=request,
                    db=conn,
                    arq_pool=arq_pool,
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_topic_not_found_returns_404(self, mock_deps):
        """Valid key but topic doesn't belong to org → 404."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline
        from fastapi import HTTPException

        conn, arq_pool, request = mock_deps
        request.headers = {"x-api-key": "valid-key"}

        with patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.lookup_api_key",
            new=AsyncMock(return_value={"org_id": "org-001", "name": "test"}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.verify_topic_org",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await ingest_tipline(
                    body=TiplineIngestRequest(text="scam msg", topic_id="bad-topic"),
                    request=request,
                    db=conn,
                    arq_pool=arq_pool,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_successful_ingest_returns_queued(self, mock_deps):
        """Happy path: valid key, valid topic → content created, job enqueued."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline

        conn, arq_pool, request = mock_deps
        request.headers = {"x-api-key": "valid-key"}

        with patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.lookup_api_key",
            new=AsyncMock(return_value={"org_id": "org-001", "name": "test"}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.verify_topic_org",
            new=AsyncMock(return_value=True),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.get_or_create_tipline_source",
            new=AsyncMock(return_value={"id": "src-001", "credibility_score": 50.0}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.insert_tipline_content",
            new=AsyncMock(return_value={"id": "ci-new-001"}),
        ):
            result = await ingest_tipline(
                body=TiplineIngestRequest(text="scam call +919876543210", topic_id="topic-001"),
                request=request,
                db=conn,
                arq_pool=arq_pool,
            )
            assert result.status == "queued"
            assert result.duplicate is False
            assert result.id is not None
            # Verify ARQ job was enqueued
            arq_pool.enqueue_job.assert_called_once()
            call_args = arq_pool.enqueue_job.call_args
            assert call_args[0][0] == "analyse_content"

    @pytest.mark.asyncio
    async def test_duplicate_content_not_enqueued(self, mock_deps):
        """Duplicate content → status=duplicate, no ARQ job."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline

        conn, arq_pool, request = mock_deps
        request.headers = {"x-api-key": "valid-key"}

        with patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.lookup_api_key",
            new=AsyncMock(return_value={"org_id": "org-001", "name": "test"}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.verify_topic_org",
            new=AsyncMock(return_value=True),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.get_or_create_tipline_source",
            new=AsyncMock(return_value={"id": "src-001", "credibility_score": 50.0}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.insert_tipline_content",
            new=AsyncMock(return_value=None),  # ON CONFLICT → None
        ):
            result = await ingest_tipline(
                body=TiplineIngestRequest(text="same scam msg", topic_id="topic-001"),
                request=request,
                db=conn,
                arq_pool=arq_pool,
            )
            assert result.status == "duplicate"
            assert result.duplicate is True
            # No ARQ job for duplicates
            arq_pool.enqueue_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_arq_failure_still_returns_success(self, mock_deps):
        """ARQ enqueue failure → still return success (content was inserted)."""
        from services.api.anveshak.api.routes.tipline import ingest_tipline

        conn, arq_pool, request = mock_deps
        request.headers = {"x-api-key": "valid-key"}
        arq_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis down"))

        with patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.lookup_api_key",
            new=AsyncMock(return_value={"org_id": "org-001", "name": "test"}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.verify_topic_org",
            new=AsyncMock(return_value=True),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.get_or_create_tipline_source",
            new=AsyncMock(return_value={"id": "src-001", "credibility_score": 50.0}),
        ), patch(
            "services.api.anveshak.api.routes.tipline.tipline_db.insert_tipline_content",
            new=AsyncMock(return_value={"id": "ci-new-002"}),
        ):
            result = await ingest_tipline(
                body=TiplineIngestRequest(text="important scam tip", topic_id="topic-001"),
                request=request,
                db=conn,
                arq_pool=arq_pool,
            )
            # Content was created — return success even though job enqueue failed
            assert result.status == "queued"
            assert result.id is not None


# ---------------------------------------------------------------------------
# Rate limiting: tipline-specific (100 req/min per API key)
# ---------------------------------------------------------------------------

class TestTiplineRateLimit:
    """Rate limit: 100 requests/minute per API key."""

    def test_rate_limit_path_in_middleware(self):
        """Tipline path should be rate-limited in the middleware."""
        from services.api.anveshak.api.middleware.rate_limit import (
            _TIPLINE_PATH,
            _TIPLINE_LIMIT,
        )
        assert _TIPLINE_PATH == "/api/v1/tipline/ingest"
        assert _TIPLINE_LIMIT == 100


# ---------------------------------------------------------------------------
# SQL safety checks
# ---------------------------------------------------------------------------

class TestSqlSafety:
    """All SQL uses parameterised queries — no f-strings."""

    def test_lookup_api_key_parameterised(self):
        assert "$1" in SQL_LOOKUP_API_KEY
        assert "{" not in SQL_LOOKUP_API_KEY

    def test_insert_content_parameterised(self):
        assert "$1" in SQL_INSERT_TIPLINE_CONTENT
        assert "{" not in SQL_INSERT_TIPLINE_CONTENT

    def test_get_source_parameterised(self):
        assert "$1" in SQL_GET_TIPLINE_SOURCE
        assert "{" not in SQL_GET_TIPLINE_SOURCE
