"""Content feed date filter on publication time, applied server side - issue #49.

Capture Time is when we saw it, Publication Time is when it happened. An
analyst filtering the evidence feed to a historic week means the latter, so
the filter reads COALESCE(published_at, captured_at). It lives in the query
rather than in the page already fetched, otherwise it filters what has been
loaded instead of the topic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from anveshak.api.db.topics import _DEFAULT_RELEVANCE_THRESHOLD, get_topic_content
from anveshak.api.routes import topics as topics_route
from fastapi import HTTPException

pytestmark = pytest.mark.unit

TOPIC_ID = "topic-049"
PUBLICATION_TIME_EXPR = "COALESCE(ci.published_at, ci.captured_at)"


async def _fetch_call(mock_conn: AsyncMock, **kwargs) -> tuple[str, tuple]:
    """Run the repository function and return the (sql, params) it issued."""
    mock_conn.fetch = AsyncMock(return_value=[])
    await get_topic_content(
        conn=mock_conn,
        topic_id=TOPIC_ID,
        limit=50,
        offset=0,
        has_embedding=None,
        platform=None,
        **kwargs,
    )
    call_args = mock_conn.fetch.call_args
    return call_args[0][0], call_args[0][1:]


class TestRepositoryFiltersOnPublicationTime:
    async def test_no_dates_adds_no_bound(self, mock_conn: AsyncMock) -> None:
        sql, params = await _fetch_call(mock_conn)

        assert params == (TOPIC_ID, 50, 0, _DEFAULT_RELEVANCE_THRESHOLD)
        assert PUBLICATION_TIME_EXPR not in sql

    async def test_date_from_binds_a_lower_bound(self, mock_conn: AsyncMock) -> None:
        since = datetime(2026, 5, 1, tzinfo=UTC)
        sql, params = await _fetch_call(mock_conn, date_from=since)

        assert params[-1] == since
        assert f"{PUBLICATION_TIME_EXPR} >= $5" in sql

    async def test_date_to_binds_an_inclusive_upper_bound(self, mock_conn: AsyncMock) -> None:
        until = datetime(2026, 5, 7, 23, 59, 59, 999999, tzinfo=UTC)
        sql, params = await _fetch_call(mock_conn, date_to=until)

        assert params[-1] == until
        assert f"{PUBLICATION_TIME_EXPR} <= $5" in sql

    async def test_both_bounds_bind_in_order(self, mock_conn: AsyncMock) -> None:
        since = datetime(2026, 5, 1, tzinfo=UTC)
        until = datetime(2026, 5, 7, 23, 59, 59, 999999, tzinfo=UTC)
        sql, params = await _fetch_call(mock_conn, date_from=since, date_to=until)

        assert params == (TOPIC_ID, 50, 0, _DEFAULT_RELEVANCE_THRESHOLD, since, until)
        assert f"{PUBLICATION_TIME_EXPR} >= $5" in sql
        assert f"{PUBLICATION_TIME_EXPR} <= $6" in sql

    async def test_bound_applies_to_both_content_paths(self, mock_conn: AsyncMock) -> None:
        """Direct items and topic_content_items are UNIONed, so both need the filter."""
        sql, _ = await _fetch_call(mock_conn, date_from=datetime(2026, 5, 1, tzinfo=UTC))

        assert sql.count(f"{PUBLICATION_TIME_EXPR} >= $5") == 2

    async def test_composes_with_pagination(self, mock_conn: AsyncMock) -> None:
        """Filtering in the query means LIMIT/OFFSET apply to the filtered set."""
        sql, params = await _fetch_call(
            mock_conn, date_from=datetime(2026, 5, 1, tzinfo=UTC), date_to=None
        )

        assert "LIMIT $2 OFFSET $3" in sql
        assert params[1] == 50
        assert params[2] == 0

    async def test_composes_with_platform_filter(self, mock_conn: AsyncMock) -> None:
        """Platform takes $4, so the bounds shift after the relevance threshold."""
        mock_conn.fetch = AsyncMock(return_value=[])
        since = datetime(2026, 5, 1, tzinfo=UTC)

        await get_topic_content(
            conn=mock_conn,
            topic_id=TOPIC_ID,
            limit=10,
            offset=0,
            has_embedding=None,
            platform="telegram",
            date_from=since,
        )

        sql = mock_conn.fetch.call_args[0][0]
        params = mock_conn.fetch.call_args[0][1:]
        assert params == (TOPIC_ID, 10, 0, "telegram", _DEFAULT_RELEVANCE_THRESHOLD, since)
        assert f"{PUBLICATION_TIME_EXPR} >= $6" in sql


class TestRouteParsesBoundaries:
    """The route accepts a bare date or a full instant and anchors both in UTC."""

    async def _call(self, monkeypatch, **kwargs) -> dict:
        captured: dict = {}

        async def fake_get_topic_content(conn, topic_id, limit, offset, *args, **kw):
            captured.update(kw)
            return []

        async def fake_verify(conn, topic_id, user):
            return None

        async def fake_get_topic(conn, topic_id):
            return {"topic_relevance_threshold": None}

        monkeypatch.setattr(topics_route.topics_db, "get_topic_content", fake_get_topic_content)
        monkeypatch.setattr(topics_route.topics_db, "verify_topic_access", fake_verify)
        monkeypatch.setattr(topics_route.topics_db, "get_topic", fake_get_topic)

        await topics_route.get_topic_content(
            topic_id=TOPIC_ID,
            db=AsyncMock(),
            user={"role": "analyst", "org_id": "org-1"},
            **kwargs,
        )
        return captured

    async def test_bare_date_from_anchors_at_start_of_day_utc(self, monkeypatch) -> None:
        captured = await self._call(monkeypatch, date_from="2026-05-01")

        assert captured["date_from"] == datetime(2026, 5, 1, 0, 0, tzinfo=UTC)

    async def test_bare_date_to_covers_the_whole_day(self, monkeypatch) -> None:
        """A picked end date includes everything published that day."""
        captured = await self._call(monkeypatch, date_to="2026-05-07")

        assert captured["date_to"] == datetime(2026, 5, 7, 23, 59, 59, 999999, tzinfo=UTC)

    async def test_full_instant_is_preserved(self, monkeypatch) -> None:
        captured = await self._call(monkeypatch, date_from="2026-05-01T08:30:00Z")

        assert captured["date_from"] == datetime(2026, 5, 1, 8, 30, tzinfo=UTC)

    async def test_naive_instant_is_read_as_utc(self, monkeypatch) -> None:
        captured = await self._call(monkeypatch, date_from="2026-05-01T08:30:00")

        assert captured["date_from"] == datetime(2026, 5, 1, 8, 30, tzinfo=UTC)

    async def test_no_dates_passes_none(self, monkeypatch) -> None:
        captured = await self._call(monkeypatch)

        assert captured["date_from"] is None
        assert captured["date_to"] is None

    async def test_unparseable_date_is_rejected(self, monkeypatch) -> None:
        with pytest.raises(HTTPException) as exc:
            await self._call(monkeypatch, date_from="last tuesday")

        assert exc.value.status_code == 422
        assert "date_from" in str(exc.value.detail)

    async def test_inverted_range_is_rejected(self, monkeypatch) -> None:
        with pytest.raises(HTTPException) as exc:
            await self._call(monkeypatch, date_from="2026-05-08", date_to="2026-05-01")

        assert exc.value.status_code == 422
