"""Unit tests for vision DB functions — topic_id linking on ad-hoc uploads.

Tests:
  - get_or_create_stub_content_item passes topic_id to SQL
  - get_or_create_stub_content_item works without topic_id (backward compat)
  - ON CONFLICT path returns existing id and still links to topic
  - topic_content_items join table insert when topic_id provided
  - No join table insert when topic_id is None
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class TestGetOrCreateStubContentItem:
    @pytest.mark.asyncio
    async def test_creates_stub_with_topic_id(self, mock_conn: AsyncMock) -> None:
        """When topic_id provided, it's passed as $5 to INSERT."""
        mock_conn.fetchrow = AsyncMock(return_value={"id": "ci-new"})

        from services.api.anveshak.api.db.vision import get_or_create_stub_content_item

        result = await get_or_create_stub_content_item(
            mock_conn,
            "abc123hash",
            "photo.jpg",
            topic_id="topic-42",
        )

        assert result == "ci-new"
        # Verify INSERT was called with positional args: (SQL, id, source, text, hash, topic_id)
        insert_call = mock_conn.fetchrow.call_args_list[0]
        args = insert_call[0]
        assert args[5] == "topic-42"  # $5 = topic_id (index 5 after SQL string)

    @pytest.mark.asyncio
    async def test_creates_stub_without_topic_id(self, mock_conn: AsyncMock) -> None:
        """Without topic_id, $5 is None (backward compat). No join table insert."""
        mock_conn.fetchrow = AsyncMock(return_value={"id": "ci-new"})

        from services.api.anveshak.api.db.vision import get_or_create_stub_content_item

        result = await get_or_create_stub_content_item(
            mock_conn,
            "abc123hash",
            "photo.jpg",
        )

        assert result == "ci-new"
        insert_call = mock_conn.fetchrow.call_args_list[0]
        args = insert_call[0]
        assert args[5] is None  # $5 = topic_id defaults to None
        # No topic_content_items insert when topic_id is None
        # execute called once for manual source upsert only
        assert mock_conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_on_conflict_returns_existing_and_links_topic(self, mock_conn: AsyncMock) -> None:
        """ON CONFLICT (content_hash) → fetch existing row, still link to topic."""
        # First fetchrow (INSERT) returns None (conflict)
        # Second fetchrow (SELECT) returns existing
        mock_conn.fetchrow = AsyncMock(
            side_effect=[None, {"id": "ci-existing"}],
        )

        from services.api.anveshak.api.db.vision import get_or_create_stub_content_item

        result = await get_or_create_stub_content_item(
            mock_conn,
            "abc123hash",
            "photo.jpg",
            topic_id="topic-42",
        )

        assert result == "ci-existing"
        assert mock_conn.fetchrow.call_count == 2
        # Should still insert into topic_content_items even on conflict
        execute_calls = mock_conn.execute.call_args_list
        # Last execute call should be topic_content_items upsert
        last_execute = execute_calls[-1]
        assert "topic-42" in last_execute[0]
        assert "ci-existing" in last_execute[0]

    @pytest.mark.asyncio
    async def test_topic_content_items_upsert_on_new_insert(self, mock_conn: AsyncMock) -> None:
        """New content_item with topic_id → join table insert."""
        mock_conn.fetchrow = AsyncMock(return_value={"id": "ci-new"})

        from services.api.anveshak.api.db.vision import get_or_create_stub_content_item

        await get_or_create_stub_content_item(
            mock_conn,
            "abc123hash",
            "photo.jpg",
            topic_id="topic-99",
        )

        # execute called twice: manual source upsert + topic_content_items upsert
        assert mock_conn.execute.call_count == 2
        last_execute = mock_conn.execute.call_args_list[-1]
        assert "topic-99" in last_execute[0]
        assert "ci-new" in last_execute[0]
