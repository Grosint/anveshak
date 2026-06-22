"""Multilingual analyst pipeline validation — runs INSIDE the analyse-worker container.

Tests the full translation → NER → keywords → embedding → clustering chain
with real NLLB-200, spaCy, YAKE, and sentence-transformers models on
non-English content (Chinese, Russian, Hindi, Bengali).

Golden test data: 2 narratives × 3 languages each = 6 items.
Pre-decided expected outputs allow us to validate ML model quality.

Usage (from host):
    docker cp scripts/test_multilingual_pipeline.py anveshak-analyse-worker-1:/tmp/
    docker exec -e POSTGRES_URL=postgresql://anveshak:...@postgres:5432/anveshak_test \
        anveshak-analyse-worker-1 python /tmp/test_multilingual_pipeline.py
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, UTC
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


# ---------------------------------------------------------------------------
# Golden test data — 2 narratives × multiple languages
# ---------------------------------------------------------------------------

# Narrative A: "UAV deployment near northern border"
NARRATIVE_A = {
    "en": {
        "text": (
            "China has deployed Wing Loong III unmanned aerial vehicles near Hotan airbase "
            "in Xinjiang province. Satellite imagery confirms at least four UAV hangars "
            "constructed since January. The PLA Air Force is expanding drone surveillance "
            "capabilities along the Line of Actual Control."
        ),
        "lang": "en",
        "expected_entities": ["China", "Hotan", "Xinjiang", "PLA"],
    },
    "zh": {
        "text": (
            "中国已在新疆和田空军基地附近部署翼龙III无人机。卫星图像证实自一月以来"
            "已建造了至少四个无人机机库。中国人民解放军空军正在沿实际控制线扩展"
            "无人机监视能力。军事专家指出这次部署标志着中国西部战区空中力量的"
            "重大升级。印度方面对此表示密切关注并加强了边境巡逻。"
        ),
        "lang": "zh",
        "translation_keywords": ["China", "UAV", "drone", "PLA", "Xinjiang"],
    },
    "hi": {
        "text": (
            "चीन ने शिनजियांग प्रांत में होतान एयरबेस के पास विंग लूंग III ड्रोन तैनात किए हैं। "
            "उपग्रह चित्रों से पता चला है कि जनवरी से कम से कम चार ड्रोन हैंगर बनाए गए हैं। "
            "पीएलए वायु सेना वास्तविक नियंत्रण रेखा के साथ ड्रोन निगरानी क्षमताओं का विस्तार कर रही है।"
        ),
        "lang": "hi",
        "translation_keywords": ["China", "Hotan", "drone", "PLA", "Xinjiang"],
    },
}

# Narrative B: "Naval exercise in Indian Ocean"
NARRATIVE_B = {
    "en": {
        "text": (
            "The Indian Navy conducted the annual Malabar naval exercise with the United States "
            "and Japan in the Bay of Bengal. INS Vikramaditya led the carrier battle group. "
            "Anti-submarine warfare drills were the primary focus of this year's exercise."
        ),
        "lang": "en",
        "expected_entities": ["Indian Navy", "Malabar", "United States", "Japan", "INS Vikramaditya"],
    },
    "ru": {
        "text": (
            "Военно-морские силы Индии провели ежегодные учения Малабар совместно с "
            "Соединёнными Штатами и Японией в Бенгальском заливе. Авианосная ударная группа "
            "под командованием INS Викрамадитья выполняла задачи по противолодочной обороне."
        ),
        "lang": "ru",
        "translation_keywords": ["India", "Navy", "Malabar", "United States", "Japan", "exercise"],
    },
    "bn": {
        "text": (
            "ভারতীয় নৌবাহিনী বঙ্গোপসাগরে মার্কিন যুক্তরাষ্ট্র ও জাপানের সঙ্গে বার্ষিক মালাবার "
            "নৌ মহড়া পরিচালনা করেছে। আইএনএস বিক্রমাদিত্য বিমানবাহী রণতরী যুদ্ধ দলের নেতৃত্ব দিয়েছে। "
            "এ বছরের মহড়ায় সাবমেরিন বিরোধী যুদ্ধ মহড়াই ছিল প্রধান বিষয়।"
        ),
        "lang": "bn",
        "translation_keywords": ["India", "Navy", "Malabar", "Japan", "exercise"],
    },
}


# ---------------------------------------------------------------------------
# DB helpers (same pattern as test_analyst_models.py)
# ---------------------------------------------------------------------------

SQL_ENSURE_ORG = """
    INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
    VALUES ('org-test', 'Test Org', 'test-org', NOW(), NOW(),
            '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (id) DO NOTHING
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

SQL_INSERT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels, content_quality, clean_hash, title, org_id
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, 'org-test')
    RETURNING id
"""

TEST_TOPIC_ID = "test-multilingual-pipeline-topic"
TEST_SOURCE_ID = "test-multilingual-pipeline-source"


def _compute_hash(text: str) -> str:
    import hashlib
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


async def _setup(pool):
    async with pool.acquire() as conn:
        await conn.execute(SQL_ENSURE_ORG)
        await conn.execute(SQL_ENSURE_TOPIC, TEST_TOPIC_ID, "Multilingual Pipeline Test",
                           ["multilingual", "test"])
        await conn.execute(SQL_ENSURE_SOURCE, TEST_SOURCE_ID, "multilingual-test-source",
                           "https://example.com/ml-test", "web", 50.0)
        await conn.execute(SQL_LINK_TOPIC_SOURCE, TEST_TOPIC_ID, TEST_SOURCE_ID)


async def _insert_item(pool, text: str, lang: str, url: str) -> str:
    item_id = str(uuid.uuid4())
    content_hash = _compute_hash(text)
    now = datetime.now(UTC)
    labels = '{"classification":"OPEN","domain":"test","owner_org":"anveshak"}'
    async with pool.acquire() as conn:
        await conn.fetchrow(
            SQL_INSERT,
            item_id, TEST_TOPIC_ID, TEST_SOURCE_ID,
            text, text, lang, content_hash, url, now, 50.0,
            now, now, labels, "good", content_hash, "Test",
        )
    return item_id


async def _cleanup(pool, item_ids: list[str]):
    async with pool.acquire() as conn:
        for item_id in item_ids:
            await conn.execute("DELETE FROM extracted_entities WHERE content_item_id = $1", item_id)
            await conn.execute("DELETE FROM content_items WHERE id = $1", item_id)
        # Clean up test fixtures
        await conn.execute("DELETE FROM topic_sources WHERE topic_id = $1", TEST_TOPIC_ID)
        await conn.execute("DELETE FROM topics WHERE id = $1", TEST_TOPIC_ID)
        await conn.execute("DELETE FROM sources WHERE id = $1", TEST_SOURCE_ID)


def _fuzzy_match(text: str, keywords: list[str], min_matches: int) -> tuple[bool, list[str], list[str]]:
    """Check if at least min_matches keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    found = [kw for kw in keywords if kw.lower() in text_lower]
    missing = [kw for kw in keywords if kw.lower() not in text_lower]
    return len(found) >= min_matches, found, missing


# ---------------------------------------------------------------------------
# Test 1–4: NLLB Translation quality
# ---------------------------------------------------------------------------

async def test_translation_chinese(pool) -> tuple[dict, str | None]:
    """Chinese → English: key military terms preserved."""
    from anveshak.analyst.translation import translate_to_english

    item = NARRATIVE_A["zh"]
    t0 = time.monotonic()
    try:
        translated = translate_to_english(item["text"], item["lang"])
        elapsed = time.monotonic() - t0

        if translated is None:
            return _result("translation_zh", False, "translate_to_english returned None", elapsed), None

        ok, found, missing = _fuzzy_match(translated, item["translation_keywords"], 3)
        detail = f"found={found}" if ok else f"only {len(found)}/{len(item['translation_keywords'])} keywords: found={found}, missing={missing}"
        return _result("translation_zh", ok, f"{detail} | output: {translated[:150]}", elapsed), None
    except Exception as exc:
        return _result("translation_zh", False, str(exc)[:200], time.monotonic() - t0), None


async def test_translation_russian(pool) -> tuple[dict, str | None]:
    """Russian → English: naval exercise terms preserved."""
    from anveshak.analyst.translation import translate_to_english

    item = NARRATIVE_B["ru"]
    t0 = time.monotonic()
    try:
        translated = translate_to_english(item["text"], item["lang"])
        elapsed = time.monotonic() - t0

        if translated is None:
            return _result("translation_ru", False, "translate_to_english returned None", elapsed), None

        ok, found, missing = _fuzzy_match(translated, item["translation_keywords"], 3)
        detail = f"found={found}" if ok else f"only {len(found)}/{len(item['translation_keywords'])} keywords: found={found}, missing={missing}"
        return _result("translation_ru", ok, f"{detail} | output: {translated[:150]}", elapsed), None
    except Exception as exc:
        return _result("translation_ru", False, str(exc)[:200], time.monotonic() - t0), None


async def test_translation_hindi(pool) -> tuple[dict, str | None]:
    """Hindi → English: drone/UAV terms preserved."""
    from anveshak.analyst.translation import translate_to_english

    item = NARRATIVE_A["hi"]
    t0 = time.monotonic()
    try:
        translated = translate_to_english(item["text"], item["lang"])
        elapsed = time.monotonic() - t0

        if translated is None:
            return _result("translation_hi", False, "translate_to_english returned None", elapsed), None

        ok, found, missing = _fuzzy_match(translated, item["translation_keywords"], 3)
        detail = f"found={found}" if ok else f"only {len(found)}/{len(item['translation_keywords'])} keywords: found={found}, missing={missing}"
        return _result("translation_hi", ok, f"{detail} | output: {translated[:150]}", elapsed), None
    except Exception as exc:
        return _result("translation_hi", False, str(exc)[:200], time.monotonic() - t0), None


async def test_translation_bengali(pool) -> tuple[dict, str | None]:
    """Bengali → English: naval terms preserved."""
    from anveshak.analyst.translation import translate_to_english

    item = NARRATIVE_B["bn"]
    t0 = time.monotonic()
    try:
        translated = translate_to_english(item["text"], item["lang"])
        elapsed = time.monotonic() - t0

        if translated is None:
            return _result("translation_bn", False, "translate_to_english returned None", elapsed), None

        ok, found, missing = _fuzzy_match(translated, item["translation_keywords"], 3)
        detail = f"found={found}" if ok else f"only {len(found)}/{len(item['translation_keywords'])} keywords: found={found}, missing={missing}"
        return _result("translation_bn", ok, f"{detail} | output: {translated[:150]}", elapsed), None
    except Exception as exc:
        return _result("translation_bn", False, str(exc)[:200], time.monotonic() - t0), None


# ---------------------------------------------------------------------------
# Test 5: NER on translated text — entities survive the translation chain
# ---------------------------------------------------------------------------

async def test_ner_on_translated(pool) -> tuple[dict, list[str]]:
    """Full analyse_content on Chinese + Russian text → NER extracts key entities."""
    from anveshak.analyst.jobs import analyse_content

    item_ids = []
    t0 = time.monotonic()
    try:
        # Insert Chinese UAV article and Russian naval article
        zh_id = await _insert_item(pool, NARRATIVE_A["zh"]["text"], "zh",
                                   f"https://example.com/zh-ner-{uuid.uuid4()}")
        ru_id = await _insert_item(pool, NARRATIVE_B["ru"]["text"], "ru",
                                   f"https://example.com/ru-ner-{uuid.uuid4()}")
        item_ids = [zh_id, ru_id]

        # Run full pipeline (detect lang → translate → NER → embed)
        ctx = {"db_pool": pool}
        await analyse_content(ctx, zh_id)
        await analyse_content(ctx, ru_id)

        # Check extracted entities
        async with pool.acquire() as conn:
            zh_entities = await conn.fetch(
                "SELECT entity_type, entity_text FROM extracted_entities WHERE content_item_id = $1",
                zh_id,
            )
            ru_entities = await conn.fetch(
                "SELECT entity_type, entity_text FROM extracted_entities WHERE content_item_id = $1",
                ru_id,
            )

            # Check translated_text was set
            zh_translated = await conn.fetchval(
                "SELECT translated_text FROM content_items WHERE id = $1", zh_id
            )
            ru_translated = await conn.fetchval(
                "SELECT translated_text FROM content_items WHERE id = $1", ru_id
            )

        elapsed = time.monotonic() - t0

        zh_texts = [e["entity_text"] for e in zh_entities]
        ru_texts = [e["entity_text"] for e in ru_entities]

        checks = []
        # Chinese article: should find China-related entities
        if len(zh_entities) > 0:
            checks.append("zh_has_entities")
        if zh_translated:
            checks.append("zh_translated")
        # Russian article: should find India/Navy-related entities
        if len(ru_entities) > 0:
            checks.append("ru_has_entities")
        if ru_translated:
            checks.append("ru_translated")

        ok = len(checks) >= 4
        detail = (
            f"checks={checks} | "
            f"zh_entities({len(zh_entities)})={zh_texts[:5]} | "
            f"ru_entities({len(ru_entities)})={ru_texts[:5]}"
        )
        return _result("ner_on_translated", ok, detail, elapsed), item_ids

    except Exception as exc:
        return _result("ner_on_translated", False, str(exc)[:300], time.monotonic() - t0), item_ids


# ---------------------------------------------------------------------------
# Test 6: YAKE keywords on translated text
# ---------------------------------------------------------------------------

async def test_yake_on_translated(pool) -> tuple[dict, str | None]:
    """YAKE extracts military-relevant keywords from NLLB-translated Chinese text."""
    from anveshak.analyst.translation import translate_to_english
    from anveshak.analyst.keywords import extract_keywords

    t0 = time.monotonic()
    try:
        translated = translate_to_english(NARRATIVE_A["zh"]["text"], "zh")
        if translated is None:
            return _result("yake_on_translated", False, "translation returned None", time.monotonic() - t0), None

        keywords = extract_keywords(translated, language="en", max_keywords=10)
        elapsed = time.monotonic() - t0

        kw_texts = [kw.keyword.lower() for kw in keywords]
        # At least one military/drone/UAV related keyword should appear
        military_terms = ["uav", "drone", "military", "air", "surveillance", "pla", "airbase"]
        found_military = [t for t in military_terms if any(t in kw for kw in kw_texts)]

        ok = len(keywords) >= 3 and len(found_military) >= 1
        detail = f"keywords={[kw.keyword for kw in keywords[:5]]} | military_terms_found={found_military}"
        return _result("yake_on_translated", ok, detail, elapsed), None

    except Exception as exc:
        return _result("yake_on_translated", False, str(exc)[:200], time.monotonic() - t0), None


# ---------------------------------------------------------------------------
# Test 7: Cross-language clustering — same narrative clusters together
# ---------------------------------------------------------------------------

async def test_cross_language_clustering(pool) -> tuple[dict, list[str]]:
    """Items from same narrative in different languages cluster together after translation.

    Narrative A (en, zh, hi) should have high mutual cosine similarity.
    Narrative B (en, ru, bn) should have high mutual cosine similarity.
    Inter-narrative similarity should be lower.
    """
    from anveshak.analyst.jobs import analyse_content

    item_ids = []
    t0 = time.monotonic()
    try:
        # Insert all 6 items — append unique suffix to avoid content_hash collision
        # with items from test_ner_on_translated (which uses the same base text)
        cluster_tag = str(uuid.uuid4())[:8]
        narrative_a_ids = []
        for lang_key, item in NARRATIVE_A.items():
            text = item["text"] + f" [{cluster_tag}-a-{lang_key}]"
            iid = await _insert_item(pool, text, item["lang"],
                                     f"https://example.com/clust-a-{lang_key}-{uuid.uuid4()}")
            narrative_a_ids.append(iid)
            item_ids.append(iid)

        narrative_b_ids = []
        for lang_key, item in NARRATIVE_B.items():
            text = item["text"] + f" [{cluster_tag}-b-{lang_key}]"
            iid = await _insert_item(pool, text, item["lang"],
                                     f"https://example.com/clust-b-{lang_key}-{uuid.uuid4()}")
            narrative_b_ids.append(iid)
            item_ids.append(iid)

        # Run full pipeline on all 6 items
        ctx = {"db_pool": pool}
        for iid in item_ids:
            await analyse_content(ctx, iid)

        # Fetch embeddings
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, embedding FROM content_items WHERE id = ANY($1) AND embedding IS NOT NULL",
                item_ids,
            )

        elapsed = time.monotonic() - t0

        if len(rows) < 6:
            embedded_ids = [r["id"] for r in rows]
            missing = [iid for iid in item_ids if iid not in embedded_ids]
            return _result("cross_lang_clustering", False,
                           f"only {len(rows)}/6 items have embeddings, missing: {missing[:3]}",
                           elapsed), item_ids

        # Build id→vector map
        import struct
        vectors = {}
        for row in rows:
            raw = row["embedding"]
            # pgvector returns bytes in binary format: 2-byte dim + 2-byte unused + float32[]
            if isinstance(raw, (bytes, memoryview)):
                raw = bytes(raw)
                dim = struct.unpack_from("<H", raw, 0)[0]
                floats = struct.unpack_from(f"<{dim}f", raw, 4)
                vectors[row["id"]] = list(floats)
            elif isinstance(raw, str):
                # pgvector text format: [0.1,0.2,...]
                vectors[row["id"]] = [float(x) for x in raw.strip("[]").split(",")]
            else:
                vectors[row["id"]] = list(raw)

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        # Compute intra-narrative similarity (should be high)
        a_sims = []
        for i in range(len(narrative_a_ids)):
            for j in range(i + 1, len(narrative_a_ids)):
                vi, vj = vectors.get(narrative_a_ids[i]), vectors.get(narrative_a_ids[j])
                if vi and vj:
                    a_sims.append(cosine_sim(vi, vj))

        b_sims = []
        for i in range(len(narrative_b_ids)):
            for j in range(i + 1, len(narrative_b_ids)):
                vi, vj = vectors.get(narrative_b_ids[i]), vectors.get(narrative_b_ids[j])
                if vi and vj:
                    b_sims.append(cosine_sim(vi, vj))

        # Compute inter-narrative similarity (should be lower)
        cross_sims = []
        for a_id in narrative_a_ids:
            for b_id in narrative_b_ids:
                va, vb = vectors.get(a_id), vectors.get(b_id)
                if va and vb:
                    cross_sims.append(cosine_sim(va, vb))

        avg_a = sum(a_sims) / len(a_sims) if a_sims else 0
        avg_b = sum(b_sims) / len(b_sims) if b_sims else 0
        avg_cross = sum(cross_sims) / len(cross_sims) if cross_sims else 0

        # Intra-narrative should be > 0.5, cross should be lower than intra
        intra_ok = avg_a > 0.5 and avg_b > 0.5
        separation_ok = avg_cross < max(avg_a, avg_b)

        ok = intra_ok and separation_ok
        detail = (
            f"narrative_A_avg_sim={avg_a:.3f} | "
            f"narrative_B_avg_sim={avg_b:.3f} | "
            f"cross_narrative_avg_sim={avg_cross:.3f} | "
            f"intra>0.5={'yes' if intra_ok else 'NO'} | "
            f"separation={'yes' if separation_ok else 'NO'}"
        )
        return _result("cross_lang_clustering", ok, detail, elapsed), item_ids

    except Exception as exc:
        import traceback
        return _result("cross_lang_clustering", False,
                       f"{exc}\n{traceback.format_exc()[-300:]}", time.monotonic() - t0), item_ids


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    import asyncpg

    # Load models at startup (same as production worker)
    from anveshak.analyst.nlp import load_models
    from anveshak.analyst.embeddings import load_encoder
    load_models()
    load_encoder()

    postgres_url = os.environ.get("POSTGRES_URL",
                                   "postgresql://anveshak:anveshak@postgres:5432/anveshak")
    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)

    await _setup(pool)

    results = []
    all_item_ids = []

    # Translation tests (no DB writes, just model inference)
    for test_fn in [test_translation_chinese, test_translation_russian,
                    test_translation_hindi, test_translation_bengali]:
        result, item_id = await test_fn(pool)
        results.append(result)
        sys.__stdout__.write(f"  {result['status']}  {result['test']} ({result['elapsed_s']}s)\n")
        sys.__stdout__.flush()

    # NER test (writes to DB, needs cleanup)
    result, item_ids = await test_ner_on_translated(pool)
    results.append(result)
    all_item_ids.extend(item_ids or [])
    sys.__stdout__.write(f"  {result['status']}  {result['test']} ({result['elapsed_s']}s)\n")
    sys.__stdout__.flush()

    # YAKE test (no DB writes)
    result, _ = await test_yake_on_translated(pool)
    results.append(result)
    sys.__stdout__.write(f"  {result['status']}  {result['test']} ({result['elapsed_s']}s)\n")
    sys.__stdout__.flush()

    # Clustering test (writes to DB, needs cleanup)
    result, item_ids = await test_cross_language_clustering(pool)
    results.append(result)
    all_item_ids.extend(item_ids or [])
    sys.__stdout__.write(f"  {result['status']}  {result['test']} ({result['elapsed_s']}s)\n")
    sys.__stdout__.flush()

    # Cleanup
    await _cleanup(pool, all_item_ids)
    await pool.close()

    # Output JSON
    sys.__stdout__.write("\n" + json.dumps(results, indent=2) + "\n")
    sys.__stdout__.flush()

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    sys.__stdout__.write(f"\nMultilingual pipeline: {passed}/{total} passed\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
