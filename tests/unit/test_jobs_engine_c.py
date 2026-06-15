"""Unit tests for Engine C wiring in analyse_content ARQ job.

Verifies that analyse_content:
  1. Calls extract_identifiers() on work_text after NER
  2. Inserts identifier matches as extracted_entities rows
  3. Calls match_templates() with content keywords + identifier types
  4. Stores template match in labels JSONB (scam_template, template_confidence, etc.)
  5. Fetches platform from source for extract_identifiers context

pytest.mark.unit -- no external dependencies, no DB, no network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers (matching test_analyst_jobs.py patterns)
# ---------------------------------------------------------------------------

@dataclass
class _FakeEntity:
    entity_type: str
    entity_text: str
    confidence: float
    language: str


@dataclass
class _FakeSentiment:
    compound: float
    positive: float
    negative: float
    neutral: float


@dataclass
class _FakeKeyword:
    keyword: str
    score: float


@dataclass
class _FakeIdentifierMatch:
    identifier_type: str
    raw_value: str
    normalized_value: str
    confidence: float


@dataclass
class _FakeTemplateMatch:
    template_name: str
    template_display: str
    confidence: float
    matched_keywords: list[str]
    matched_identifier_types: list[str]
    legal_sections: list[str]
    severity: str


def _make_db_row(
    content_item_id: str = "ci-1",
    clean_text: str = "Call +91 9876543210 for guaranteed returns. Send money to fraud@ybl",
    topic_id: str = "topic-1",
    topic_name: str = "Cyber Fraud Monitoring",
    topic_keywords: list[str] | None = None,
    topic_relevance_threshold: float | None = None,
    platform: str = "telegram",
) -> dict:
    return {
        "id": content_item_id,
        "clean_text": clean_text,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "topic_keywords": topic_keywords or ["fraud", "scam", "investment"],
        "topic_relevance_threshold": topic_relevance_threshold,
        "platform": platform,
    }


def _build_ctx(pool: AsyncMock) -> dict:
    return {"db_pool": pool}


def _make_pool(fetchrow_rv=None) -> AsyncMock:
    """Create a mock asyncpg pool with acquire/transaction context managers."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_rv)
    conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    acq = AsyncMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=acq)
    return pool


_MOD = "anveshak.analyst.jobs"


# ---------------------------------------------------------------------------
# Common patch context for Engine C tests
# ---------------------------------------------------------------------------

def _base_patches(
    fake_embedding=None,
    fake_entities=None,
    fake_identifiers=None,
    fake_template_match=None,
    fake_keywords=None,
):
    """Return a list of patch context managers for the full NLP + Engine C pipeline."""
    if fake_embedding is None:
        fake_embedding = [0.1] * 384
    if fake_entities is None:
        fake_entities = [_FakeEntity("ORG", "DRDO", 1.0, "en")]
    if fake_identifiers is None:
        fake_identifiers = [
            _FakeIdentifierMatch("PHONE_IN", "+91 9876543210", "9876543210", 0.95),
            _FakeIdentifierMatch("UPI", "fraud@ybl", "fraud@ybl", 1.0),
        ]
    if fake_keywords is None:
        fake_keywords = [_FakeKeyword("guaranteed", 0.01), _FakeKeyword("returns", 0.02)]

    return [
        patch(f"{_MOD}.is_quality_content", return_value=(True, "passed")),
        patch(f"{_MOD}.detect_language", return_value="en"),
        patch(f"{_MOD}.needs_translation", return_value=False),
        patch(f"{_MOD}.is_model_loaded", return_value=True),
        patch(f"{_MOD}.parse_entities", return_value=fake_entities),
        patch(f"{_MOD}.encode_text", return_value=fake_embedding),
        patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
        patch(f"{_MOD}.compute_topic_relevance", return_value=0.78),
        patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.5, 0.6, 0.1, 0.3)),
        patch(f"{_MOD}.extract_keywords", return_value=fake_keywords),
        patch(f"{_MOD}.compute_entity_minhash", return_value=[123, 456]),
        patch(f"{_MOD}.extract_identifiers", return_value=fake_identifiers),
        patch(f"{_MOD}.match_templates", return_value=fake_template_match),
        patch(f"{_MOD}.analyst_nlp_jobs_total"),
        patch(f"{_MOD}.analyst_nlp_duration_seconds"),
        patch(f"{_MOD}.analyst_relevance_score"),
        patch(f"{_MOD}.analyst_embedding_completed_total"),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnalyseContentCallsExtractIdentifiers:
    """analyse_content must call extract_identifiers(work_text, platform) after NER."""

    @pytest.mark.asyncio
    async def test_extract_identifiers_called_with_work_text(self):
        row = _make_db_row(platform="telegram")
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        patches = _base_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9], \
             patches[10], patches[11] as mock_extract, patches[12], \
             patches[13], patches[14], patches[15], patches[16]:

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # extract_identifiers must be called with work_text and platform
        mock_extract.assert_called_once()
        call_args = mock_extract.call_args
        assert call_args.args[0] == row["clean_text"], \
            "extract_identifiers should receive work_text"
        assert call_args.args[1] == "telegram", \
            "extract_identifiers should receive platform from source"


@pytest.mark.unit
class TestAnalyseContentInsertsIdentifierEntities:
    """Identifier matches must be inserted as extracted_entities rows."""

    @pytest.mark.asyncio
    async def test_identifier_entities_inserted(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        fake_ids = [
            _FakeIdentifierMatch("PHONE_IN", "+91 9876543210", "9876543210", 0.95),
            _FakeIdentifierMatch("UPI", "fraud@ybl", "fraud@ybl", 1.0),
        ]

        patches = _base_patches(fake_identifiers=fake_ids)
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9], \
             patches[10], patches[11], patches[12], \
             patches[13], patches[14], patches[15], patches[16]:

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        conn = pool.acquire().__aenter__.return_value
        # Filter INSERT INTO extracted_entities calls
        insert_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "INSERT INTO extracted_entities" in str(c.args[0])
        ]

        # Should have spaCy entity (1) + identifier entities (2) = 3 inserts
        assert len(insert_calls) >= 3, (
            f"Expected at least 3 extracted_entities inserts "
            f"(1 spaCy + 2 identifiers), got {len(insert_calls)}"
        )

        # Check identifier entity types are in the inserts
        inserted_types = [c.args[3] for c in insert_calls]  # $3 = entity_type
        assert "PHONE_IN" in inserted_types, "PHONE_IN identifier not inserted"
        assert "UPI" in inserted_types, "UPI identifier not inserted"


@pytest.mark.unit
class TestAnalyseContentCallsMatchTemplates:
    """analyse_content must call match_templates with keywords + identifier types."""

    @pytest.mark.asyncio
    async def test_match_templates_called(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        patches = _base_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9], \
             patches[10], patches[11], patches[12] as mock_match, \
             patches[13], patches[14], patches[15], patches[16]:

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # match_templates must be called
        mock_match.assert_called_once()
        call_args = mock_match.call_args

        # First arg: content_keywords (set of strings)
        content_kw = call_args.args[0]
        assert isinstance(content_kw, set), "content_keywords should be a set"

        # Second arg: identifier_types (set of strings)
        id_types = call_args.args[1]
        assert isinstance(id_types, set), "identifier_types should be a set"
        assert "PHONE_IN" in id_types
        assert "UPI" in id_types


@pytest.mark.unit
class TestAnalyseContentTemplateMatchInLabels:
    """When template matches, labels JSONB must contain template data."""

    @pytest.mark.asyncio
    async def test_template_match_stored_in_labels(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        fake_match = _FakeTemplateMatch(
            template_name="investment_fraud",
            template_display="Investment Fraud",
            confidence=0.82,
            matched_keywords=["guaranteed", "returns"],
            matched_identifier_types=["PHONE_IN", "UPI"],
            legal_sections=["SEBI (PFUTP) Regulations", "IPC 420"],
            severity="CRITICAL",
        )

        patches = _base_patches(fake_template_match=fake_match)
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9], \
             patches[10], patches[11], patches[12], \
             patches[13], patches[14], patches[15], patches[16]:

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        conn = pool.acquire().__aenter__.return_value
        update_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "UPDATE content_items" in str(c.args[0])
        ]
        assert len(update_calls) >= 1, "SQL_UPDATE_CONTENT_NLP not called"

        # $5 = labels_json
        labels = json.loads(update_calls[0].args[5])
        assert labels.get("scam_template") == "investment_fraud", \
            f"labels must contain scam_template, got {labels}"
        assert labels.get("template_confidence") == 0.82, \
            f"labels must contain template_confidence, got {labels}"
        assert "matched_keywords" in labels, \
            "labels must contain matched_keywords"
        assert "extracted_identifiers" in labels, \
            "labels must contain extracted_identifiers dict"


@pytest.mark.unit
class TestAnalyseContentNoTemplateMatch:
    """When no template matches, labels should NOT contain scam_template."""

    @pytest.mark.asyncio
    async def test_no_template_match_no_labels(self):
        row = _make_db_row(
            clean_text="India successfully tested its new Agni-V missile.",
        )
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        patches = _base_patches(
            fake_identifiers=[],
            fake_template_match=None,
            fake_keywords=[_FakeKeyword("missile", 0.01)],
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
             patches[5], patches[6], patches[7], patches[8], patches[9], \
             patches[10], patches[11], patches[12], \
             patches[13], patches[14], patches[15], patches[16]:

            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        conn = pool.acquire().__aenter__.return_value
        update_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "UPDATE content_items" in str(c.args[0])
        ]
        assert len(update_calls) >= 1

        labels = json.loads(update_calls[0].args[5])
        assert "scam_template" not in labels, \
            "labels should NOT contain scam_template when no match"


@pytest.mark.unit
class TestAnalyseContentFetchesPlatform:
    """SQL_GET_CONTENT must fetch platform from sources table."""

    def test_sql_get_content_includes_platform(self):
        from anveshak.analyst.jobs import SQL_GET_CONTENT
        sql_lower = SQL_GET_CONTENT.lower()
        assert "platform" in sql_lower, \
            "SQL_GET_CONTENT must SELECT platform (from sources table)"
        assert "sources" in sql_lower or "source" in sql_lower, \
            "SQL_GET_CONTENT must JOIN sources table to get platform"
