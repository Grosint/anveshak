"""Integration tests: deepfake detection → credibility auto-downgrade.

Criteria 4.33: deepfake_score > 0.8 on a source → triggers credibility auto-downgrade.
Criteria 2.23: score change ALWAYS writes credibility_audit_log row.
Criteria 2.24: UPDATE + audit log INSERT in same transaction.

Requires Docker Compose with postgres + redis running.
Run with: pytest tests/integration/ -m integration
"""

import hashlib
import uuid

import pytest

from tests.conftest import LABELS_JSON


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deepfake_amplifier_reduces_source_credibility(db_pool, make_topic, make_source):
    """Source with vision_results.deepfake_score > 0.8 gets credibility reduced.

    This is an integration test for the full Phase 4 → Phase 2 data flow:
      scraper/social → media_assets → vision_results → credibility_update_loop
    """
    topic_id = await make_topic(name="Deepfake Test Topic")
    source_id = await make_source(
        name="Deepfake Test Source",
        url_or_handle="http://deepfake-test.example.com",
        credibility_score=80.0,
    )
    initial_credibility = 80.0

    async with db_pool.acquire() as conn:
        # Enable auto-scoring on the source
        await conn.execute("UPDATE sources SET auto_score_enabled = TRUE WHERE id = $1", source_id)

        # Create a content_item from this source
        ci_id = str(uuid.uuid4())
        ci_hash = hashlib.sha256(f"deepfake_test_{ci_id}".encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO content_items (id, topic_id, source_id, raw_text, clean_text,
                                       content_hash, url, labels, org_id)
            VALUES ($1, $2, $3, 'deepfake test content', 'deepfake test content',
                    $4, 'http://deepfake-test.example.com/post',
                    $5::jsonb, $6)
        """,
            ci_id,
            topic_id,
            source_id,
            ci_hash,
            LABELS_JSON,
            "org-integration-test",
        )

        # Create a media_asset linked to this content_item
        ma_id = str(uuid.uuid4())
        ma_hash = hashlib.sha256(f"media_bytes_{ma_id}".encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO media_assets (id, content_item_id, asset_type, storage_path,
                                      content_hash, labels)
            VALUES ($1, $2, 'image', '/tmp/deepfake.jpg', $3, $4::jsonb)
        """,
            ma_id,
            ci_id,
            ma_hash,
            LABELS_JSON,
        )

        # Insert a vision_result with high deepfake_score (> 0.8 threshold)
        vr_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO vision_results (id, media_asset_id, deepfake_score, deepfake_model,
                                        processed_at, labels)
            VALUES ($1, $2, 0.92, 'facetorch:face', NOW(), $3::jsonb)
        """,
            vr_id,
            ma_id,
            LABELS_JSON,
        )

    # Run the credibility update loop
    from anveshak.analyst.credibility import run_credibility_update

    updated_count = await run_credibility_update(db_pool)
    assert updated_count >= 1, (
        "Expected at least 1 source to have credibility reduced after deepfake_score > 0.8"
    )

    # Verify the credibility score was reduced
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT credibility_score FROM sources WHERE id = $1", source_id)
        assert row["credibility_score"] < initial_credibility, (
            f"Source credibility should have been reduced below {initial_credibility}, "
            f"got {row['credibility_score']}"
        )

        # Verify audit log entry was written (criteria 2.23)
        audit_row = await conn.fetchrow(
            "SELECT id, old_score, new_score, reason FROM credibility_audit_log "
            "WHERE source_id = $1 ORDER BY created_at DESC LIMIT 1",
            source_id,
        )
        assert audit_row is not None, (
            "credibility_audit_log entry must be written on every score change (AGENTS.md rule 8)"
        )
        assert audit_row["old_score"] == initial_credibility
        assert audit_row["new_score"] < initial_credibility
        assert "deepfake" in audit_row["reason"].lower()
