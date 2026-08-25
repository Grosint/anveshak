"""Analyst ML model integration tests — runs INSIDE the analyse-worker container.

Tests spaCy NER, sentence-transformers embedding, VADER sentiment, and NLLB
translation using the exact same code paths and models as production.
Outputs JSON to stdout for the host orchestrator (make test-integration).

Usage (from host):
    docker cp scripts/test_analyst_models.py anveshak-analyse-worker-1:/tmp/
    docker exec anveshak-analyse-worker-1 python /tmp/test_analyst_models.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

# Suppress log noise so JSON on stdout is clean
os.environ["LOG_LEVEL"] = "ERROR"


def _result(test: str, passed: bool, detail: str, elapsed: float) -> dict[str, Any]:
    return {
        "test": test,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "elapsed_s": round(elapsed, 2),
    }


def _exc_detail(exc: BaseException, limit: int = 200) -> str:
    """Format an exception as type plus message.

    Many exceptions stringify to nothing: httpx.ReadTimeout is the one that cost
    time here, since a timed-out Ollama call was reported as `"detail": ""`, with
    only the elapsed_s hinting at what happened. The type alone is diagnostic.
    """
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}"[:limit] if message else type(exc).__name__


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

SQL_ENSURE_ORG = """
    INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
    VALUES ('org-test', 'Test Org', 'test-org', NOW(), NOW(),
            '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (id) DO NOTHING
"""

SQL_INSERT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels, content_quality, clean_hash, title, org_id
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, 'org-test')
    RETURNING id
"""

SQL_ENSURE_TOPIC = """
    INSERT INTO topics (id, name, keywords, org_id, labels, created_at, updated_at)
    VALUES ($1, $2, $3, 'org-test',
            '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'::jsonb,
            NOW(), NOW())
    ON CONFLICT (id) DO NOTHING
"""

SQL_ENSURE_SOURCE = """
    INSERT INTO sources (id, name, url_or_handle, platform,
                         credibility_score, is_active, org_id, labels, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, TRUE, 'org-test',
            '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'::jsonb,
            NOW(), NOW())
    ON CONFLICT (id) DO NOTHING
"""

SQL_LINK_TOPIC_SOURCE = """
    INSERT INTO topic_sources (topic_id, source_id) VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

TEST_TOPIC_ID = "test-analyst-models-topic"
TEST_SOURCE_ID = "test-analyst-models-source"


async def _setup(pool):
    """Create test topic and source if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute(SQL_ENSURE_ORG)
        await conn.execute(
            SQL_ENSURE_TOPIC, TEST_TOPIC_ID, "Analyst Model Tests", ["test", "integration"]
        )
        await conn.execute(
            SQL_ENSURE_SOURCE,
            TEST_SOURCE_ID,
            "test-source",
            "https://example.com/test",
            "web",
            50.0,
        )
        await conn.execute(SQL_LINK_TOPIC_SOURCE, TEST_TOPIC_ID, TEST_SOURCE_ID)


def _compute_hash(text: str) -> str:
    """SHA-256 of normalised text — same algorithm as scraper/normalise.py."""
    import hashlib

    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


async def _insert_item(pool, text: str, url: str) -> str:
    item_id = str(uuid.uuid4())
    content_hash = _compute_hash(text)
    now = datetime.now(UTC)
    labels = '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'
    async with pool.acquire() as conn:
        await conn.fetchrow(
            SQL_INSERT,
            item_id,
            TEST_TOPIC_ID,
            TEST_SOURCE_ID,
            text,
            text,
            "en",
            content_hash,
            url,
            now,
            50.0,
            now,
            now,
            labels,
            "good",
            content_hash,
            "Test",
        )
    return item_id


async def _cleanup(pool, item_ids: list[str]):
    """Remove test data."""
    async with pool.acquire() as conn:
        for item_id in item_ids:
            await conn.execute("DELETE FROM extracted_entities WHERE content_item_id = $1", item_id)
            await conn.execute("DELETE FROM content_items WHERE id = $1", item_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_spacy_ner(pool) -> tuple[dict, str]:
    """spaCy NER extracts entities from intelligence-relevant English text."""
    text = (
        "General Ahmed Khan of Pakistan visited Moscow to meet with Defence Minister Shoigu. "
        "The meeting focused on bilateral agreements and arms exports to South Asia. "
        "China's PLA also expressed interest in the joint exercise programme."
    )
    item_id = await _insert_item(pool, text, f"https://example.com/ner-{uuid.uuid4()}")
    t0 = time.monotonic()
    try:
        from anveshak.analyst.jobs import analyse_content

        ctx = {"db_pool": pool}
        await analyse_content(ctx, item_id)

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM extracted_entities WHERE content_item_id = $1", item_id
            )
        elapsed = time.monotonic() - t0
        return _result(
            "spacy_ner",
            count > 0,
            f"{count} entities extracted" if count > 0 else "No entities found",
            elapsed,
        ), item_id
    except Exception as exc:
        return _result("spacy_ner", False, _exc_detail(exc), time.monotonic() - t0), item_id


async def test_embedding(pool) -> tuple[dict, str]:
    """sentence-transformers sets embedding after analysis."""
    text = (
        "Russian forces conducted exercises near the border. "
        "NATO responded with increased aerial surveillance over the Baltic region."
    )
    item_id = await _insert_item(pool, text, f"https://example.com/emb-{uuid.uuid4()}")
    t0 = time.monotonic()
    try:
        from anveshak.analyst.jobs import analyse_content

        ctx = {"db_pool": pool}
        await analyse_content(ctx, item_id)

        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT embedding FROM content_items WHERE id = $1", item_id)
        elapsed = time.monotonic() - t0
        has_embedding = row is not None and row["embedding"] is not None
        return _result(
            "embedding",
            has_embedding,
            "embedding set" if has_embedding else "embedding is NULL",
            elapsed,
        ), item_id
    except Exception as exc:
        return _result("embedding", False, _exc_detail(exc), time.monotonic() - t0), item_id


async def test_sentiment(pool) -> tuple[dict, str]:
    """VADER sentiment scores are set in content labels."""
    text = (
        "The devastating attack on the military base killed 40 soldiers. "
        "International condemnation was swift and severe."
    )
    item_id = await _insert_item(pool, text, f"https://example.com/sent-{uuid.uuid4()}")
    t0 = time.monotonic()
    try:
        from anveshak.analyst.jobs import analyse_content

        ctx = {"db_pool": pool}
        await analyse_content(ctx, item_id)

        async with pool.acquire() as conn:
            labels = await conn.fetchval("SELECT labels FROM content_items WHERE id = $1", item_id)
        elapsed = time.monotonic() - t0
        has_sentiment = labels is not None and "sentiment" in (
            json.loads(labels) if isinstance(labels, str) else labels
        )
        return _result(
            "vader_sentiment",
            has_sentiment,
            "sentiment scores in labels" if has_sentiment else "no sentiment in labels",
            elapsed,
        ), item_id
    except Exception as exc:
        return _result("vader_sentiment", False, _exc_detail(exc), time.monotonic() - t0), item_id


async def test_language_detection(pool) -> tuple[dict, str]:
    """Language field is set after analysis."""
    text = (
        "The Indian Air Force deployed Rafale jets to the eastern sector following "
        "intelligence reports of increased activity across the LAC."
    )
    item_id = await _insert_item(pool, text, f"https://example.com/lang-{uuid.uuid4()}")
    t0 = time.monotonic()
    try:
        from anveshak.analyst.jobs import analyse_content

        ctx = {"db_pool": pool}
        await analyse_content(ctx, item_id)

        async with pool.acquire() as conn:
            lang = await conn.fetchval("SELECT language FROM content_items WHERE id = $1", item_id)
        elapsed = time.monotonic() - t0
        ok = lang is not None and len(lang) >= 2
        return _result(
            "language_detection", ok, f"language={lang}" if ok else f"language={lang!r}", elapsed
        ), item_id
    except Exception as exc:
        return _result(
            "language_detection", False, _exc_detail(exc), time.monotonic() - t0
        ), item_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    import asyncpg
    from anveshak.analyst.embeddings import load_encoder

    # Load models at startup (same as production worker)
    from anveshak.analyst.nlp import load_models

    load_models()
    load_encoder()

    postgres_url = os.environ.get(
        "POSTGRES_URL", "postgresql://anveshak:anveshak@postgres:5432/anveshak"
    )
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)

    await _setup(pool)

    results = []
    item_ids = []

    for test_fn in [test_spacy_ner, test_embedding, test_sentiment, test_language_detection]:
        result, item_id = await test_fn(pool)
        results.append(result)
        item_ids.append(item_id)

    await _cleanup(pool, item_ids)
    await pool.close()

    # Output JSON to stdout
    sys.__stdout__.write(json.dumps(results, indent=2) + "\n")
    sys.__stdout__.flush()

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    sys.__stdout__.write(f"\nAnalyst models: {passed}/{total} passed\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
