"""Integration tests — M1 complete (Phase 7, criteria 7.1–7.6, 7.9, 7.10).

Requires: Docker Compose up with PostgreSQL + Redis.
Run: uv run pytest tests/integration/test_m1_complete.py -v

These tests exercise the full credibility feedback loop end-to-end:
  cross-verification boost → contradiction drop → report source warnings dedup.
"""
import asyncio
import json
import uuid
from datetime import datetime, UTC

import asyncpg
import pytest

from anveshak.analyst.credibility import (
    run_cross_verification_update,
    run_contradiction_update,
    clamp_score,
)
from anveshak.analyst.settings import AnalystSettings

POSTGRES_URL = "postgresql://anveshak:anveshak@localhost:5433/anveshak"
LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'

settings = AnalystSettings()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def pool():
    p = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield p
    await p.close()


async def _insert_topic(conn, topic_id: str) -> None:
    await conn.execute("""
        INSERT INTO topics (id, name, keywords, signal_threshold, created_at, updated_at, labels)
        VALUES ($1, $2, ARRAY['test'], 2, NOW(), NOW(), $3::jsonb)
        ON CONFLICT (id) DO NOTHING
    """, topic_id, f"Test Topic {topic_id[:8]}", LABELS_JSON)


async def _insert_source(conn, source_id: str, name: str, score: float) -> None:
    await conn.execute("""
        INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                             auto_score_enabled, is_active, created_at, updated_at, labels)
        VALUES ($1, $2, $3, 'web', $4, TRUE, TRUE, NOW(), NOW(), $5::jsonb)
        ON CONFLICT (id) DO NOTHING
    """, source_id, name, f"https://{source_id}.example.com", score, LABELS_JSON)


async def _insert_cluster(conn, cluster_id: str, topic_id: str, isc: int) -> None:
    await conn.execute("""
        INSERT INTO narrative_clusters
            (id, topic_id, label, item_count, independent_source_count, created_at, updated_at, labels)
        VALUES ($1, $2, 'Test Cluster', 3, $3, NOW(), NOW(), $4::jsonb)
        ON CONFLICT (id) DO NOTHING
    """, cluster_id, topic_id, isc, LABELS_JSON)


async def _insert_content_item(
    conn, item_id: str, topic_id: str, source_id: str,
    cluster_id: str | None = None,
) -> None:
    content_hash = f"hash_{item_id}"
    await conn.execute("""
        INSERT INTO content_items
            (id, topic_id, source_id, raw_text, clean_text, content_hash,
             narrative_cluster_id, captured_at, created_at, updated_at, labels)
        VALUES ($1, $2, $3, 'test text', 'test text', $4, $5, NOW(), NOW(), NOW(), $6::jsonb)
        ON CONFLICT (content_hash) DO NOTHING
    """, item_id, topic_id, source_id, content_hash, cluster_id, LABELS_JSON)


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


# ---------------------------------------------------------------------------
# Test 1: Cross-verification boost (7.1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_verification_boosts_high_credibility_sources(pool):
    """Sources in multi-platform clusters with score >= high_threshold get boosted."""
    topic_id = str(uuid.uuid4())
    source_a_id = str(uuid.uuid4())
    source_b_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    item_a_id = str(uuid.uuid4())
    item_b_id = str(uuid.uuid4())

    initial_score = 70.0  # above credibility_high_threshold (60.0)

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_a_id, "Source A", initial_score)
        await _insert_source(conn, source_b_id, "Source B", initial_score)
        # Cluster with independent_source_count=2 (two platforms)
        await _insert_cluster(conn, cluster_id, topic_id, isc=2)
        await _insert_content_item(conn, item_a_id, topic_id, source_a_id, cluster_id)
        await _insert_content_item(conn, item_b_id, topic_id, source_b_id, cluster_id)

    updated = await run_cross_verification_update(pool, topic_id)

    assert updated >= 2, f"Expected >= 2 sources boosted, got {updated}"

    async with pool.acquire() as conn:
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
async def test_cross_verification_skips_low_credibility_sources(pool):
    """Sources below credibility_high_threshold are not boosted even if in a cluster."""
    topic_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    low_score = 40.0  # below high_threshold (60.0)

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_id, "Low Credibility Source", low_score)
        await _insert_cluster(conn, cluster_id, topic_id, isc=2)
        await _insert_content_item(conn, item_id, topic_id, source_id, cluster_id)

    await run_cross_verification_update(pool, topic_id)

    async with pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score == low_score, f"Low-credibility source should not be boosted: got {score}"


# ---------------------------------------------------------------------------
# Test 3: Score is clamped to 100.0 (7.5)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_verification_clamps_score_at_100(pool):
    """A source already at 99.0 should not exceed 100.0 after boost."""
    topic_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_id, "Near-Max Source", 99.0)
        await _insert_cluster(conn, cluster_id, topic_id, isc=2)
        await _insert_content_item(conn, item_id, topic_id, source_id, cluster_id)

    await run_cross_verification_update(pool, topic_id)

    async with pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score <= 100.0, f"Score must never exceed 100.0, got {score}"


# ---------------------------------------------------------------------------
# Test 4: Contradiction drop (7.2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_contradiction_drops_high_noise_ratio_source(pool):
    """Source with >= 60% unclustered items on a topic with real clusters gets dropped."""
    topic_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    # Another source whose items go INTO the cluster (makes this a "real cluster" topic)
    anchor_source_id = str(uuid.uuid4())
    anchor_item_id = str(uuid.uuid4())

    initial_score = 60.0

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_id, "Contradicting Source", initial_score)
        await _insert_source(conn, anchor_source_id, "Anchor Source", 80.0)

        # Real cluster with item_count >= credibility_contradiction_min_items
        await _insert_cluster(conn, cluster_id, topic_id, isc=2)
        # Anchor item goes INTO the cluster
        await _insert_content_item(conn, anchor_item_id, topic_id, anchor_source_id, cluster_id)

        # Noise items from contradicting source (no cluster_id)
        for _ in range(settings.credibility_contradiction_min_items + 1):
            await _insert_content_item(
                conn, str(uuid.uuid4()), topic_id, source_id, cluster_id=None
            )

    updated = await run_contradiction_update(pool)

    assert updated >= 1, "Contradiction update should have dropped at least 1 source"

    async with pool.acquire() as conn:
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
async def test_contradiction_skips_low_noise_ratio_source(pool):
    """Source with < 60% noise items should not be penalised."""
    topic_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    cluster_id = str(uuid.uuid4())
    initial_score = 75.0

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_id, "Good Source", initial_score)
        await _insert_cluster(conn, cluster_id, topic_id, isc=2)

        # 8 clustered, 2 unclustered → noise ratio = 0.2 (below threshold 0.6)
        for _ in range(8):
            await _insert_content_item(
                conn, str(uuid.uuid4()), topic_id, source_id, cluster_id
            )
        for _ in range(2):
            await _insert_content_item(
                conn, str(uuid.uuid4()), topic_id, source_id, cluster_id=None
            )

    await run_contradiction_update(pool)

    async with pool.acquire() as conn:
        score = await _get_source_score(conn, source_id)

    assert score == initial_score, (
        f"Low noise ratio source should not be dropped: got {score}"
    )


# ---------------------------------------------------------------------------
# Test 6: Report source warnings dedup (7.6)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_source_warning_no_duplicates(pool):
    """check_source_warnings cron must not insert duplicate (report_id, source_id) rows."""
    from anveshak.reporter.db import insert_source_warning

    report_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    topic_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, source_id, "Warning Source", 50.0)

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
    await insert_source_warning(pool, report_id, source_id, "Warning Source",
                                old_score=80.0, new_score=50.0)
    await insert_source_warning(pool, report_id, source_id, "Warning Source",
                                old_score=80.0, new_score=50.0)

    async with pool.acquire() as conn:
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
async def test_list_sources_below_returns_only_low_credibility(pool):
    """list_sources_below(40) must return only sources with score < 40."""
    low_id = str(uuid.uuid4())
    high_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await _insert_source(conn, low_id, "Low Source", 25.0)
        await _insert_source(conn, high_id, "High Source", 85.0)

    from anveshak.api.db.sources import list_sources_below
    async with pool.acquire() as conn:
        results = await list_sources_below(conn, 40.0)

    result_ids = [r["id"] for r in results]
    assert low_id in result_ids, "Source with score 25 should appear in credibility_below=40"
    assert high_id not in result_ids, "Source with score 85 must not appear in credibility_below=40"


# ---------------------------------------------------------------------------
# Test 8: topic sources query (7.10) — DB-level
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_topic_sources_returns_contributing_sources(pool):
    """list_topic_sources returns only sources that have content items in the topic."""
    topic_id = str(uuid.uuid4())
    contributing_source_id = str(uuid.uuid4())
    non_contributing_source_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await _insert_topic(conn, topic_id)
        await _insert_source(conn, contributing_source_id, "Contributing", 60.0)
        await _insert_source(conn, non_contributing_source_id, "Non-Contributing", 60.0)
        await _insert_content_item(conn, item_id, topic_id, contributing_source_id)

    from anveshak.api.db.sources import list_topic_sources
    async with pool.acquire() as conn:
        results = await list_topic_sources(conn, topic_id)

    result_ids = [r["id"] for r in results]
    assert contributing_source_id in result_ids
    assert non_contributing_source_id not in result_ids

    # item_count must be present and correct
    contributing_row = next(r for r in results if r["id"] == contributing_source_id)
    assert contributing_row["item_count"] >= 1
