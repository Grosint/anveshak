"""RED phase — Audit trail and dead-letter queue tests.

Tests for:
  - log_action() stores audit entries in DB
  - get_audit_trail() retrieves filtered entries
  - DLQ: record_failed_job() stores failed job payload
  - DLQ: list_failed_jobs() returns failed jobs
  - HSTS header present when enabled
  - Backup script references correct volume name

pytest.mark.unit — no external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


# ===================================================================
# 1. Audit trail DB functions
# ===================================================================


class TestAuditTrailDB:
    """db/audit.py must provide log_action() and get_audit_trail()."""

    @pytest.mark.asyncio
    async def test_log_action_callable(self):
        """log_action function must exist and be callable."""
        from services.api.anveshak.api.db.audit import log_action

        assert callable(log_action)

    @pytest.mark.asyncio
    async def test_log_action_inserts_row(self, mock_conn):
        """log_action must INSERT into audit_trail table."""
        from services.api.anveshak.api.db.audit import log_action

        await log_action(
            mock_conn,
            user_id="user-1",
            action="topic.create",
            resource_type="topic",
            resource_id="topic-abc",
            details={"name": "Test Topic"},
            ip_address="10.0.0.1",
        )

        mock_conn.execute.assert_awaited_once()
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        assert "audit_trail" in sql.lower()
        assert "INSERT" in sql.upper()

    @pytest.mark.asyncio
    async def test_log_action_passes_all_fields(self, mock_conn):
        """log_action must pass user_id, action, resource_type, resource_id, details, ip."""
        from services.api.anveshak.api.db.audit import log_action

        await log_action(
            mock_conn,
            user_id="user-99",
            action="source.delete",
            resource_type="source",
            resource_id="src-xyz",
            details={"force": True},
            ip_address="192.168.1.1",
        )

        call_args = mock_conn.execute.call_args[0]
        # Positional args after SQL: id, user_id, action, resource_type, resource_id, details, ip, timestamp, labels
        assert call_args[1]  # id (non-empty)
        assert call_args[2] == "user-99"  # user_id
        assert call_args[3] == "source.delete"  # action
        assert call_args[4] == "source"  # resource_type
        assert call_args[5] == "src-xyz"  # resource_id

    @pytest.mark.asyncio
    async def test_get_audit_trail_callable(self):
        """get_audit_trail function must exist and be callable."""
        from services.api.anveshak.api.db.audit import get_audit_trail

        assert callable(get_audit_trail)

    @pytest.mark.asyncio
    async def test_get_audit_trail_returns_tuple(self, mock_conn):
        """get_audit_trail must return (items, total) tuple."""
        from services.api.anveshak.api.db.audit import get_audit_trail

        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "a1",
                    "user_id": "u1",
                    "action": "topic.create",
                    "resource_type": "topic",
                    "resource_id": "t1",
                    "created_at": datetime.now(UTC),
                    "total": 42,
                },
            ]
        )

        items, total = await get_audit_trail(mock_conn, resource_type="topic", limit=50)
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["action"] == "topic.create"
        assert "total" not in items[0]  # total stripped from items
        assert total == 42

    @pytest.mark.asyncio
    async def test_get_audit_trail_empty_returns_zero_total(self, mock_conn):
        """get_audit_trail with no rows must return total=0."""
        from services.api.anveshak.api.db.audit import get_audit_trail

        mock_conn.fetch = AsyncMock(return_value=[])
        items, total = await get_audit_trail(mock_conn, limit=50)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_audit_trail_filters_by_resource_type(self, mock_conn):
        """get_audit_trail SQL must filter by resource_type when provided."""
        from services.api.anveshak.api.db.audit import get_audit_trail

        mock_conn.fetch = AsyncMock(return_value=[])
        await get_audit_trail(mock_conn, resource_type="source", limit=100)

        call_args = mock_conn.fetch.call_args[0]
        sql = call_args[0]
        assert "resource_type" in sql.lower()

    @pytest.mark.asyncio
    async def test_get_audit_trail_filters_by_resource_id(self, mock_conn):
        """get_audit_trail SQL must filter by resource_id when provided."""
        from services.api.anveshak.api.db.audit import get_audit_trail

        mock_conn.fetch = AsyncMock(return_value=[])
        await get_audit_trail(mock_conn, resource_type="topic", resource_id="t1", limit=50)

        call_args = mock_conn.fetch.call_args[0]
        sql = call_args[0]
        assert "resource_id" in sql.lower()

    def test_sql_constants_exist(self):
        """SQL constants for audit trail must be defined."""
        from services.api.anveshak.api.db.audit import SQL_GET_AUDIT_TRAIL, SQL_INSERT_AUDIT

        assert "INSERT" in SQL_INSERT_AUDIT.upper()
        assert "SELECT" in SQL_GET_AUDIT_TRAIL.upper()


# ===================================================================
# 2. Dead-letter queue DB functions
# ===================================================================


class TestDeadLetterQueue:
    """db/failed_jobs.py must store and retrieve failed ARQ job payloads."""

    @pytest.mark.asyncio
    async def test_record_failed_job_callable(self):
        """record_failed_job function must exist."""
        from services.api.anveshak.api.db.failed_jobs import record_failed_job

        assert callable(record_failed_job)

    @pytest.mark.asyncio
    async def test_record_failed_job_inserts_row(self, mock_conn):
        """record_failed_job must INSERT into failed_jobs table."""
        from services.api.anveshak.api.db.failed_jobs import record_failed_job

        await record_failed_job(
            mock_conn,
            job_id="job-001",
            function_name="generate_report",
            args='["report-id-123"]',
            error="Ollama connection refused",
            queue_name="arq:reporter",
        )

        mock_conn.execute.assert_awaited_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "failed_jobs" in sql.lower()
        assert "INSERT" in sql.upper()

    @pytest.mark.asyncio
    async def test_record_failed_job_uses_on_conflict(self, mock_conn):
        """record_failed_job must use ON CONFLICT to be idempotent."""
        from services.api.anveshak.api.db.failed_jobs import record_failed_job

        await record_failed_job(
            mock_conn,
            job_id="job-dup",
            function_name="scrape_topic",
            args='["topic-1"]',
            error="Timeout",
            queue_name="arq:scraper",
        )

        sql = mock_conn.execute.call_args[0][0]
        assert "ON CONFLICT" in sql.upper()

    @pytest.mark.asyncio
    async def test_list_failed_jobs_returns_list(self, mock_conn):
        """list_failed_jobs must return a list of dicts."""
        from services.api.anveshak.api.db.failed_jobs import list_failed_jobs

        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "j1",
                    "job_id": "job-001",
                    "function_name": "generate_report",
                    "error": "timeout",
                    "failed_at": datetime.now(UTC),
                },
            ]
        )

        result = await list_failed_jobs(mock_conn, limit=50)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["function_name"] == "generate_report"

    @pytest.mark.asyncio
    async def test_list_failed_jobs_filters_by_queue(self, mock_conn):
        """list_failed_jobs can filter by queue_name."""
        from services.api.anveshak.api.db.failed_jobs import list_failed_jobs

        mock_conn.fetch = AsyncMock(return_value=[])
        await list_failed_jobs(mock_conn, queue_name="arq:reporter", limit=50)

        sql = mock_conn.fetch.call_args[0][0]
        assert "queue_name" in sql.lower()

    def test_sql_constants_exist(self):
        """SQL constants for failed_jobs must be defined."""
        from services.api.anveshak.api.db.failed_jobs import (
            SQL_INSERT_FAILED_JOB,
            SQL_LIST_FAILED_JOBS,
        )

        assert "INSERT" in SQL_INSERT_FAILED_JOB.upper()
        assert "SELECT" in SQL_LIST_FAILED_JOBS.upper()


# ===================================================================
# 3. Audit trail API endpoint
# ===================================================================


class TestAuditTrailEndpoint:
    """GET /api/v1/system/audit-trail must return audit entries (admin only)."""

    def test_audit_trail_route_exists(self):
        """System router must have a /audit-trail endpoint."""
        from services.api.anveshak.api.routes.system import router

        paths = [route.path for route in router.routes]
        assert "/api/v1/system/audit-trail" in paths or "/audit-trail" in paths


# ===================================================================
# 4. Failed jobs API endpoint
# ===================================================================


class TestFailedJobsEndpoint:
    """GET /api/v1/system/failed-jobs must return DLQ entries (admin only)."""

    def test_failed_jobs_route_exists(self):
        """System router must have a /failed-jobs endpoint."""
        from services.api.anveshak.api.routes.system import router

        paths = [route.path for route in router.routes]
        assert "/api/v1/system/failed-jobs" in paths or "/failed-jobs" in paths


# ===================================================================
# 5. HSTS + CSP headers
# ===================================================================


class TestSecurityHeaders:
    """Security middleware must include HSTS when enabled."""

    def test_hsts_header_logic_exists(self):
        """SecurityHeadersMiddleware source must reference Strict-Transport-Security."""
        from pathlib import Path

        source = Path("services/api/anveshak/api/middleware/security.py").read_text()
        assert "Strict-Transport-Security" in source, "Security middleware must set HSTS header"

    def test_csp_header_logic_exists(self):
        """SecurityHeadersMiddleware source must reference Content-Security-Policy."""
        from pathlib import Path

        source = Path("services/api/anveshak/api/middleware/security.py").read_text()
        assert "Content-Security-Policy" in source, "Security middleware must set CSP header"

    def test_hsts_setting_exists(self):
        """Settings must have hsts_enabled flag."""
        from services.api.anveshak.api.settings import Settings

        s = Settings()
        assert hasattr(s, "hsts_enabled")


# ===================================================================
# 6. Backup volume name
# ===================================================================


class TestBackupScript:
    """backup.sh must reference the correct Docker volume name."""

    def test_backup_uses_correct_volume(self):
        """backup.sh must use 'anveshak_vision_media', not 'anveshak_media_store'."""
        from pathlib import Path

        content = Path("scripts/backup.sh").read_text()
        assert "anveshak_media_store" not in content, (
            "backup.sh references non-existent volume 'anveshak_media_store' — should be 'anveshak_vision_media'"
        )
        assert "anveshak_vision_media" in content, (
            "backup.sh must use volume 'anveshak_vision_media' (matches compose.yml)"
        )


# ===================================================================
# 7. Redis AOF configuration
# ===================================================================


class TestRedisAOF:
    """Redis must have AOF persistence enabled."""

    def test_compose_redis_has_aof(self):
        """compose.yml Redis command must include --appendonly yes."""
        from pathlib import Path

        content = Path("infra/compose.yml").read_text()
        assert "--appendonly yes" in content or "appendonly yes" in content, (
            "Redis must have AOF enabled (--appendonly yes) to prevent ARQ job loss"
        )

    def test_compose_redis_has_appendfsync(self):
        """compose.yml Redis command must include --appendfsync everysec."""
        from pathlib import Path

        content = Path("infra/compose.yml").read_text()
        assert "appendfsync" in content, "Redis must specify --appendfsync for durability control"


# ===================================================================
# 8. Migration 005 exists
# ===================================================================


class TestMigrationAuditTables:
    """Initial migration must create audit_trail and failed_jobs tables."""

    def test_migration_file_exists(self):
        """Migration 001 file must exist."""
        from pathlib import Path

        migration_dir = Path("services/api/migrations/versions")
        files = [f.name for f in migration_dir.iterdir()]
        assert any("001" in f for f in files), (
            "Migration 001 must exist in services/api/migrations/versions/"
        )

    def test_migration_creates_audit_trail(self):
        """Migration 001 must create audit_trail table."""
        from pathlib import Path

        migration_dir = Path("services/api/migrations/versions")
        content = ""
        for f in migration_dir.iterdir():
            if "001" in f.name:
                content = f.read_text()
                break

        assert "audit_trail" in content.lower(), "Migration 001 must create audit_trail table"

    def test_migration_creates_failed_jobs(self):
        """Migration 001 must create failed_jobs table."""
        from pathlib import Path

        migration_dir = Path("services/api/migrations/versions")
        content = ""
        for f in migration_dir.iterdir():
            if "001" in f.name:
                content = f.read_text()
                break

        assert "failed_jobs" in content.lower(), "Migration 001 must create failed_jobs table"
