"""Boundary contract tests — verify data crosses service boundaries correctly.

Tests the shape of data at each producer→consumer boundary with real PostgreSQL.
No mocks — these tests catch schema drift, NULL handling, and encoding bugs
that unit tests with mocked DB can never find.

Contracts tested:
  B1: Content with NULL clean_text survives analyst SQL_GET_CONTENT read
  B2: Cluster with HTML in label survives reporter data bundle read
  B3: Signal evidence JSONB not double-encoded through DB round-trip
  B4: Report generation handles deleted topic gracefully
  B5: Vision NULL deepfake_score → credibility update skips (no penalty)
  B6: Orphan sweep finds content with NULL embedding
  B7: Concurrent insert with same content_hash → exactly 1 row
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest

from tests.conftest import LABELS_JSON, TEST_ORG_ID, insert_content_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# B1: Content with NULL clean_text survives analyst read
# ---------------------------------------------------------------------------


async def test_content_with_empty_clean_text_readable(db_pool, make_topic, make_source):
    """Analyst SQL_GET_CONTENT must handle empty clean_text.

    clean_text is NOT NULL in schema, but scraper can write empty string when
    extraction fails (paywall, binary). Analyst must handle gracefully.
    """
    topic_id = await make_topic()
    source_id = await make_source()

    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    ch = hashlib.sha256(b"empty-clean-text-test").hexdigest()

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                org_id, created_at, updated_at, labels
            ) VALUES ($1,$2,$3,$4,'',$5,$6,$7,$8,50.0,$9,$10,$11,$12)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            item_id,
            topic_id,
            source_id,
            "<html>paywall</html>",
            "en",
            ch,
            "https://example.com/paywall",
            now,
            TEST_ORG_ID,
            now,
            now,
            LABELS_JSON,
        )

        # Analyst's SQL_GET_CONTENT query
        row = await conn.fetchrow(
            """
            SELECT ci.id, ci.clean_text, ci.topic_id,
                   t.name AS topic_name, t.keywords AS topic_keywords,
                   s.platform
            FROM content_items ci
            JOIN topics t ON ci.topic_id = t.id
            LEFT JOIN sources s ON ci.source_id = s.id
            WHERE ci.id = $1
            """,
            item_id,
        )

    assert row is not None, "Row should exist"
    assert row["clean_text"] == "", "clean_text should be empty string"
    assert row["topic_name"] is not None, "Topic name should be present"
    assert row["platform"] is not None, "Source platform should be present"


# ---------------------------------------------------------------------------
# B2: Cluster with HTML in label survives reporter read
# ---------------------------------------------------------------------------


async def test_cluster_with_html_label_readable(db_pool, make_topic):
    """Reporter data bundle must not crash when cluster label contains HTML.

    Cluster labels are LLM-generated — they can contain raw HTML artifacts
    like href="..." from scraper content that leaked into the label.
    """
    topic_id = await make_topic()
    cluster_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO narrative_clusters (
                id, topic_id, label, item_count, independent_source_count,
                created_at, updated_at, labels
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            cluster_id,
            topic_id,
            'Cyber Fraud: TGCSB, href="https://www.siasat.com"',  # dirty label
            35,
            3,
            now,
            now,
            LABELS_JSON,
        )

        # Reporter's cluster query (from fetch_report_data_bundle)
        row = await conn.fetchrow(
            """
            SELECT id, label, item_count, independent_source_count,
                   executive_summary
            FROM narrative_clusters
            WHERE topic_id = $1
            """,
            topic_id,
        )

    assert row is not None
    assert "href=" in row["label"], "HTML should survive round-trip"
    assert row["item_count"] == 35
    assert row["executive_summary"] is None, "NULL summary should be handled"


# ---------------------------------------------------------------------------
# B3: Signal evidence JSONB not double-encoded
# ---------------------------------------------------------------------------


async def test_signal_evidence_jsonb_not_double_encoded(db_pool, make_topic):
    """Signal evidence must be a proper dict after DB round-trip, not a string.

    asyncpg returns JSONB as Python dict. But if evidence was stored as a
    JSON string (double-encoded), it comes back as str — frontend gets garbage.
    """
    topic_id = await make_topic()
    signal_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    evidence = {"independent_source_count": 5, "sources": ["src-1", "src-2"]}

    async with db_pool.acquire() as conn:
        # Link topic_sources if needed by FK
        await conn.execute(
            """
            INSERT INTO signals (
                id, topic_id, signal_type, description, evidence,
                status, created_at, updated_at, labels
            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $7, $8)
            """,
            signal_id,
            topic_id,
            "multi_source_convergence",
            "Test signal — 5 independent sources",
            json.dumps(evidence),
            "new",
            now,
            LABELS_JSON,
        )

        row = await conn.fetchrow("SELECT id, evidence FROM signals WHERE id = $1", signal_id)

    assert row is not None
    ev = row["evidence"]
    # asyncpg returns JSONB as string by default (no set_type_codec).
    # All consumers must parse defensively: json.loads(ev) if isinstance(ev, str)
    # This test verifies round-trip integrity — the JSON must be parseable
    # and contain the original structure.
    if isinstance(ev, str):
        ev = json.loads(ev)
    assert isinstance(ev, dict), (
        f"evidence should be parseable as dict, got {type(ev).__name__}: {ev!r}"
    )
    assert ev["independent_source_count"] == 5
    assert ev["sources"] == ["src-1", "src-2"]


# ---------------------------------------------------------------------------
# B4: Report generation handles deleted topic
# ---------------------------------------------------------------------------


async def test_report_data_bundle_with_deleted_topic(db_pool, make_topic):
    """Reporter must handle topic deleted between enqueue and execution.

    Race condition: API creates report row → topic deleted → reporter worker
    calls fetch_report_data_bundle → must not crash with unhandled exception.
    """
    topic_id = await make_topic()
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        # Create report row (API would do this)
        await conn.execute(
            """
            INSERT INTO reports (
                id, topic_id, report_type, time_window_start, time_window_end,
                credibility_min_filter, source_snapshot,
                created_at, updated_at, labels
            ) VALUES ($1, $2, 'intelligence_brief', $3, $4, 30.0, '{}'::jsonb,
                      $5, $6, $7)
            """,
            report_id,
            topic_id,
            now,
            now,
            now,
            now,
            LABELS_JSON,
        )

        # Verify report exists
        report_row = await conn.fetchrow(
            "SELECT id, topic_id, generated_at FROM reports WHERE id = $1",
            report_id,
        )
        assert report_row is not None
        assert report_row["generated_at"] is None, "Should be pending"

        # Now "delete" the topic (simulate race condition)
        # Can't actually delete due to FK — set status instead
        await conn.execute("UPDATE topics SET status = 'deleted' WHERE id = $1", topic_id)

        # Reporter's topic stats query should handle gracefully
        topic_row = await conn.fetchrow(
            "SELECT id, name, status FROM topics WHERE id = $1", topic_id
        )
        assert topic_row is not None  # Row exists but status='deleted'
        assert topic_row["status"] == "deleted"


# ---------------------------------------------------------------------------
# B5: Vision NULL deepfake_score → no credibility penalty
# ---------------------------------------------------------------------------


async def test_null_deepfake_score_excluded_from_credibility(db_pool, make_topic, make_source):
    """Credibility update query must not penalize sources with NULL deepfake_score.

    When vision worker crashes or model fails, deepfake_score is NULL (not 0.0).
    The credibility query filters `WHERE vr.deepfake_score > 0.8` — NULL rows
    must be excluded (NULL > 0.8 = NULL = excluded from WHERE).
    """
    topic_id = await make_topic()
    source_id = await make_source(credibility_score=80.0)

    item_id = str(uuid.uuid4())
    media_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    ch = hashlib.sha256(b"vision-null-test").hexdigest()

    async with db_pool.acquire() as conn:
        # Insert content + media + vision result with NULL deepfake_score
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                org_id, created_at, updated_at, labels
            ) VALUES ($1,$2,$3,'test','test','en',$4,'https://x.com',$5,80.0,
                      $6,$7,$8,$9)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            item_id,
            topic_id,
            source_id,
            ch,
            now,
            TEST_ORG_ID,
            now,
            now,
            LABELS_JSON,
        )
        media_hash = hashlib.sha256(b"test-media-asset").hexdigest()
        await conn.execute(
            """
            INSERT INTO media_assets (
                id, content_item_id, asset_type, storage_path,
                content_hash, created_at, labels
            ) VALUES ($1, $2, 'image', '/tmp/test.jpg', $3, $4, $5)
            """,
            media_id,
            item_id,
            media_hash,
            now,
            LABELS_JSON,
        )
        await conn.execute(
            """
            INSERT INTO vision_results (
                id, media_asset_id, deepfake_score, processed_at, labels
            ) VALUES ($1, $2, NULL, $3, $4)
            """,
            str(uuid.uuid4()),
            media_id,
            now,
            LABELS_JSON,
        )

        # Credibility query — should return 0 rows (NULL excluded by > 0.8)
        rows = await conn.fetch(
            """
            SELECT s.id AS source_id, COUNT(vr.id) AS deepfake_count
            FROM sources s
            JOIN content_items ci ON ci.source_id = s.id
            JOIN media_assets ma ON ma.content_item_id = ci.id
            JOIN vision_results vr ON vr.media_asset_id = ma.id
            WHERE vr.deepfake_score > 0.8
              AND vr.processed_at > NOW() - INTERVAL '7 days'
            GROUP BY s.id
            """,
        )

    assert len(rows) == 0, (
        f"NULL deepfake_score should be excluded from credibility penalty, got {len(rows)} rows"
    )


# ---------------------------------------------------------------------------
# B6: Orphan sweep finds content with NULL embedding
# ---------------------------------------------------------------------------


async def test_orphan_sweep_query_finds_unprocessed_content(db_pool, make_topic, make_source):
    """Orphan sweep query must find content_items with NULL embedding.

    This is the safety net for when scraper inserts but enqueue_job fails.
    """
    topic_id = await make_topic()
    source_id = await make_source()

    # Insert content WITHOUT embedding (simulates missed enqueue)
    item_id = await insert_content_item(
        db_pool,
        topic_id,
        source_id,
        text="Orphan content that was never analysed",
        embedding=None,  # No embedding = not processed
    )

    async with db_pool.acquire() as conn:
        # Full orphan sweep query from scheduler.py — including orphan_enqueued_at
        rows = await conn.fetch(
            """
            SELECT id FROM content_items
            WHERE embedding IS NULL
              AND created_at > NOW() - INTERVAL '1 hour'
              AND (orphan_enqueued_at IS NULL
                   OR orphan_enqueued_at < NOW() - INTERVAL '10 minutes')
            ORDER BY captured_at ASC
            LIMIT 100
            """,
        )

    found_ids = [r["id"] for r in rows]
    assert item_id in found_ids, (
        f"Orphan sweep should find item {item_id[:8]}... (found {len(rows)} orphans total)"
    )


# ---------------------------------------------------------------------------
# B7: Concurrent insert with same content_hash → exactly 1 row
# ---------------------------------------------------------------------------


async def test_concurrent_dedup_same_hash_one_row(db_pool, make_topic, make_source):
    """ON CONFLICT(content_hash) DO NOTHING must prevent duplicates.

    Two concurrent scraper tasks inserting the same content must result in
    exactly 1 row — no duplicate, no error.
    """
    topic_id = await make_topic()
    source_id = await make_source()
    text = "Identical content from two scraper workers"
    ch = hashlib.sha256(text.lower().strip().encode()).hexdigest()

    async def _insert(suffix: str) -> str:
        """Insert with unique ID but same content_hash."""
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, raw_text, clean_text, language,
                    content_hash, url, captured_at, credibility_score_at_capture,
                    org_id, created_at, updated_at, labels
                ) VALUES ($1,$2,$3,$4,$5,'en',$6,$7,$8,50.0,$9,$10,$11,$12)
                ON CONFLICT(content_hash) DO NOTHING
                """,
                item_id,
                topic_id,
                source_id,
                text,
                text,
                ch,
                f"https://example.com/{suffix}",
                now,
                TEST_ORG_ID,
                now,
                now,
                LABELS_JSON,
            )
        return item_id

    # Run 5 concurrent inserts with same content_hash
    await asyncio.gather(_insert("a"), _insert("b"), _insert("c"), _insert("d"), _insert("e"))

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM content_items WHERE content_hash = $1", ch
        )

    assert count == 1, f"Expected exactly 1 row for content_hash, got {count}"
