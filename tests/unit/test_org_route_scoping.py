"""RED phase — Organization route-level scoping tests (PR 2).

Tests for:
  1. verify_topic_access() — ownership check helper
  2. verify_source_access() — source visibility check
  3. Org-filtered SQL queries (topics, sources, signals)
  4. Dynamic labels helper
  5. Route-level org enforcement (topics, sources)
  6. SQL_INSERT_TOPIC includes org_id

pytest.mark.unit — no external dependencies.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ===================================================================
# 1. verify_topic_access — topic ownership check
# ===================================================================

class TestVerifyTopicAccess:

    @pytest.mark.asyncio
    async def test_allows_same_org(self):
        """User in same org as topic passes verification."""
        from services.api.anveshak.api.db.topics import verify_topic_access

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"org_id": "org-nia"})

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        # Should not raise
        await verify_topic_access(mock_conn, "topic-1", user)

    @pytest.mark.asyncio
    async def test_blocks_different_org(self):
        """User in different org gets 404."""
        from fastapi import HTTPException
        from services.api.anveshak.api.db.topics import verify_topic_access

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"org_id": "org-nia"})

        user = {"sub": "u1", "role": "analyst", "org_id": "org-ats"}
        with pytest.raises(HTTPException) as exc_info:
            await verify_topic_access(mock_conn, "topic-1", user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_blocks_nonexistent_topic(self):
        """Non-existent topic returns 404."""
        from fastapi import HTTPException
        from services.api.anveshak.api.db.topics import verify_topic_access

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        with pytest.raises(HTTPException) as exc_info:
            await verify_topic_access(mock_conn, "missing", user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_bypasses(self):
        """Super-admin can access any topic regardless of org."""
        from services.api.anveshak.api.db.topics import verify_topic_access

        mock_conn = AsyncMock()
        # Should not even query the DB
        user = {"sub": "sa-1", "role": "super-admin"}
        await verify_topic_access(mock_conn, "any-topic", user)
        mock_conn.fetchrow.assert_not_awaited()


# ===================================================================
# 2. verify_source_access — source visibility via org_sources
# ===================================================================

class TestVerifySourceAccess:

    @pytest.mark.asyncio
    async def test_allows_visible_source(self):
        """Source visible to user's org passes."""
        from services.api.anveshak.api.db.sources import verify_source_access

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)  # EXISTS returns 1

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        await verify_source_access(mock_conn, "src-1", user)

    @pytest.mark.asyncio
    async def test_blocks_invisible_source(self):
        """Source not visible to user's org gets 404."""
        from fastapi import HTTPException
        from services.api.anveshak.api.db.sources import verify_source_access

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=0)

        user = {"sub": "u1", "role": "analyst", "org_id": "org-nia"}
        with pytest.raises(HTTPException) as exc_info:
            await verify_source_access(mock_conn, "src-1", user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_bypasses(self):
        """Super-admin can access any source."""
        from services.api.anveshak.api.db.sources import verify_source_access

        mock_conn = AsyncMock()
        user = {"sub": "sa-1", "role": "super-admin"}
        await verify_source_access(mock_conn, "any-src", user)
        mock_conn.fetchval.assert_not_awaited()


# ===================================================================
# 3. Org-filtered SQL constants exist
# ===================================================================

class TestOrgFilteredSQL:

    def test_topics_has_org_filtered_query(self):
        """SQL_LIST_TOPICS_BY_ORG must exist and filter by org_id."""
        from services.api.anveshak.api.db.topics import SQL_LIST_TOPICS_BY_ORG

        assert "org_id" in SQL_LIST_TOPICS_BY_ORG.lower()

    def test_sources_has_org_filtered_query(self):
        """SQL_LIST_SOURCES_BY_ORG must exist and filter via org_sources."""
        from services.api.anveshak.api.db.sources import SQL_LIST_SOURCES_BY_ORG

        sql = SQL_LIST_SOURCES_BY_ORG.lower()
        assert "org_sources" in sql or "org_id" in sql

    def test_signals_has_org_filtered_query(self):
        """SQL_LIST_SIGNALS_BY_ORG must exist and filter by topic's org."""
        from services.api.anveshak.api.db.signals import SQL_LIST_SIGNALS_BY_ORG

        assert "org_id" in SQL_LIST_SIGNALS_BY_ORG.lower()

    def test_topic_get_org_sql_exists(self):
        """SQL_GET_TOPIC_ORG must exist for ownership checks."""
        from services.api.anveshak.api.db.topics import SQL_GET_TOPIC_ORG

        assert "org_id" in SQL_GET_TOPIC_ORG.lower()

    def test_source_check_visibility_sql_exists(self):
        """SQL_CHECK_SOURCE_VISIBILITY must exist."""
        from services.api.anveshak.api.db.sources import SQL_CHECK_SOURCE_VISIBILITY

        assert "org_sources" in SQL_CHECK_SOURCE_VISIBILITY.lower()


# ===================================================================
# 4. Org-filtered DB functions
# ===================================================================

class TestOrgFilteredDBFunctions:

    @pytest.mark.asyncio
    async def test_list_topics_by_org(self):
        """list_topics_by_org() passes org_id to SQL."""
        from services.api.anveshak.api.db.topics import list_topics_by_org

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await list_topics_by_org(mock_conn, "org-nia")
        call_args = mock_conn.fetch.call_args
        assert "org-nia" in call_args[0]

    @pytest.mark.asyncio
    async def test_list_sources_by_org(self):
        """list_sources_by_org() passes org_id to SQL."""
        from services.api.anveshak.api.db.sources import list_sources_by_org

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        await list_sources_by_org(mock_conn, "org-nia")
        call_args = mock_conn.fetch.call_args
        assert "org-nia" in call_args[0]

    @pytest.mark.asyncio
    async def test_list_signals_by_org(self):
        """list_signals_by_org() passes org_id and status to SQL."""
        from services.api.anveshak.api.db.signals import list_signals_by_org

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        items, total = await list_signals_by_org(mock_conn, "new", "org-nia")
        call_args = mock_conn.fetch.call_args
        assert "org-nia" in call_args[0]
        assert total == 0
        assert items == []


# ===================================================================
# 5. Dynamic labels helper
# ===================================================================

class TestDynamicLabels:

    def test_make_labels_default(self):
        """make_labels() returns valid JSON with classification and domain."""
        from services.api.anveshak.api.routes._labels import make_labels
        import json

        result = make_labels()
        parsed = json.loads(result)
        assert parsed["classification"] == "OPEN"
        assert parsed["domain"] == "osint"

    def test_make_labels_custom_domain(self):
        """make_labels() accepts custom domain."""
        from services.api.anveshak.api.routes._labels import make_labels
        import json

        result = make_labels(domain="report")
        parsed = json.loads(result)
        assert parsed["domain"] == "report"

    def test_make_labels_extra_kwargs(self):
        """make_labels() accepts arbitrary extra fields."""
        from services.api.anveshak.api.routes._labels import make_labels
        import json

        result = make_labels(topic_id="t-1", source_id="s-1")
        parsed = json.loads(result)
        assert parsed["topic_id"] == "t-1"
        assert parsed["source_id"] == "s-1"


# ===================================================================
# 6. SQL_INSERT_TOPIC includes org_id
# ===================================================================

class TestTopicInsertOrgId:

    def test_insert_topic_sql_has_org_id(self):
        """SQL_INSERT_TOPIC must include org_id column."""
        from services.api.anveshak.api.db.topics import SQL_INSERT_TOPIC

        assert "org_id" in SQL_INSERT_TOPIC.lower()


# ===================================================================
# 7. Route-level enforcement: list_topics uses org filter
# ===================================================================

class TestTopicRouteOrgScoping:

    @pytest.mark.asyncio
    async def test_list_topics_calls_org_filtered_for_analyst(self):
        """list_topics route uses list_topics_by_org for non-super-admin."""
        with patch(
            "services.api.anveshak.api.routes.topics.topics_db.list_topics_by_org",
            new=AsyncMock(return_value=[{"id": "t1", "name": "Test"}]),
        ) as mock_by_org:
            from services.api.anveshak.api.routes.topics import list_topics

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            result = await list_topics(db=mock_conn, user=user)

        mock_by_org.assert_awaited_once_with(mock_conn, "org-nia")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_topics_calls_unfiltered_for_super_admin(self):
        """list_topics route uses list_topics (unfiltered) for super-admin."""
        with patch(
            "services.api.anveshak.api.routes.topics.topics_db.list_topics",
            new=AsyncMock(return_value=[]),
        ) as mock_all:
            from services.api.anveshak.api.routes.topics import list_topics

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            result = await list_topics(db=mock_conn, user=user)

        mock_all.assert_awaited_once()


# ===================================================================
# 8. Route-level: list_sources uses org filter
# ===================================================================

class TestSourceRouteOrgScoping:

    @pytest.mark.asyncio
    async def test_list_sources_calls_org_filtered_for_analyst(self):
        """list_sources route uses list_sources_by_org for non-super-admin."""
        with patch(
            "services.api.anveshak.api.routes.sources.sources_db.list_sources_by_org",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_by_org:
            from services.api.anveshak.api.routes.sources import list_sources

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            result = await list_sources(credibility_below=None, limit=50, offset=0, db=mock_conn, user=user)

        mock_by_org.assert_awaited_once_with(mock_conn, "org-nia", 50, 0)

    @pytest.mark.asyncio
    async def test_list_sources_calls_unfiltered_for_super_admin(self):
        """list_sources route uses list_sources (unfiltered) for super-admin."""
        with patch(
            "services.api.anveshak.api.routes.sources.sources_db.list_sources",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_all:
            from services.api.anveshak.api.routes.sources import list_sources

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            result = await list_sources(credibility_below=None, limit=50, offset=0, db=mock_conn, user=user)

        mock_all.assert_awaited_once()


# ===================================================================
# 9. Route-level: list_signals uses org filter
# ===================================================================

class TestSignalRouteOrgScoping:

    @pytest.mark.asyncio
    async def test_list_signals_calls_org_filtered_for_analyst(self):
        """list_signals route uses list_signals_by_org for non-super-admin."""
        with patch(
            "services.api.anveshak.api.routes.signals.signals_db.list_signals_by_org",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_by_org:
            from services.api.anveshak.api.routes.signals import list_signals

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            result = await list_signals(
                status="new", topic_id=None, since=None, until=None,
                limit=50, offset=0,
                db=mock_conn, user=user,
            )

        mock_by_org.assert_awaited_once_with(mock_conn, "new", "org-nia", 50, 0)

    @pytest.mark.asyncio
    async def test_list_signals_calls_unfiltered_for_super_admin(self):
        """list_signals route uses list_signals (unfiltered) for super-admin."""
        with patch(
            "services.api.anveshak.api.routes.signals.signals_db.list_signals",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_all:
            from services.api.anveshak.api.routes.signals import list_signals

            mock_conn = AsyncMock()
            user = {"sub": "sa-1", "role": "super-admin", "jti": "x"}
            result = await list_signals(
                status="new", topic_id=None, since=None, until=None,
                limit=50, offset=0,
                db=mock_conn, user=user,
            )

        mock_all.assert_awaited_once()


# ===================================================================
# 10. Route-level: get_topic verifies access
# ===================================================================

class TestGetTopicOrgVerification:

    @pytest.mark.asyncio
    async def test_get_topic_calls_verify_access(self):
        """get_topic route calls verify_topic_access before fetching."""
        with patch(
            "services.api.anveshak.api.routes.topics.topics_db.verify_topic_access",
            new=AsyncMock(),
        ) as mock_verify, patch(
            "services.api.anveshak.api.routes.topics.topics_db.get_topic",
            new=AsyncMock(return_value={"id": "t1", "name": "Test"}),
        ):
            from services.api.anveshak.api.routes.topics import get_topic

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            await get_topic(topic_id="t1", db=mock_conn, user=user)

        mock_verify.assert_awaited_once_with(mock_conn, "t1", user)

    @pytest.mark.asyncio
    async def test_get_topic_blocks_cross_org(self):
        """get_topic returns 404 when topic belongs to different org."""
        from fastapi import HTTPException

        with patch(
            "services.api.anveshak.api.routes.topics.topics_db.verify_topic_access",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Topic not found")),
        ):
            from services.api.anveshak.api.routes.topics import get_topic

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-ats", "jti": "x"}
            with pytest.raises(HTTPException) as exc_info:
                await get_topic(topic_id="t1", db=mock_conn, user=user)
            assert exc_info.value.status_code == 404


# ===================================================================
# 11. Route-level: source routes verify access
# ===================================================================

class TestSourceRouteVerification:

    @pytest.mark.asyncio
    async def test_check_health_calls_verify_access(self):
        """check_source_health calls verify_source_access."""
        with patch(
            "services.api.anveshak.api.routes.sources.sources_db.verify_source_access",
            new=AsyncMock(),
        ) as mock_verify, patch(
            "services.api.anveshak.api.routes.sources.sources_db.get_source_for_health",
            new=AsyncMock(return_value={
                "platform": "web", "url_or_handle": "https://example.com",
                "consecutive_failures": 0,
            }),
        ), patch(
            "services.api.anveshak.api.routes.sources.sources_db.update_source_health",
            new=AsyncMock(),
        ), patch(
            "services.api.anveshak.api.routes.sources._probe_web",
            new=AsyncMock(return_value=("healthy", None, False)),
        ):
            from services.api.anveshak.api.routes.sources import check_source_health

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            await check_source_health(source_id="src-1", db=mock_conn, user=user)

        mock_verify.assert_awaited_once_with(mock_conn, "src-1", user)


# ===================================================================
# 12. Route-level: report routes verify topic access
# ===================================================================

class TestReportRouteVerification:

    @pytest.mark.asyncio
    async def test_list_topic_reports_calls_verify(self):
        """list_topic_reports calls verify_topic_access."""
        with patch(
            "services.api.anveshak.api.routes.reports.topics_db.verify_topic_access",
            new=AsyncMock(),
        ) as mock_verify, patch(
            "services.api.anveshak.api.routes.reports.reports_db.list_topic_reports",
            new=AsyncMock(return_value=([], 0)),
        ):
            from services.api.anveshak.api.routes.reports import list_topic_reports

            mock_conn = AsyncMock()
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            await list_topic_reports(topic_id="t1", db=mock_conn, user=user)

        mock_verify.assert_awaited_once_with(mock_conn, "t1", user)


# ===================================================================
# 13. Route-level: export routes verify topic access
# ===================================================================

class TestExportRouteVerification:

    @pytest.mark.asyncio
    async def test_export_content_calls_verify(self):
        """export_content calls verify_topic_access."""
        with patch(
            "services.api.anveshak.api.routes.export.topics_db.verify_topic_access",
            new=AsyncMock(),
        ) as mock_verify, patch(
            "services.api.anveshak.api.routes.export._fetch_rows",
            new=AsyncMock(return_value=[{"id": "1", "url": "http://x"}]),
        ), patch(
            "services.api.anveshak.api.routes.export.audit_db.log_action",
            new=AsyncMock(),
        ):
            from services.api.anveshak.api.routes.export import export_content

            mock_conn = AsyncMock()
            mock_request = AsyncMock()
            mock_request.client = AsyncMock()
            mock_request.client.host = "127.0.0.1"
            user = {"sub": "u1", "role": "analyst", "org_id": "org-nia", "jti": "x"}
            await export_content(
                request=mock_request, topic_id="t1", format="json",
                limit=10, db=mock_conn, user=user,
            )

        mock_verify.assert_awaited_once_with(mock_conn, "t1", user)
