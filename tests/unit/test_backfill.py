"""Unit tests for historical topic backfill (Phase 2, criterion 2.9).

pytest.mark.unit — no external dependencies, no DB, no network.
Tests cover the pure helper and the similarity filtering logic with a mocked pool.
"""
from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from anveshak.analyst.backfill import _build_query_text, backfill_topic


# ---------------------------------------------------------------------------
# _build_query_text — pure function
# ---------------------------------------------------------------------------

class TestBuildQueryText:
    def test_combines_name_and_keywords(self):
        text = _build_query_text("IAF Procurement", ["rafale", "fighter jet", "defence"])
        assert "IAF Procurement" in text
        assert "rafale" in text
        assert "fighter jet" in text
        assert "defence" in text

    def test_empty_keywords(self):
        text = _build_query_text("Topic Name", [])
        assert text == "Topic Name"

    def test_single_keyword(self):
        text = _build_query_text("China Border", ["LAC"])
        assert "China Border" in text
        assert "LAC" in text

    def test_result_is_space_separated(self):
        text = _build_query_text("A", ["B", "C"])
        assert text == "A B C"


# ---------------------------------------------------------------------------
# backfill_topic — async, mocked pool
# ---------------------------------------------------------------------------

class TestBackfillTopic:
    """Criterion 2.9: pgvector cosine search assigns relevant items to topic."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_topic_not_found(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        result = await backfill_topic("nonexistent-topic", pool)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_similar_items(self):
        topic_row = {"name": "IAF News", "keywords": ["rafale", "IAF"]}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=topic_row)
        conn.fetch = AsyncMock(return_value=[])
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        dummy_vec = np.zeros(384, dtype=np.float32)
        with patch(
            "anveshak.analyst.backfill.encode_text",
            return_value=dummy_vec,
        ):
            result = await backfill_topic("topic-1", pool)

        assert result == 0

    @pytest.mark.asyncio
    async def test_inserts_similar_items(self):
        """Matching items are inserted into topic_content_items."""
        topic_row = {"name": "Border Tensions", "keywords": ["LAC", "China"]}
        similar_rows = [
            {"id": "item-1", "similarity_score": 0.92},
            {"id": "item-2", "similarity_score": 0.88},
            {"id": "item-3", "similarity_score": 0.91},
        ]

        executed_sqls: list[tuple] = []

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=topic_row)
        conn.fetch = AsyncMock(return_value=similar_rows)

        async def mock_execute(sql, *args):
            executed_sqls.append((sql, args))

        conn.execute = mock_execute

        # Transaction context manager
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        dummy_vec = np.ones(384, dtype=np.float32) * 0.5
        with patch(
            "anveshak.analyst.backfill.encode_text",
            return_value=dummy_vec,
        ):
            result = await backfill_topic("topic-1", pool)

        assert result == 3
        # Each item should have triggered an INSERT
        assert len(executed_sqls) == 3

    @pytest.mark.asyncio
    async def test_embeds_topic_name_and_keywords(self):
        """encode_text is called with name + keywords combined."""
        topic_row = {"name": "Rafale Deal", "keywords": ["Rafale", "IAF", "procurement"]}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=topic_row)
        conn.fetch = AsyncMock(return_value=[])
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        dummy_vec = np.zeros(384, dtype=np.float32)
        with patch(
            "anveshak.analyst.backfill.encode_text",
            return_value=dummy_vec,
        ) as mock_encode:
            await backfill_topic("topic-1", pool)

        mock_encode.assert_called_once()
        call_text: str = mock_encode.call_args.args[0]
        assert "Rafale Deal" in call_text
        assert "Rafale" in call_text
        assert "IAF" in call_text
        assert "procurement" in call_text

    @pytest.mark.asyncio
    async def test_similarity_threshold_passed_to_query(self):
        """The configurable threshold is forwarded to the pgvector query."""
        from anveshak.analyst import backfill as backfill_module

        topic_row = {"name": "Test", "keywords": ["kw"]}
        fetch_calls: list = []

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=topic_row)

        async def capture_fetch(sql, *args):
            fetch_calls.append(args)
            return []

        conn.fetch = capture_fetch
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)

        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=conn)

        dummy_vec = np.zeros(384, dtype=np.float32)
        with patch(
            "anveshak.analyst.backfill.encode_text",
            return_value=dummy_vec,
        ):
            await backfill_topic("topic-1", pool)

        assert fetch_calls, "fetch should have been called for similarity query"
        # Third positional arg to SQL_SIMILAR_ITEMS is threshold ($3)
        query_args = fetch_calls[0]
        threshold_value = query_args[2]  # $1=topic_id, $2=embedding, $3=threshold
        assert threshold_value == backfill_module.settings.backfill_similarity_threshold
