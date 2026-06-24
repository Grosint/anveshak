#!/usr/bin/env python3
"""Generate a leave-behind PDF for the Cyber Fraud topic — Nagaland Police DIG demo.

This is the SECOND leave-behind. The first covers Nagaland Social Media Monitoring.
This one showcases Engine C identifier intelligence on live cyber fraud Telegram data.

    docker cp scripts/gen_cyber_fraud_leave_behind.py anveshak-report-worker-1:/tmp/
    docker exec anveshak-report-worker-1 python /tmp/gen_cyber_fraud_leave_behind.py
    docker cp anveshak-report-worker-1:/tmp/cyber_fraud_leave_behind.pdf .
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timezone

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:anveshak@postgres:5432/anveshak",
)
TOPIC_ID = "b52d8425-4809-4ec7-83fd-821a440f7087"
OUTPUT_PATH = "/tmp/cyber_fraud_leave_behind.pdf"


async def main() -> None:
    import asyncpg

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
    assert pool is not None

    async with pool.acquire() as conn:
        # ── Topic ──
        topic = await conn.fetchrow(
            "SELECT name, keywords FROM topics WHERE id = $1", TOPIC_ID
        )
        assert topic, f"Topic {TOPIC_ID} not found"

        # ── Stats ──
        stats = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM content_items WHERE topic_id = $1) AS content_count,
                (SELECT COUNT(DISTINCT source_id) FROM content_items WHERE topic_id = $1) AS source_count,
                (SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1) AS cluster_count,
                (SELECT COUNT(*) FROM signals WHERE topic_id = $1) AS signal_count,
                (SELECT MIN(captured_at) FROM content_items WHERE topic_id = $1) AS earliest,
                (SELECT MAX(captured_at) FROM content_items WHERE topic_id = $1) AS latest
        """, TOPIC_ID)

        # ── Sources ──
        source_rows = await conn.fetch("""
            SELECT s.name, s.platform,
                   CASE WHEN s.credibility_score = 0 THEN NULL
                        ELSE s.credibility_score END AS credibility_score,
                   COUNT(ci.id) AS item_count
            FROM sources s
            JOIN topic_sources ts ON ts.source_id = s.id AND ts.topic_id = $1
            LEFT JOIN content_items ci ON ci.source_id = s.id AND ci.topic_id = $1
            GROUP BY s.id, s.name, s.platform, s.credibility_score
            ORDER BY item_count DESC
        """, TOPIC_ID)
        sources = []
        for r in source_rows:
            d = dict(r)
            if d["credibility_score"] is None:
                d["credibility_score"] = 0
            sources.append(d)

        # ── Clusters ──
        cluster_rows = await conn.fetch("""
            SELECT label, item_count, independent_source_count, executive_summary
            FROM narrative_clusters
            WHERE topic_id = $1 AND independent_source_count >= 1
            ORDER BY independent_source_count DESC, item_count DESC
            LIMIT 10
        """, TOPIC_ID)
        clusters = [dict(r) for r in cluster_rows]

        # ── Signals ──
        signal_rows = await conn.fetch("""
            SELECT s.signal_type, s.description, s.status, s.created_at
            FROM signals s
            WHERE s.topic_id = $1
              AND s.description NOT ILIKE '%URL_DOMAIN%'
            ORDER BY s.created_at DESC
            LIMIT 15
        """, TOPIC_ID)
        _CLUSTER_NAME_RE = re.compile(r"Cluster '([^']+)'")
        _IDENT_RE = re.compile(r"Identifier (\S+) '([^']+)'")
        signals = []
        for r in signal_rows:
            d = dict(r)
            desc = d["description"] or ""
            m = _CLUSTER_NAME_RE.search(desc)
            if m:
                d["cluster_label"] = m.group(1)
            else:
                m2 = _IDENT_RE.search(desc)
                d["cluster_label"] = f"{m2.group(1)}: {m2.group(2)}" if m2 else "—"
            signals.append(d)

        # ── Identifiers — the star of this report ──
        # Phone numbers (HK, China, India)
        phone_rows = await conn.fetch("""
            SELECT identifier_type, identifier_value, source_count, content_item_count
            FROM identifier_clusters
            WHERE topic_id = $1
              AND identifier_type IN ('PHONE_INTL', 'PHONE_IN')
            ORDER BY content_item_count DESC
            LIMIT 20
        """, TOPIC_ID)

        # Telegram handles
        handle_rows = await conn.fetch("""
            SELECT identifier_type, identifier_value, source_count, content_item_count
            FROM identifier_clusters
            WHERE topic_id = $1
              AND identifier_type = 'TELEGRAM_HANDLE'
            ORDER BY content_item_count DESC
            LIMIT 20
        """, TOPIC_ID)

        # Combine into identifiers list, phones first
        identifiers = [dict(r) for r in phone_rows] + [dict(r) for r in handle_rows]

        # ── Identifier summary stats for BLUF ──
        ident_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE identifier_type = 'PHONE_INTL' AND identifier_value LIKE '+852%') AS hk_phones,
                COUNT(*) FILTER (WHERE identifier_type = 'PHONE_INTL' AND identifier_value LIKE '+86%') AS cn_phones,
                COUNT(*) FILTER (WHERE identifier_type = 'PHONE_IN') AS in_phones,
                COUNT(*) FILTER (WHERE identifier_type = 'TELEGRAM_HANDLE') AS tg_handles,
                COUNT(*) AS total_identifiers
            FROM identifier_clusters
            WHERE topic_id = $1
        """, TOPIC_ID)

        # ── Top entities ──
        entity_rows = await conn.fetch("""
            SELECT ee.entity_type,
                   INITCAP(LOWER(ee.entity_text)) AS entity_text,
                   SUM(cnt) AS mention_count
            FROM (
                SELECT ee.entity_type, ee.entity_text, COUNT(*) AS cnt
                FROM extracted_entities ee
                JOIN content_items ci ON ci.id = ee.content_item_id
                WHERE ci.topic_id = $1
                  AND ee.entity_type IN ('ORG', 'PERSON', 'GPE', 'EVENT')
                  AND LENGTH(ee.entity_text) > 2
                GROUP BY ee.entity_type, ee.entity_text
            ) ee
            GROUP BY ee.entity_type, INITCAP(LOWER(ee.entity_text))
            HAVING SUM(cnt) >= 2
            ORDER BY mention_count DESC
            LIMIT 15
        """, TOPIC_ID)
        entities = [dict(r) for r in entity_rows]

        # ── Language breakdown ──
        _LANG_NAMES = {
            "en": "English", "hi": "Hindi", "zh": "Chinese", "ar": "Arabic",
            "id": "Indonesian", "tl": "Tagalog", "mr": "Marathi",
        }
        lang_rows = await conn.fetch("""
            SELECT COALESCE(language, 'unknown') AS language, COUNT(*) AS count
            FROM content_items
            WHERE topic_id = $1 AND language IS NOT NULL
            GROUP BY language
            ORDER BY count DESC
        """, TOPIC_ID)
        language_breakdown = []
        for r in lang_rows:
            code = r["language"]
            language_breakdown.append({
                "language": _LANG_NAMES.get(code, code),
                "count": r["count"],
            })

        # ── Evidence items — sample from fraud content ──
        evidence_rows = await conn.fetch("""
            SELECT ci.clean_text, ci.url, ci.captured_at, ci.credibility_score_at_capture,
                   s.name AS source_name, s.platform
            FROM content_items ci
            JOIN sources s ON s.id = ci.source_id
            WHERE ci.topic_id = $1
              AND LENGTH(ci.clean_text) > 50
            ORDER BY ci.captured_at DESC
            LIMIT 15
        """, TOPIC_ID)
        evidence_items = []
        for r in evidence_rows:
            text = r["clean_text"] or ""
            evidence_items.append({
                "title": "Cyber Fraud Content",
                "snippet": text[:300] + ("..." if len(text) > 300 else ""),
                "url": r["url"] or "",
                "captured_at": str(r["captured_at"]),
                "credibility_score_at_capture": r["credibility_score_at_capture"] or 0,
                "source_name": r["source_name"],
                "platform": r["platform"],
            })

        # ── Keyword frequency ──
        keywords_list = topic["keywords"] or []
        keyword_stats = []
        for kw in keywords_list[:10]:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM content_items "
                "WHERE topic_id = $1 AND clean_text ILIKE $2",
                TOPIC_ID, f"%{kw}%",
            )
            keyword_stats.append({
                "keyword": kw,
                "frequency": count_row["cnt"] if count_row else 0,
            })
        keyword_stats.sort(key=lambda x: x["frequency"], reverse=True)

    await pool.close()

    # ── Build report data bundle ──
    now = datetime.now(timezone.utc)
    report_data = {
        "id": "cyber-fraud-leave-behind-001",
        "topic_name": "Cyber Fraud Financial — Identifier Intelligence Report",
        "report_type": "research_summary",
        "generated_at": now.isoformat(),
        "confidence_score": 0.85,
        "content_item_count": stats["content_count"],
        "labels": {"classification": "RESTRICTED", "domain": "cyber_fraud"},
        "topic_stats": {
            "content_count": stats["content_count"],
            "source_count": stats["source_count"],
            "cluster_count": stats["cluster_count"],
            "signal_count": stats["signal_count"],
        },
        "bluf": (
            f"Automated monitoring of {stats['content_count']} messages from "
            f"{stats['source_count']} Telegram channels reveals an active cross-border "
            "cyber fraud network operating through Hong Kong and China-based phone numbers "
            "with Indian mule account recruitment.\n\n"
            "Key findings from automated identifier extraction:\n"
            f"• {ident_stats['hk_phones']} Hong Kong (+852) phone numbers linked to fraud operations\n"
            f"• {ident_stats['cn_phones']} Chinese mainland (+86) phone number — cross-border link\n"
            f"• {ident_stats['in_phones']} Indian phone numbers tied to mule recruitment\n"
            f"• {ident_stats['tg_handles']} Telegram handles operating as payment agents "
            "(USDT exchange, UPI panel operators, money transfer fronts)\n\n"
            "No officer searched for these identifiers. The system extracted phone numbers, "
            "Telegram handles, and payment references from raw Telegram messages and "
            "linked them across posts automatically. Each identifier is a potential lead "
            "for financial investigation.\n\n"
            f"Collection period: {stats['earliest'].strftime('%d %b %Y')} to "
            f"{stats['latest'].strftime('%d %b %Y')}."
        ),
        "sources": sources,
        "clusters": clusters,
        "entities": entities,
        "signals": signals,
        "identifiers": identifiers,
        "language_breakdown": language_breakdown,
        "evidence_items": evidence_items,
        "keywords": keyword_stats,
    }

    # ── Render PDF ──
    sys.path.insert(0, "/workspace/services/reporter")
    from anveshak.reporter.pdf import generate_pdf

    path = await generate_pdf(
        report_id="cyber-fraud-leave-behind",
        report_data=report_data,
        output_dir="/tmp",
    )
    if path != OUTPUT_PATH:
        os.rename(path, OUTPUT_PATH)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
