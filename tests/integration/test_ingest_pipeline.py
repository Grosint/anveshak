"""Integration test: full scrape → DB → analyst → embedding stored (criteria 1.33, 1.34).

pytest.mark.integration — requires running Docker Compose services:
  make up

Run with:
  uv run --package anveshak-tests pytest tests/integration/ -v -m integration
"""
from __future__ import annotations

import pytest

from tests.conftest import insert_content_item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_hash_deduplication(db_pool, make_topic, make_source):
    """Criteria 1.26: same content scraped twice → exactly ONE row."""
    from anveshak.scraper.normalise import compute_content_hash

    topic_id = await make_topic(name="Integration Test Topic")
    source_id = await make_source(name="Test Source", url_or_handle="https://example.com")

    text = "This is a test article about defence procurement. " * 5
    content_hash = compute_content_hash(text)

    # Insert twice
    await insert_content_item(
        db_pool, topic_id, source_id, text, content_hash, "https://example.com/a1"
    )
    await insert_content_item(
        db_pool, topic_id, source_id, text, content_hash, "https://example.com/a2"
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM content_items WHERE content_hash = $1", content_hash
        )

    assert count == 1, "Duplicate content_hash must produce exactly one row"



# NOTE: test_analyst_sets_embedding, test_extracted_entities_exist, and
# test_language_not_null_after_analysis have been moved to
# scripts/test_analyst_models.py (runs inside analyst-worker container
# where spaCy and sentence-transformers are installed).
# They execute as part of `make test-integration` step 2/4.
