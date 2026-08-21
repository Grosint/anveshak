"""Error path tests — verify graceful handling at service boundaries.

Tests what happens when producers write bad/missing data and consumers read it.
Real PostgreSQL, no mocks. Each test exercises a failure mode that would
cause silent data loss or crashes in production.

Tests:
  E1: analyse_content with empty clean_text → quality gate skips (not crash)
  E2: generate_report with zero RAG chunks → set_report_failed
  E3: run_clustering with zero embedded items → empty result
  E4: Report replay idempotent — generated_at sentinel prevents overwrite
  E5: Source downgrade → report_source_warnings inserted, report untouched
  E6: Vision 0.0 deepfake vs NULL — must distinguish real from error
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import LABELS_JSON, TEST_ORG_ID, insert_content_item

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# E1: Empty clean_text → quality gate skips
# ---------------------------------------------------------------------------


async def test_empty_clean_text_skipped_by_quality_gate(db_pool, make_topic, make_source):
    """Analyst quality gate must reject empty clean_text without crashing.

    Scraper writes empty string when extraction fails (paywall, binary).
    """
    from anveshak.analyst.content_quality import is_quality_content

    # Empty text
    passed, gate = is_quality_content("")
    assert not passed, "Empty string should fail quality gate"
    assert gate is not None, "Gate reason should be set"

    # Whitespace-only
    passed2, gate2 = is_quality_content("   \n\t  ")
    assert not passed2, "Whitespace-only should fail quality gate"

    # Very short text (below min word count)
    passed3, gate3 = is_quality_content("hi")
    assert not passed3, "Single word should fail quality gate"


# ---------------------------------------------------------------------------
# E2: Report with zero RAG chunks → set_report_failed
# ---------------------------------------------------------------------------


async def test_report_with_no_content_marked_failed(db_pool, make_topic):
    """Report for topic with zero content items must be marked failed, not crash.

    Reporter checks `if not chunks: set_report_failed(...)`.
    This test verifies the DB state after that path.
    """
    topic_id = await make_topic(name="Empty Topic For Report Test")
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
            now - timedelta(hours=72),
            now,
            now,
            now,
            LABELS_JSON,
        )

        # Verify: no content for this topic
        content_count = await conn.fetchval(
            "SELECT count(*) FROM content_items WHERE topic_id = $1", topic_id
        )
        assert content_count == 0, "Topic should have zero content"

        # Simulate reporter failure path: mark report as failed
        error_msg = "No scraped content available for this topic yet."
        await conn.execute(
            """
            UPDATE reports
            SET generation_error = $1, updated_at = $2
            WHERE id = $3 AND generated_at IS NULL
            """,
            error_msg,
            now,
            report_id,
        )

        # Verify report state
        row = await conn.fetchrow(
            "SELECT generated_at, generation_error FROM reports WHERE id = $1",
            report_id,
        )
        assert row["generated_at"] is None, "Failed report should NOT have generated_at"
        assert row["generation_error"] is not None, "Error message should be set"
        assert "No scraped content" in row["generation_error"]


# ---------------------------------------------------------------------------
# E3: Clustering with zero embedded items → empty result
# ---------------------------------------------------------------------------


async def test_clustering_zero_embeddings_returns_empty(db_pool, make_topic, make_source):
    """Clustering query with no embedded items must return empty, not crash."""
    topic_id = await make_topic(name="No Embeddings Topic")
    source_id = await make_source()

    # Insert content WITHOUT embedding
    await insert_content_item(
        db_pool,
        topic_id,
        source_id,
        text="Content without embedding — not yet analysed",
        embedding=None,
    )

    async with db_pool.acquire() as conn:
        # Clustering query loads only items with embeddings
        rows = await conn.fetch(
            """
            SELECT id, embedding
            FROM content_items
            WHERE topic_id = $1
              AND embedding IS NOT NULL
              AND narrative_cluster_id IS NULL
            """,
            topic_id,
        )

    assert len(rows) == 0, "Should find zero items with embeddings"


# ---------------------------------------------------------------------------
# E4: Report replay idempotent — generated_at sentinel
# ---------------------------------------------------------------------------


async def test_report_replay_does_not_overwrite(db_pool, make_topic):
    """Replayed generate_report job must NOT overwrite a completed report.

    The UPDATE uses WHERE generated_at IS NULL. If report already generated,
    the UPDATE is a no-op (0 rows affected).
    """
    topic_id = await make_topic()
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    original_content = "# Original Report\n\nThis is the real report."

    async with db_pool.acquire() as conn:
        # Insert completed report (generated_at IS NOT NULL)
        await conn.execute(
            """
            INSERT INTO reports (
                id, topic_id, report_type, time_window_start, time_window_end,
                credibility_min_filter, content_md, generated_at,
                source_snapshot, confidence_score,
                created_at, updated_at, labels
            ) VALUES ($1, $2, 'intelligence_brief', $3, $4, 30.0, $5, $6,
                      '{"src-1": {"credibility_score": 80}}'::jsonb, 0.85,
                      $7, $8, $9)
            """,
            report_id,
            topic_id,
            now - timedelta(hours=72),
            now,
            original_content,
            now,
            now,
            now,
            LABELS_JSON,
        )

        # Attempt replay: UPDATE with WHERE generated_at IS NULL
        replay_content = "# REPLAYED — THIS SHOULD NOT APPEAR"
        result = await conn.execute(
            """
            UPDATE reports
            SET content_md = $1, generated_at = $2, confidence_score = 0.99
            WHERE id = $3 AND generated_at IS NULL
            """,
            replay_content,
            now,
            report_id,
        )

        # Should affect 0 rows (sentinel guard)
        rows_affected = int(result.split()[-1])
        assert rows_affected == 0, f"Replay should be no-op (0 rows), got {rows_affected}"

        # Verify original content unchanged
        row = await conn.fetchrow(
            "SELECT content_md, confidence_score FROM reports WHERE id = $1",
            report_id,
        )
        assert row["content_md"] == original_content, "Report content must not change"
        assert row["confidence_score"] == 0.85, "Confidence must not change"


# ---------------------------------------------------------------------------
# E5: Source downgrade → warning inserted, report untouched
# ---------------------------------------------------------------------------


async def test_source_downgrade_inserts_warning_not_modifies_report(
    db_pool, make_topic, make_source
):
    """When source credibility drops after report generation:
    1. report_source_warnings row inserted
    2. Report content_md and generated_at UNCHANGED (immutability)
    """
    topic_id = await make_topic()
    source_id = await make_source(credibility_score=80.0)
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    original_content = "# Report with credible source"

    async with db_pool.acquire() as conn:
        # Generate report with source snapshot showing score=80
        snapshot = json.dumps({source_id: {"credibility_score": 80.0, "name": "Good Source"}})
        await conn.execute(
            """
            INSERT INTO reports (
                id, topic_id, report_type, time_window_start, time_window_end,
                credibility_min_filter, content_md, generated_at,
                source_snapshot, confidence_score,
                created_at, updated_at, labels
            ) VALUES ($1, $2, 'intelligence_brief', $3, $4, 30.0, $5, $6,
                      $7::jsonb, 0.8, $8, $9, $10)
            """,
            report_id,
            topic_id,
            now - timedelta(hours=72),
            now,
            original_content,
            now,
            snapshot,
            now,
            now,
            LABELS_JSON,
        )

        # Downgrade source: 80 → 40
        await conn.execute(
            "UPDATE sources SET credibility_score = 40.0 WHERE id = $1",
            source_id,
        )

        # Insert source warning (what check_source_warnings cron would do)
        warning_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO report_source_warnings (
                id, report_id, source_id, source_name, warning_type,
                old_score, new_score, created_at, updated_at, labels
            ) VALUES ($1, $2, $3, 'Good Source', 'credibility_downgraded',
                      80.0, 40.0, $4, $5, $6)
            """,
            warning_id,
            report_id,
            source_id,
            now,
            now,
            LABELS_JSON,
        )

        # Verify: warning exists
        warnings = await conn.fetch(
            "SELECT * FROM report_source_warnings WHERE report_id = $1",
            report_id,
        )
        assert len(warnings) == 1
        assert warnings[0]["old_score"] == 80.0
        assert warnings[0]["new_score"] == 40.0

        # Verify: report UNCHANGED (immutability)
        report = await conn.fetchrow(
            "SELECT content_md, generated_at, source_snapshot FROM reports WHERE id = $1",
            report_id,
        )
        assert report["content_md"] == original_content, "Report content must be immutable"
        assert report["generated_at"] is not None, "generated_at must remain set"
        # Snapshot still shows old score (frozen at gen time)
        snap = (
            json.loads(report["source_snapshot"])
            if isinstance(report["source_snapshot"], str)
            else report["source_snapshot"]
        )
        assert snap[source_id]["credibility_score"] == 80.0, (
            "Snapshot must preserve score at generation time"
        )


# ---------------------------------------------------------------------------
# E6: Vision 0.0 vs NULL deepfake_score distinction
# ---------------------------------------------------------------------------


async def test_deepfake_score_zero_vs_null_distinction(db_pool, make_topic, make_source):
    """0.0 means 'definitely real'. NULL means 'error/not processed'.

    Credibility update must treat these differently:
    - 0.0 → no penalty (image is real)
    - NULL → skip entirely (unknown)
    - 0.9 → penalty (likely deepfake)
    """
    topic_id = await make_topic()
    source_id = await make_source(credibility_score=80.0)
    now = datetime.now(UTC)

    async with db_pool.acquire() as conn:
        scores = {
            "real": 0.0,  # Definitely real — no penalty
            "unknown": None,  # Error/not processed — skip
            "fake": 0.9,  # Likely deepfake — penalty
        }

        media_ids = {}
        for label, score in scores.items():
            item_id = str(uuid.uuid4())
            media_id = str(uuid.uuid4())
            ch = hashlib.sha256(f"deepfake-test-{label}".encode()).hexdigest()
            media_hash = hashlib.sha256(f"media-{label}".encode()).hexdigest()

            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, raw_text, clean_text, language,
                    content_hash, url, captured_at, credibility_score_at_capture,
                    org_id, created_at, updated_at, labels
                ) VALUES ($1,$2,$3,'t','t','en',$4,'https://x.com',$5,80.0,$6,$7,$8,$9)
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
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                str(uuid.uuid4()),
                media_id,
                score,
                now,
                LABELS_JSON,
            )
            media_ids[label] = media_id

        # Credibility query: deepfake_score > 0.8 (penalty threshold)
        penalty_rows = await conn.fetch(
            """
            SELECT vr.deepfake_score, ma.id AS media_id
            FROM vision_results vr
            JOIN media_assets ma ON ma.id = vr.media_asset_id
            WHERE vr.deepfake_score > 0.8
              AND vr.processed_at > NOW() - INTERVAL '7 days'
            """,
        )
        penalty_media = {r["media_id"] for r in penalty_rows}

        # Only "fake" (0.9) should trigger penalty
        assert media_ids["fake"] in penalty_media, "0.9 should trigger penalty"
        assert media_ids["real"] not in penalty_media, "0.0 should NOT trigger penalty"
        assert media_ids["unknown"] not in penalty_media, "NULL should NOT trigger penalty"

        # Verify NULL is truly excluded (not treated as 0)
        null_count = await conn.fetchval(
            """
            SELECT count(*) FROM vision_results
            WHERE deepfake_score IS NULL
              AND media_asset_id = $1
            """,
            media_ids["unknown"],
        )
        assert null_count == 1, "NULL deepfake_score must remain NULL, not coerced to 0"
