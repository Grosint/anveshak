"""Integration tests: deepfake detection → credibility auto-downgrade.

Criteria 4.33: deepfake_score > 0.8 on a source → triggers credibility auto-downgrade.
Criteria 2.23: score change ALWAYS writes credibility_audit_log row.
Criteria 2.24: UPDATE + audit log INSERT in same transaction.

Requires Docker Compose with postgres + redis running.
Run with: pytest tests/integration/ -m integration
"""
import asyncio
import hashlib
import os
import uuid
from datetime import datetime, UTC

import pytest
import asyncpg


POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://anveshak:change-me-in-production@localhost:5433/anveshak")


@pytest.fixture
async def db():
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    yield pool
    await pool.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deepfake_amplifier_reduces_source_credibility(db):
    """Source with vision_results.deepfake_score > 0.8 gets credibility reduced.

    This is an integration test for the full Phase 4 → Phase 2 data flow:
      scraper/social → media_assets → vision_results → credibility_update_loop
    """
    async with db.acquire() as conn:
        # 1. Create a test source with high credibility
        source_id = str(uuid.uuid4())
        initial_credibility = 80.0
        await conn.execute("""
            INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                                 auto_score_enabled, labels)
            VALUES ($1, 'Deepfake Test Source', 'http://deepfake-test.example.com',
                    'web', $2, TRUE,
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
        """, source_id, initial_credibility)

        # 2. Create a topic and content_item from this source
        topic_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO topics (id, name, keywords, labels)
            VALUES ($1, 'Deepfake Test Topic', '{}',
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
        """, topic_id)

        ci_id = str(uuid.uuid4())
        ci_hash = hashlib.sha256(f"deepfake_test_{ci_id}".encode()).hexdigest()
        await conn.execute("""
            INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                                       content_hash, url, labels)
            VALUES ($1, $2, $3, 'deepfake test content', 'deepfake test content',
                    $4, 'http://deepfake-test.example.com/post',
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
        """, ci_id, topic_id, source_id, ci_hash)

        # 3. Create a media_asset linked to this content_item
        ma_id = str(uuid.uuid4())
        ma_hash = hashlib.sha256(f"media_bytes_{ma_id}".encode()).hexdigest()
        await conn.execute("""
            INSERT INTO media_assets (id, content_item_id, asset_type, storage_path,
                                      content_hash, labels)
            VALUES ($1, $2, 'image', '/tmp/deepfake.jpg', $3,
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
        """, ma_id, ci_id, ma_hash)

        # 4. Insert a vision_result with high deepfake_score (> 0.8 threshold)
        vr_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO vision_results (id, media_asset_id, deepfake_score, deepfake_model,
                                        processed_at, labels)
            VALUES ($1, $2, 0.92, 'facetorch:face', NOW(),
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
        """, vr_id, ma_id)

    # 5. Run the credibility update loop
    import sys
    sys.path.insert(0, "/Users/navitas28/Work/anveshak/services/analyst/src")
    from anveshak.analyst.credibility import run_credibility_update

    updated_count = await run_credibility_update(db)
    assert updated_count >= 1, (
        "Expected at least 1 source to have credibility reduced after deepfake_score > 0.8"
    )

    # 6. Verify the credibility score was reduced
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT credibility_score FROM sources WHERE id = $1", source_id
        )
        assert row["credibility_score"] < initial_credibility, (
            f"Source credibility should have been reduced below {initial_credibility}, "
            f"got {row['credibility_score']}"
        )

        # 7. Verify audit log entry was written (criteria 2.23)
        audit_row = await conn.fetchrow(
            "SELECT id, old_score, new_score, reason FROM credibility_audit_log "
            "WHERE source_id = $1 ORDER BY created_at DESC LIMIT 1",
            source_id,
        )
        assert audit_row is not None, (
            "credibility_audit_log entry must be written on every score change (CLAUDE.md rule 8)"
        )
        assert audit_row["old_score"] == initial_credibility
        assert audit_row["new_score"] < initial_credibility
        assert "deepfake" in audit_row["reason"].lower()

        # Cleanup
        await conn.execute("DELETE FROM vision_results WHERE id = $1", vr_id)
        await conn.execute("DELETE FROM media_assets WHERE id = $1", ma_id)
        await conn.execute("DELETE FROM content_items WHERE id = $1", ci_id)
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)
        await conn.execute("DELETE FROM credibility_audit_log WHERE source_id = $1", source_id)
        await conn.execute("DELETE FROM sources WHERE id = $1", source_id)
