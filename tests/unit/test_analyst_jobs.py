"""Unit tests for analyse_content ARQ job (criteria 1.11-1.18).

pytest.mark.unit -- no external dependencies, no DB, no network.
All DB and ML functions are mocked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
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


def _make_db_row(
    content_item_id: str = "ci-1",
    clean_text: str = "India successfully tested its new Agni-V missile from Abdul Kalam Island.",
    topic_id: str = "topic-1",
    topic_name: str = "Defence Procurement",
    topic_keywords: list[str] | None = None,
    topic_relevance_threshold: float | None = None,
) -> dict:
    return {
        "id": content_item_id,
        "clean_text": clean_text,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "topic_keywords": topic_keywords or ["defence", "missile"],
        "topic_relevance_threshold": topic_relevance_threshold,
    }


def _build_ctx(pool: AsyncMock) -> dict:
    return {"db_pool": pool}


def _make_pool(fetchrow_rv=None) -> AsyncMock:
    """Create a mock asyncpg pool with acquire/transaction context managers."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_rv)
    conn.execute = AsyncMock()

    # conn.transaction() returns an async context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    # pool.acquire() returns async context manager yielding conn
    acq = AsyncMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=acq)
    return pool


# Module path prefix for patching
_MOD = "anveshak.analyst.jobs"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAnalyseContentHappyPath:
    """Full English pipeline -- all 9 params written to DB in correct order."""

    @pytest.mark.asyncio
    async def test_analyse_content_happy_path(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        fake_embedding = [0.1] * 384

        with (
            patch(f"{_MOD}.is_quality_content", return_value=True),
            patch(f"{_MOD}.detect_language", return_value="en"),
            patch(f"{_MOD}.needs_translation", return_value=False),
            patch(f"{_MOD}.is_model_loaded", return_value=True),
            patch(f"{_MOD}.parse_entities", return_value=[
                _FakeEntity("ORG", "DRDO", 1.0, "en"),
            ]),
            patch(f"{_MOD}.encode_text", return_value=fake_embedding),
            patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_MOD}.compute_topic_relevance", return_value=0.78),
            patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.5, 0.6, 0.1, 0.3)),
            patch(f"{_MOD}.extract_keywords", return_value=[_FakeKeyword("missile", 0.01)]),
            patch(f"{_MOD}.compute_entity_minhash", return_value=[123, 456]),
            patch(f"{_MOD}.analyst_nlp_jobs_total") as mock_counter,
            patch(f"{_MOD}.analyst_nlp_duration_seconds"),
            patch(f"{_MOD}.analyst_relevance_score"),
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # Verify SQL_UPDATE_CONTENT_NLP was called
        conn = pool.acquire().__aenter__.return_value
        update_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "UPDATE content_items" in str(c.args[0])
        ]
        assert len(update_calls) >= 1, "SQL_UPDATE_CONTENT_NLP not called"

        args = update_calls[0].args
        # $1 = embedding_str (string starting with '[')
        assert args[1].startswith("["), f"$1 should be embedding string, got {args[1]}"
        # $2 = language
        assert args[2] == "en", f"$2 should be 'en', got {args[2]}"
        # $3 = translated_text (None for English)
        assert args[3] is None, f"$3 should be None for English, got {args[3]}"
        # $4 = translation_model (None for English)
        assert args[4] is None, f"$4 should be None for English, got {args[4]}"
        # $5 = labels_json (valid JSON with sentiment + keywords)
        labels = json.loads(args[5])
        assert "sentiment" in labels
        assert "keywords" in labels
        # $6 = now (datetime)
        assert isinstance(args[6], datetime)
        # $7 = relevance_score
        assert args[7] == 0.78
        # $8 = content_item_id
        assert args[8] == "ci-1"
        # $9 = minhash
        assert args[9] == [123, 456]


@pytest.mark.unit
class TestAnalyseContentNotFound:
    """Content not in DB -- return early, increment failed counter."""

    @pytest.mark.asyncio
    async def test_analyse_content_not_found(self):
        pool = _make_pool(fetchrow_rv=None)
        ctx = _build_ctx(pool)

        with (
            patch(f"{_MOD}.analyst_nlp_jobs_total") as mock_counter,
            patch(f"{_MOD}.is_quality_content") as mock_quality,
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "nonexistent-id")

        # Quality gate should never be reached
        mock_quality.assert_not_called()
        # Failed counter should be incremented
        mock_counter.labels.assert_called_with(status="failed")


@pytest.mark.unit
class TestAnalyseContentQualityGate:
    """Low-quality content -- skip entire NLP pipeline."""

    @pytest.mark.asyncio
    async def test_analyse_content_quality_gate_skips(self):
        row = _make_db_row(clean_text="nav menu links")
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        with (
            patch(f"{_MOD}.is_quality_content", return_value=False),
            patch(f"{_MOD}.detect_language") as mock_lang,
            patch(f"{_MOD}.encode_text") as mock_embed,
            patch(f"{_MOD}.analyst_nlp_jobs_total") as mock_counter,
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # Pipeline functions should never be called
        mock_lang.assert_not_called()
        mock_embed.assert_not_called()
        # Skipped counter incremented
        mock_counter.labels.assert_called_with(status="skipped")


@pytest.mark.unit
class TestAnalyseContentTranslationFallback:
    """translate_to_english returns None -- work_text falls back to clean_text."""

    @pytest.mark.asyncio
    async def test_analyse_content_translation_fallback(self):
        original_text = "This is the original Hindi-looking text for testing."
        row = _make_db_row(clean_text=original_text)
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        with (
            patch(f"{_MOD}.is_quality_content", return_value=True),
            patch(f"{_MOD}.detect_language", return_value="hi"),
            patch(f"{_MOD}.needs_translation", return_value=True),
            patch(f"{_MOD}.translate_to_english", return_value=None),  # translation fails
            patch(f"{_MOD}.settings") as mock_settings,
            patch(f"{_MOD}.is_model_loaded", return_value=True),
            patch(f"{_MOD}.parse_entities", return_value=[]) as mock_ner,
            patch(f"{_MOD}.encode_text", return_value=[0.1] * 384) as mock_encode,
            patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_MOD}.compute_topic_relevance", return_value=0.5),
            patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.0, 0.0, 0.0, 1.0)),
            patch(f"{_MOD}.extract_keywords", return_value=[]),
            patch(f"{_MOD}.compute_entity_minhash", return_value=None),
            patch(f"{_MOD}.analyst_nlp_jobs_total"),
            patch(f"{_MOD}.analyst_nlp_duration_seconds"),
            patch(f"{_MOD}.analyst_relevance_score"),
        ):
            mock_settings.translation_enabled = True
            mock_settings.minhash_num_perm = 128
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # NER and embedding should receive the original text (fallback)
        mock_ner.assert_called_once()
        ner_text = mock_ner.call_args.args[0]
        assert ner_text == original_text, (
            f"When translation fails, NER should run on original text, got: {ner_text!r}"
        )
        mock_encode.assert_called_once_with(original_text)


@pytest.mark.unit
class TestAnalyseContentTranslationSuccess:
    """Non-English content translated -- NER runs on English model with translated text."""

    @pytest.mark.asyncio
    async def test_analyse_content_translation_success(self):
        original_text = "Inde a teste son missile Agni."
        translated = "India tested its Agni missile."
        row = _make_db_row(clean_text=original_text)
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        with (
            patch(f"{_MOD}.is_quality_content", return_value=True),
            patch(f"{_MOD}.detect_language", return_value="fr"),
            patch(f"{_MOD}.needs_translation", return_value=True),
            patch(f"{_MOD}.translate_to_english", return_value=translated),
            patch(f"{_MOD}.settings") as mock_settings,
            patch(f"{_MOD}.is_model_loaded", return_value=True),
            patch(f"{_MOD}.parse_entities", return_value=[]) as mock_ner,
            patch(f"{_MOD}.encode_text", return_value=[0.1] * 384) as mock_encode,
            patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_MOD}.compute_topic_relevance", return_value=0.6),
            patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.0, 0.0, 0.0, 1.0)),
            patch(f"{_MOD}.extract_keywords", return_value=[]),
            patch(f"{_MOD}.compute_entity_minhash", return_value=None),
            patch(f"{_MOD}.analyst_nlp_jobs_total"),
            patch(f"{_MOD}.analyst_nlp_duration_seconds"),
            patch(f"{_MOD}.analyst_relevance_score"),
        ):
            mock_settings.translation_enabled = True
            mock_settings.translation_model = "facebook/nllb-200-distilled-600M"
            mock_settings.minhash_num_perm = 128
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # NER must use English model ("en") with translated text
        mock_ner.assert_called_once_with(translated, "en")
        # Embedding must use translated text
        mock_encode.assert_called_once_with(translated)

        # DB write: $3 = translated_text, $4 = translation_model
        conn = pool.acquire().__aenter__.return_value
        update_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "UPDATE content_items" in str(c.args[0])
        ]
        assert len(update_calls) >= 1
        args = update_calls[0].args
        assert args[3] == translated, f"$3 should be translated text, got {args[3]}"
        assert args[4] == "facebook/nllb-200-distilled-600M"


@pytest.mark.unit
class TestAnalyseContentNERUnavailable:
    """spaCy model not loaded -- entities list is empty but pipeline continues."""

    @pytest.mark.asyncio
    async def test_analyse_content_ner_unavailable(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        with (
            patch(f"{_MOD}.is_quality_content", return_value=True),
            patch(f"{_MOD}.detect_language", return_value="en"),
            patch(f"{_MOD}.needs_translation", return_value=False),
            patch(f"{_MOD}.is_model_loaded", return_value=False),  # NER unavailable
            patch(f"{_MOD}.parse_entities") as mock_ner,
            patch(f"{_MOD}.encode_text", return_value=[0.1] * 384),
            patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_MOD}.compute_topic_relevance", return_value=0.5),
            patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.0, 0.0, 0.0, 1.0)),
            patch(f"{_MOD}.extract_keywords", return_value=[]),
            patch(f"{_MOD}.compute_entity_minhash", return_value=None) as mock_minhash,
            patch(f"{_MOD}.analyst_nlp_jobs_total"),
            patch(f"{_MOD}.analyst_nlp_duration_seconds"),
            patch(f"{_MOD}.analyst_relevance_score"),
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        # parse_entities must NOT be called when model is not loaded
        mock_ner.assert_not_called()
        # Pipeline should still complete (embedding, DB write happen)
        conn = pool.acquire().__aenter__.return_value
        assert conn.execute.call_count >= 1, "DB write should still happen even without NER"
        # Minhash called with empty entity list
        mock_minhash.assert_called_once()
        assert mock_minhash.call_args.args[0] == []


@pytest.mark.unit
class TestAnalyseContentSQLParamOrder:
    """Verify the 9 positional params to SQL_UPDATE_CONTENT_NLP are in the correct order.

    This test catches the real bug where swapping $8 and $9 would silently write
    content_item_id into entity_minhash and vice versa.
    """

    @pytest.mark.asyncio
    async def test_analyse_content_sql_param_order(self):
        row = _make_db_row()
        pool = _make_pool(fetchrow_rv=row)
        ctx = _build_ctx(pool)

        sentinel_minhash = [999, 888, 777]

        with (
            patch(f"{_MOD}.is_quality_content", return_value=True),
            patch(f"{_MOD}.detect_language", return_value="en"),
            patch(f"{_MOD}.needs_translation", return_value=False),
            patch(f"{_MOD}.is_model_loaded", return_value=True),
            patch(f"{_MOD}.parse_entities", return_value=[
                _FakeEntity("PERSON", "Narendra Modi", 1.0, "en"),
            ]),
            patch(f"{_MOD}.encode_text", return_value=[0.5] * 384),
            patch(f"{_MOD}.build_topic_query_embedding", return_value=[0.2] * 384),
            patch(f"{_MOD}.compute_topic_relevance", return_value=0.91),
            patch(f"{_MOD}.analyse_sentiment", return_value=_FakeSentiment(0.3, 0.4, 0.2, 0.4)),
            patch(f"{_MOD}.extract_keywords", return_value=[_FakeKeyword("Modi", 0.02)]),
            patch(f"{_MOD}.compute_entity_minhash", return_value=sentinel_minhash),
            patch(f"{_MOD}.analyst_nlp_jobs_total"),
            patch(f"{_MOD}.analyst_nlp_duration_seconds"),
            patch(f"{_MOD}.analyst_relevance_score"),
        ):
            from anveshak.analyst.jobs import analyse_content
            await analyse_content(ctx, "ci-1")

        conn = pool.acquire().__aenter__.return_value
        update_calls = [
            c for c in conn.execute.call_args_list
            if len(c.args) > 1 and "UPDATE content_items" in str(c.args[0])
        ]
        assert len(update_calls) >= 1
        args = update_calls[0].args
        # Positional param verification:
        # args[0] = SQL string
        # args[1] = $1 = embedding_str
        assert isinstance(args[1], str) and args[1].startswith("["), "$1 must be embedding string"
        # args[2] = $2 = language
        assert args[2] == "en", "$2 must be language"
        # args[3] = $3 = translated_text
        assert args[3] is None, "$3 must be translated_text (None for English)"
        # args[4] = $4 = translation_model
        assert args[4] is None, "$4 must be translation_model (None for English)"
        # args[5] = $5 = labels_json
        assert isinstance(args[5], str), "$5 must be labels JSON string"
        parsed_labels = json.loads(args[5])
        assert "sentiment" in parsed_labels, "$5 labels must contain sentiment"
        # args[6] = $6 = now
        assert isinstance(args[6], datetime), "$6 must be datetime"
        # args[7] = $7 = relevance_score
        assert isinstance(args[7], float), "$7 must be relevance_score float"
        assert args[7] == 0.91
        # args[8] = $8 = content_item_id -- THIS IS THE BUG-CATCHING ASSERTION
        assert args[8] == "ci-1", f"$8 must be content_item_id, got {args[8]}"
        # args[9] = $9 = minhash -- THIS IS THE BUG-CATCHING ASSERTION
        assert args[9] == sentinel_minhash, f"$9 must be minhash, got {args[9]}"
