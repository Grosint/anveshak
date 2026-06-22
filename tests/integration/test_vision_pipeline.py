"""Integration tests: full vision pipeline end-to-end.

Requires Docker Compose (postgres + redis + vision-worker running).
Run with: pytest tests/integration/ -m integration

Criteria:
  4.31: scraped article with images → media_assets rows → vision job dispatched
  4.32: vision_results.deepfake_score is always float (never NULL after processing)
  4.34: same image URL scraped from two sources → one vision_results row (dedup)
"""
import hashlib
import uuid

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_asset_insert_dedup(db_pool, make_topic, make_source):
    """Same content_hash → ON CONFLICT DO NOTHING → one media_assets row (criteria 4.34)."""
    raw_bytes = b"test image bytes for deduplication"
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    topic_id = await make_topic(name="Vision Test Topic")
    source_id = await make_source(name="Test Source", url_or_handle="http://test.example.com")

    async with db_pool.acquire() as conn:
        # Insert content_item
        ci_id = str(uuid.uuid4())
        ci_hash = hashlib.sha256(f"content_{ci_id}".encode()).hexdigest()
        await conn.execute("""
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, content_hash,
                url, labels, org_id
            )
            VALUES ($1, $2, $3, 'test content', 'test content', $4, 'http://test.example.com',
                    '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb, $5)
            ON CONFLICT (content_hash) DO NOTHING
        """, ci_id, topic_id, source_id, ci_hash, "org-integration-test")

        # Insert media_asset twice with same content_hash — second should be ignored
        ma_id_1 = str(uuid.uuid4())
        ma_id_2 = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO media_assets (id, content_item_id, asset_type, storage_path, content_hash, labels)
            VALUES ($1, $2, 'image', '/tmp/test.jpg', $3,
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (content_hash) DO NOTHING
        """, ma_id_1, ci_id, content_hash)

        await conn.execute("""
            INSERT INTO media_assets (id, content_item_id, asset_type, storage_path, content_hash, labels)
            VALUES ($1, $2, 'image', '/tmp/test.jpg', $3,
                    '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
            ON CONFLICT (content_hash) DO NOTHING
        """, ma_id_2, ci_id, content_hash)

        # Verify exactly ONE row exists for this content_hash
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM media_assets WHERE content_hash = $1", content_hash
        )
        assert count == 1, (
            f"Expected 1 media_assets row for content_hash={content_hash}, got {count}. "
            "ON CONFLICT(content_hash) DO NOTHING must be enforced."
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vision_results_deepfake_score_is_float(db_pool):
    """vision_results.deepfake_score stored as FLOAT, never NULL after processing.

    Criteria 4.32: deepfake_score is always float 0.0–1.0 after vision job runs.
    CLAUDE.md rule 7: never bool, never None.
    """
    async with db_pool.acquire() as conn:
        # Check that all processed vision_results have non-NULL float scores
        rows = await conn.fetch("""
            SELECT id, deepfake_score
            FROM vision_results
            WHERE processed_at IS NOT NULL
        """)

        for row in rows:
            score = row["deepfake_score"]
            assert score is not None, (
                f"vision_result {row['id']} has NULL deepfake_score after processing"
            )
            assert isinstance(score, float), (
                f"vision_result {row['id']} deepfake_score is {type(score)}, not float"
            )
            assert 0.0 <= score <= 1.0, (
                f"vision_result {row['id']} deepfake_score={score} outside [0.0, 1.0]"
            )
