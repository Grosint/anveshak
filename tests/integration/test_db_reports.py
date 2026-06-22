"""Integration tests — reports DB repository against real PostgreSQL.

Replaces tests/unit/test_db_reports.py which only tested mocks.
These tests exercise real SQL: INSERT, SELECT, JOIN, JSON aggregation, NULLs.

Requires: make up (PostgreSQL running)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC

import pytest

from anveshak.api.db.reports import (
    fetch_report,
    get_report_geojson,
    insert_report,
    list_topic_reports,
)

from tests.conftest import LABELS_JSON

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_topic(conn, topic_id: str) -> None:
    await conn.execute(
        """
        INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
        VALUES ('org-integration-test', 'Integration Test Org', 'integration-test', NOW(), NOW(),
                '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
    )
    await conn.execute(
        """
        INSERT INTO topics (id, name, keywords, created_at, updated_at, labels, org_id)
        VALUES ($1, $2, '{}', NOW(), NOW(), $3::jsonb, $4)
        ON CONFLICT (id) DO NOTHING
        """,
        topic_id, f"Report Test {topic_id[:8]}", LABELS_JSON, "org-integration-test",
    )


async def _cleanup(conn, topic_id: str, report_ids: list[str]) -> None:
    for rid in report_ids:
        await conn.execute("DELETE FROM report_source_warnings WHERE report_id=$1", rid)
        await conn.execute("DELETE FROM reports WHERE id=$1", rid)
    await conn.execute("DELETE FROM topics WHERE id=$1", topic_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_insert_and_fetch_report(db_pool):
    """INSERT a report then SELECT it back — all fields must match."""
    topic_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await _create_topic(conn, topic_id)
        await insert_report(
            conn, report_id, topic_id, "intelligence_brief",
            now, now, 30.0, now, LABELS_JSON,
        )
        result = await fetch_report(conn, report_id)

    try:
        assert result is not None, "fetch_report should return the inserted report"
        assert result["id"] == report_id
        assert result["topic_id"] == topic_id
        assert result["report_type"] == "intelligence_brief"
        assert result["credibility_min_filter"] == 30.0
        # source_warnings should be empty JSON array (no warnings yet)
        warnings = json.loads(result["source_warnings"]) if isinstance(result["source_warnings"], str) else result["source_warnings"]
        assert warnings == [], f"Expected empty warnings, got {warnings}"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id, [report_id])


async def test_fetch_report_returns_none_for_missing(db_pool):
    """fetch_report with non-existent ID must return None, not crash."""
    async with db_pool.acquire() as conn:
        result = await fetch_report(conn, "nonexistent-report-id")
    assert result is None


async def test_list_topic_reports_generation_status(db_pool):
    """list_topic_reports must compute generation_status from generated_at and generation_error."""
    topic_id = str(uuid.uuid4())
    report_queued = str(uuid.uuid4())
    report_complete = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await _create_topic(conn, topic_id)
        # Queued report (no generated_at, no error)
        await insert_report(conn, report_queued, topic_id, "intelligence_brief",
                            now, now, 30.0, now, LABELS_JSON)
        # Complete report (has generated_at)
        await insert_report(conn, report_complete, topic_id, "intelligence_brief",
                            now, now, 30.0, now, LABELS_JSON)
        await conn.execute(
            "UPDATE reports SET generated_at=$1 WHERE id=$2", now, report_complete
        )

        result = await list_topic_reports(conn, topic_id)

    try:
        assert len(result) == 2, f"Expected 2 reports, got {len(result)}"
        statuses = {r["id"]: r["generation_status"] for r in result}
        assert statuses[report_queued] == "queued"
        assert statuses[report_complete] == "complete"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id, [report_queued, report_complete])


async def test_list_topic_reports_empty_topic(db_pool):
    """Topic with no reports → empty list, no crash."""
    topic_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await _create_topic(conn, topic_id)
        result = await list_topic_reports(conn, topic_id)
    try:
        assert result == []
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id, [])


async def test_get_report_geojson_returns_none_when_missing(db_pool):
    """get_report_geojson for non-existent report → None."""
    async with db_pool.acquire() as conn:
        result = await get_report_geojson(conn, "nonexistent-id")
    assert result is None


async def test_get_report_geojson_null_geojson(db_pool):
    """Report without GIS data → geojson field is NULL."""
    topic_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await _create_topic(conn, topic_id)
        await insert_report(conn, report_id, topic_id, "intelligence_brief",
                            now, now, 30.0, now, LABELS_JSON)
        result = await get_report_geojson(conn, report_id)

    try:
        assert result is not None, "Report exists but get_report_geojson returned None"
        assert result["geojson"] is None, "Newly inserted report should have NULL geojson"
    finally:
        async with db_pool.acquire() as conn:
            await _cleanup(conn, topic_id, [report_id])
