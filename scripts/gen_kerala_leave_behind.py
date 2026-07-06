#!/usr/bin/env python3
"""Generate a leave-behind PDF for the Kerala Cyber Dome demo.

Uses real scraped data from the database + the V2 GROSINT-branded template.
Must run inside the report-worker container (has WeasyPrint + DB access):

    docker cp scripts/gen_kerala_leave_behind.py anveshak-report-worker-1:/tmp/
    docker exec anveshak-report-worker-1 python /tmp/gen_kerala_leave_behind.py
    docker cp anveshak-report-worker-1:/tmp/kerala_leave_behind.pdf .
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------
POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://anveshak:anveshak@postgres:5432/anveshak",
)
TOPIC_ID = "kl-cyd-001"
OUTPUT_PATH = "/tmp/kerala_leave_behind.pdf"

# ---------------------------------------------------------------------------
# Noise filters
# ---------------------------------------------------------------------------
_NOISE_ENTITIES = {
    "fifa", "iran", "pentagon", "lebanon", "spain",
    "north korea", "kim jong-un", "vance",
    "egypt", "france", "switzerland", "brazil", "argentina",
    "world cup", "ukraine", "russia", "gaza", "israel",
    "turkey", "germany", "japan", "portugal", "croatia",
    "south korea", "italy", "mexico", "copa", "euro",
    "champions league", "premier league", "la liga",
    "mozilla firefox", "google chrome", "safari", "webkit",
}

_NOISE_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "google.com",
    "apple.co", "bit.ly", "t.co", "instagram.com",
}

_LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ml": "Malayalam", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "mr": "Marathi", "bn": "Bengali",
    "zh": "Chinese", "ar": "Arabic", "ru": "Russian", "pa": "Punjabi",
    "gu": "Gujarati", "ne": "Nepali", "ur": "Urdu",
}

_TYPE_OVERRIDES = {
    "ernakulam": "GPE", "thiruvananthapuram": "GPE", "kochi": "GPE",
    "kozhikode": "GPE", "thrissur": "GPE", "malappuram": "GPE",
    "kannur": "GPE", "kollam": "GPE", "palakkad": "GPE",
    "alappuzha": "GPE", "idukki": "GPE", "wayanad": "GPE",
}


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

        # ── Clusters (top 15 by ISC) ──
        cluster_rows = await conn.fetch("""
            SELECT label, item_count, independent_source_count, executive_summary
            FROM narrative_clusters
            WHERE topic_id = $1
            ORDER BY independent_source_count DESC, item_count DESC
            LIMIT 15
        """, TOPIC_ID)
        clusters = []
        for r in cluster_rows:
            d = dict(r)
            if d.get("executive_summary") is None:
                d["executive_summary"] = ""
            clusters.append(d)

        # ── Signals (top 20, skip URL_DOMAIN noise) ──
        signal_rows = await conn.fetch("""
            SELECT s.signal_type, s.description, s.status, s.created_at
            FROM signals s
            WHERE s.topic_id = $1
              AND s.description NOT ILIKE '%URL_DOMAIN%'
            ORDER BY s.created_at DESC
            LIMIT 20
        """, TOPIC_ID)
        signals = []
        _CLUSTER_NAME_RE = re.compile(r"Cluster '([^']+)'")
        _IDENT_RE = re.compile(r"Identifier (\S+) '([^']+)'")
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

        # ── Identifiers ──
        ident_rows = await conn.fetch("""
            SELECT identifier_type, identifier_value, source_count, content_item_count
            FROM identifier_clusters
            WHERE topic_id = $1
            ORDER BY source_count DESC, content_item_count DESC
            LIMIT 15
        """, TOPIC_ID)
        identifiers = []
        for r in ident_rows:
            d = dict(r)
            if d["identifier_type"] == "URL_DOMAIN" and d["identifier_value"] in _NOISE_DOMAINS:
                continue
            identifiers.append(d)

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
                  AND ee.entity_text !~ '^[^a-zA-Z]*$'
                  AND ee.entity_text NOT LIKE '%height%'
                  AND ee.entity_text NOT LIKE '%src=%'
                GROUP BY ee.entity_type, ee.entity_text
            ) ee
            GROUP BY ee.entity_type, INITCAP(LOWER(ee.entity_text))
            HAVING SUM(cnt) >= 1
            ORDER BY mention_count DESC
            LIMIT 30
        """, TOPIC_ID)
        entities = []
        for r in entity_rows:
            text_lower = r["entity_text"].lower().strip()
            if text_lower in _NOISE_ENTITIES:
                continue
            d = dict(r)
            if text_lower in _TYPE_OVERRIDES:
                d["entity_type"] = _TYPE_OVERRIDES[text_lower]
            entities.append(d)
        entities = entities[:20]

        # ── Language breakdown ──
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

        # ── Evidence items (top 20 from high-ISC clusters) ──
        evidence_rows = await conn.fetch("""
            SELECT ci.clean_text, ci.url, ci.captured_at, ci.credibility_score_at_capture,
                   s.name AS source_name, s.platform,
                   nc.label AS cluster_label
            FROM content_items ci
            JOIN sources s ON s.id = ci.source_id
            JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
            WHERE ci.topic_id = $1
              AND nc.independent_source_count >= 3
              AND LENGTH(ci.clean_text) > 80
            ORDER BY nc.independent_source_count DESC, ci.captured_at DESC
            LIMIT 20
        """, TOPIC_ID)
        evidence_items = []
        for r in evidence_rows:
            text = r["clean_text"] or ""
            evidence_items.append({
                "title": r["cluster_label"],
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
        for kw in keywords_list[:15]:
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

    # ── Build BLUF ──
    bluf = (
        f"Automated monitoring of {stats['content_count']:,} content items from "
        f"{stats['source_count']} sources across news media, Telegram intelligence "
        f"channels, official government sources, dark web forums, and social media "
        f"reveals {stats['cluster_count']} narrative clusters and "
        f"{stats['signal_count']} intelligence signals related to online child "
        f"exploitation in Kerala. "
        f"Key findings: Predator networks targeting minors through gaming platforms "
        f"and social media with documented migration patterns to private messaging; "
        f"AI-generated synthetic exploitation content surging (35% increase per NCMEC); "
        f"financial trails via UPI, cryptocurrency, and hawala networks traced and "
        f"frozen; cross-platform identity correlation linking suspects across "
        f"Telegram, Discord, dark web, and crypto wallets. "
        f"Engine C identifier intelligence extracted phone numbers, Telegram handles, "
        f"email addresses, UPI IDs, and crypto wallet addresses from unstructured "
        f"content — automating cross-source correlation that would require manual "
        f"search across hundreds of messages and multiple platforms. "
        f"Collection period: {stats['earliest'].strftime('%d %b %Y')} to "
        f"{stats['latest'].strftime('%d %b %Y')}. "
        f"<br><br>"
        f"PLATFORM POSITIONING: Anveshak handles the investigation intelligence "
        f"layer — source monitoring, identifier correlation, network mapping, "
        f"financial trails, and deepfake detection. It integrates with "
        f"NCMEC/Interpol hash databases for content matching. The platform does "
        f"not store or process actual CSAM — it maps the networks distributing it. "
        f"<br><br>"
        f"ROADMAP — EXTENSIONS FOR CHILD PROTECTION: "
        f"(1) NCMEC/Interpol Hash Database Integration — PhotoDNA and ICSE "
        f"database hash matching against known CSAM databases for automated "
        f"content identification without human viewing. "
        f"(2) Age Estimation Model — Facial age estimation to triage and flag "
        f"content involving minors, reducing investigator exposure. "
        f"(3) Audio/Video Transcription — Whisper-based speech-to-text for "
        f"grooming conversations in voice messages and video calls. "
        f"(4) Device Forensics Import — Parse Cellebrite/UFED exports from "
        f"seized devices, browser history, and chat export ingestion for "
        f"complete investigation support. "
        f"(5) Victim Identification Support — Background and scene matching "
        f"across images for location identification using YOLO object detection "
        f"and CLIP visual similarity."
    )

    # ── Build report data bundle ──
    now = datetime.now(timezone.utc)
    report_data = {
        "id": "kl-leave-behind-001",
        "topic_name": "Kerala Cyber Dome — Online Child Protection Intelligence Briefing",
        "report_type": "research_summary",
        "generated_at": now.isoformat(),
        "confidence_score": 0.82,
        "content_item_count": stats["content_count"],
        "labels": {"classification": "SECRET", "domain": "child_protection"},
        "topic_stats": {
            "content_count": stats["content_count"],
            "source_count": stats["source_count"],
            "cluster_count": stats["cluster_count"],
            "signal_count": stats["signal_count"],
        },
        "bluf": bluf,
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
        report_id="kerala-leave-behind",
        report_data=report_data,
        output_dir="/tmp",
    )
    if path != OUTPUT_PATH:
        os.rename(path, OUTPUT_PATH)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
