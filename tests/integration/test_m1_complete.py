"""Integration tests — M1 complete (Phase 7, criteria 7.1–7.6, 7.9, 7.10).

Requires: Docker Compose up with PostgreSQL + Redis.
Run: uv run pytest tests/integration/test_m1_complete.py -v

These tests exercise the full credibility feedback loop end-to-end:
  cross-verification boost → contradiction drop → report source warnings dedup.
"""
import uuid

import pytest

from anveshak.analyst.credibility import (
    run_cross_verification_update,
    run_contradiction_update,
    clamp_score,
)
from anveshak.analyst.settings import AnalystSettings
from tests.conftest import LABELS_JSON, insert_content_item

settings = AnalystSettings()


# ---------------------------------------------------------------------------
# Helpers (read-only queries)
# ---------------------------------------------------------------------------

async def _get_source_score(conn, source_id: str) -> float:
    return await conn.fetchval(
        "SELECT credibility_score FROM sources WHERE id = $1", source_id
    )


async def _count_audit_entries(conn, source_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM credibility_audit_log WHERE source_id = $1", source_id
    )


async def _count_report_warnings(conn, report_id: str, source_id: str) -> int:
    return await conn.fetchval(
        "SELECT COUNT(*) FROM report_source_warnings WHERE report_id=$1 AND source_id=$2",
        report_id, source_id,
    )


async def _insert_cluster(pool, cluster_id: str, topic_id: str, isc: int, item_count: int = 5) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO narrative_clusters
                (id, topic_id, label, item_count, independent_source_count, created_at, updated_at, labels)
            VALUES ($1, $2, 'Test Cluster', $3, $4, NOW(), NOW(), $5::jsonb)
            ON CONFLICT (id) DO NOTHING
        """, cluster_id, topic_id, item_count, isc, LABELS_JSON)


async def _insert_content_item_m1(
    pool, item_id: str, topic_id: str, source_id: str,
    cluster_id: str | None = None,
) -> None:
    content_hash = f"hash_{item_id}"
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO content_items
                (id, topic_id, source_id, raw_text, clean_text, content_hash,
                 narrative_cluster_id, captured_at, created_at, updated_at, labels, org_id)
            VALUES ($1, $2, $3, 'test text', 'test text', $4, $5, NOW(), NOW(), NOW(), $6::jsonb, $7)
            ON CONFLICT (content_hash) DO NOTHING
        """, item_id, topic_id, source_id, content_hash, cluster_id, LABELS_JSON, "org-integration-test")


# ---------------------------------------------------------------------------
# Test 1: Cross-verification boost (7.1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_verification_boosts_high_credibility_sources(db_pool, make_topic, make_source):
    """Sources in multi-platform clusters with score >= high_threshold get boosted."""
    topic_id = await make_topic(name="Test Topic xv-boost")
    source_a_id = await make_source(name="Source A", credibility_score=70.0)
    source_b_id = await make_source(name="Source B", credibility_score=70.0)

    cluster_id = str(uuid.uuid4())
    item_a_id = str(uuid.uuid4())
    item_b_id = str(uuid.uuid4())
    initial_score = 70.0

    await _insert_cluster(db_pool, cluster_id, topic_id, isc=2)
    await _insert_content_item_m1(db_pool, item_a_id, topic_id, source_a_id, cluster_id)
    await _insert_content_item_m1(db_pool, item_b_id, topic_id, source_b_id, cluster_id)

    updated = await run_cross_verification_update(db_pool, topic_id)

    assert updated >= 2, f"Expected >= 2 sources boosted, got {updated}"

    async with db_pool.acquire() as conn:
        score_a = await _get_source_score(conn, source_a_id)
        score_b = await _get_source_score(conn, source_b_id)
        audit_a = await _count_audit_entries(conn, source_a_id)
        audit_b = await _count_audit_entries(conn, source_b_id)

    expected = clamp_score(initial_score + settings.credibility_cross_verify_boost)
    assert score_a == expected, f"Source A: expected {expected}, got {score_a}"
    assert score_b == expected, f"Source B: expected {expected}, got {score_b}"
    assert audit_a >= 1, "Cross-verify boost must write audit log entry for source A"
    assert audit_b >= 1, "Cross-verify boost must write audit log entry for source B"


# ---------------------------------------------------------------------------
# Test 2: Cross-verify does NOT boost low-credibility sources (7.1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_verification_skips_low_credibility_sources(db_pool, make_topic, make_source):
    """Sources below credibility_high_threshold are not boosted even if in a cluster."""
    topic_id = await make_topic(name="Test Topic xv-skip")
    source_id = await make_source(name="Low Credibility Source", credibility_score=40.0)

    cluster_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    low_score = 40.0

    await _insert_cluster(db_pool, cluster_id, topic_id, isc=2)
    await _insert_content_item_m1(db_pool, item_id, topic_id, source_id, cluster_id)

    await run_cross_verification_update(db_pool, topic_id)

    async with db_pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score == low_score, f"Low-credibility source should not be boosted: got {score}"


# ---------------------------------------------------------------------------
# Test 3: Score is clamped to 100.0 (7.5)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_verification_clamps_score_at_100(db_pool, make_topic, make_source):
    """A source already at 99.0 should not exceed 100.0 after boost."""
    topic_id = await make_topic(name="Test Topic xv-clamp")
    source_id = await make_source(name="Near-Max Source", credibility_score=99.0)

    cluster_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    await _insert_cluster(db_pool, cluster_id, topic_id, isc=2)
    await _insert_content_item_m1(db_pool, item_id, topic_id, source_id, cluster_id)

    await run_cross_verification_update(db_pool, topic_id)

    async with db_pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score <= 100.0, f"Score must never exceed 100.0, got {score}"


# ---------------------------------------------------------------------------
# Test 4: Contradiction drop (7.2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_contradiction_drops_high_noise_ratio_source(db_pool, make_topic, make_source):
    """Source with >= 60% unclustered items on a topic with real clusters gets dropped."""
    topic_id = await make_topic(name="Test Topic contra-drop")
    source_id = await make_source(name="Contradicting Source", credibility_score=60.0)
    anchor_source_id = await make_source(name="Anchor Source", credibility_score=80.0)

    cluster_id = str(uuid.uuid4())
    anchor_item_id = str(uuid.uuid4())
    initial_score = 60.0

    await _insert_cluster(db_pool, cluster_id, topic_id, isc=2)
    await _insert_content_item_m1(db_pool, anchor_item_id, topic_id, anchor_source_id, cluster_id)

    # Noise items from contradicting source (no cluster_id)
    for _ in range(settings.credibility_contradiction_min_items + 1):
        await _insert_content_item_m1(
            db_pool, str(uuid.uuid4()), topic_id, source_id, cluster_id=None
        )

    updated = await run_contradiction_update(db_pool)

    assert updated >= 1, "Contradiction update should have dropped at least 1 source"

    async with db_pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)
        audit_count = await _count_audit_entries(conn, source_id)

    expected = clamp_score(initial_score - settings.credibility_contradiction_drop)
    assert score == expected, f"Expected {expected}, got {score}"
    assert audit_count >= 1, "Contradiction drop must write audit log entry"


# ---------------------------------------------------------------------------
# Test 5: Contradiction does NOT drop source with low noise ratio (7.2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_contradiction_skips_low_noise_ratio_source(db_pool, make_topic, make_source):
    """Source with < 60% noise items should not be penalised."""
    topic_id = await make_topic(name="Test Topic contra-skip")
    source_id = await make_source(name="Good Source", credibility_score=75.0)

    cluster_id = str(uuid.uuid4())
    initial_score = 75.0

    await _insert_cluster(db_pool, cluster_id, topic_id, isc=2)

    # 8 clustered, 2 unclustered → noise ratio = 0.2 (below threshold 0.6)
    for _ in range(8):
        await _insert_content_item_m1(
            db_pool, str(uuid.uuid4()), topic_id, source_id, cluster_id
        )
    for _ in range(2):
        await _insert_content_item_m1(
            db_pool, str(uuid.uuid4()), topic_id, source_id, cluster_id=None
        )

    await run_contradiction_update(db_pool)

    async with db_pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score == initial_score, (
        f"Low noise ratio source should not be dropped: got {score}"
    )


# ---------------------------------------------------------------------------
# Test 6: Report source warnings dedup (7.6)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_source_warning_no_duplicates(db_pool, make_topic, make_source):
    """check_source_warnings cron must not insert duplicate (report_id, source_id) rows."""
    from anveshak.reporter.db import insert_source_warning

    report_id = str(uuid.uuid4())
    topic_id = await make_topic(name="Test Topic rsw-dedup")
    source_id = await make_source(name="Warning Source", credibility_score=50.0)

    async with db_pool.acquire() as conn:
        # Create a minimal report row
        await conn.execute("""
            INSERT INTO reports
                (id, topic_id, report_type, time_window_start, time_window_end,
                 credibility_min_filter, generated_at, source_snapshot,
                 created_at, updated_at, labels)
            VALUES ($1, $2, 'intelligence_brief', NOW() - INTERVAL '1 day', NOW(),
                    30.0, NOW(), '{}'::jsonb, NOW(), NOW(), $3::jsonb)
            ON CONFLICT (id) DO NOTHING
        """, report_id, topic_id, LABELS_JSON)

    # Simulate cron firing twice — both should produce exactly one row
    await insert_source_warning(db_pool, report_id, source_id, "Warning Source",
                                old_score=80.0, new_score=50.0)
    await insert_source_warning(db_pool, report_id, source_id, "Warning Source",
                                old_score=80.0, new_score=50.0)

    async with db_pool.acquire() as conn:
        count = await _count_report_warnings(conn, report_id, source_id)

    assert count == 1, (
        f"Expected exactly 1 warning row, got {count}. "
        "ON CONFLICT DO NOTHING is not working — migration 004 may not be applied."
    )


# ---------------------------------------------------------------------------
# Test 7: credibility_below API filter SQL (7.9) — DB-level
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_sources_below_returns_only_low_credibility(db_pool, make_source):
    """list_sources_below(40) must return only sources with score < 40."""
    low_id = await make_source(name="Low Source", credibility_score=25.0)
    high_id = await make_source(name="High Source", credibility_score=85.0)

    from anveshak.api.db.sources import list_sources_below
    async with db_pool.acquire() as conn:
        results = await list_sources_below(conn, 40.0)

    result_ids = [r["id"] for r in results]
    assert low_id in result_ids, "Source with score 25 should appear in credibility_below=40"
    assert high_id not in result_ids, "Source with score 85 must not appear in credibility_below=40"


# ---------------------------------------------------------------------------
# Test 8: topic sources query (7.10) — DB-level
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_topic_sources_returns_contributing_sources(db_pool, make_topic, make_source):
    """list_topic_sources returns only sources that have content items in the topic."""
    topic_id = await make_topic(name="Test Topic ts-contrib")
    contributing_source_id = await make_source(name="Contributing", credibility_score=60.0)
    non_contributing_source_id = await make_source(name="Non-Contributing", credibility_score=60.0)

    item_id = str(uuid.uuid4())

    async with db_pool.acquire() as conn:
        # Link both sources to the topic via topic_sources join table
        await conn.execute(
            "INSERT INTO topic_sources (topic_id, source_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            topic_id, contributing_source_id,
        )
        await conn.execute(
            "INSERT INTO topic_sources (topic_id, source_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            topic_id, non_contributing_source_id,
        )

    # Only the contributing source has content items
    await _insert_content_item_m1(db_pool, item_id, topic_id, contributing_source_id)

    from anveshak.api.db.sources import list_topic_sources
    async with db_pool.acquire() as conn:
        results = await list_topic_sources(conn, topic_id)

    result_ids = [r["id"] for r in results]
    assert contributing_source_id in result_ids
    assert non_contributing_source_id in result_ids  # linked but no content yet

    # item_count distinguishes contributing from non-contributing
    contributing_row = next(r for r in results if r["id"] == contributing_source_id)
    non_contributing_row = next(r for r in results if r["id"] == non_contributing_source_id)
    assert contributing_row["item_count"] >= 1
    assert non_contributing_row["item_count"] == 0
