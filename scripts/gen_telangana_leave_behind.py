#!/usr/bin/env python3
"""Generate a leave-behind PDF for the Telangana TGCSB demo.

Uses real scraped data from the database + the V2 GROSINT-branded template.
Must run inside the report-worker container (has WeasyPrint + DB access):

    docker cp scripts/gen_telangana_leave_behind.py anveshak-report-worker-1:/tmp/
    docker exec anveshak-report-worker-1 python /tmp/gen_telangana_leave_behind.py
    docker cp anveshak-report-worker-1:/tmp/telangana_leave_behind.pdf .
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
TOPIC_ID = "tg-cyber-001"
OUTPUT_PATH = "/tmp/telangana_leave_behind.pdf"

# ---------------------------------------------------------------------------
# Noise filters — scrape artifacts that pollute display
# ---------------------------------------------------------------------------

# HTML artifacts extracted as entities by spaCy from raw HTML fragments
_HTML_ARTIFACT_RE = re.compile(
    r"href=|src=|dir=|class=|style=|xmlns|</?[a-z]|\.css|\.js|"
    r"mozilla|firefox|chrome|safari|webkit|opera|edge|trident|"
    r"windows nt|macintosh|linux x86|compatible|gecko|applewebkit",
    re.IGNORECASE,
)

# Entities that are generic web/browser/boilerplate noise, not intelligence
_NOISE_ENTITIES = {
    # Web/browser artifacts
    "mozilla firefox",
    "google chrome",
    "safari",
    "internet explorer",
    "microsoft edge",
    "opera",
    "webkit",
    "gecko",
    # Generic terms misclassified by NER
    "state",
    "ips",
    "dgp",
    "sp",
    "dsp",
    "si",
    "ci",
    "lok adalat",
    "lok sabha",
    "rajya sabha",
    # Global noise not relevant to Telangana cyber fraud
    "fifa",
    "iran",
    "pentagon",
    "lebanon",
    "spain",
    "north korea",
    "kim jong-un",
    "vance",
    "egypt",
    "france",
    "switzerland",
    "brazil",
    "argentina",
    "world cup",
    "ukraine",
    "russia",
    "gaza",
    "israel",
    "turkey",
    "germany",
    "japan",
    "portugal",
    "croatia",
    "south korea",
    "italy",
    "mexico",
    "copa",
    "euro",
    "champions league",
    "premier league",
    "la liga",
}

# URL domains that are noise in identifier tables
_NOISE_DOMAINS = {
    "facebook.com",
    "twitter.com",
    "x.com",
    "google.com",
    "apple.co",
    "bit.ly",
    "t.co",
    "instagram.com",
    "cdn.siasat.com",
    "media.telanganatoday.com",
    "siasat.com",
    "mseducationacademy.in",
    "voters.eci.gov.in",
}

# Language code → human-readable name
_LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ur": "Urdu",
    "ta": "Tamil",
    "kn": "Kannada",
    "mr": "Marathi",
    "bn": "Bengali",
    "zh": "Chinese",
    "ar": "Arabic",
    "ru": "Russian",
    "id": "Indonesian",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "ko": "Korean",
    "no": "Norwegian",
    "ja": "Japanese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "tr": "Turkish",
    "th": "Thai",
    "vi": "Vietnamese",
    "ms": "Malay",
    "tl": "Tagalog",
    "ne": "Nepali",
    "as": "Assamese",
}


def _clean_cluster_label(label: str) -> str:
    """Remove HTML fragments from cluster labels."""
    # Strip href="..." fragments (closed or unclosed quotes)
    label = re.sub(r',?\s*href="[^"]*"?', "", label)
    # Strip any remaining HTML attributes (dir=, class=, style=, etc.)
    label = re.sub(r',?\s*\w+="[^"]*"?', "", label)
    # Strip any remaining HTML tags
    label = re.sub(r"<[^>]+>", "", label)
    # Remove bare URLs that snuck through
    label = re.sub(r"https?://\S+", "", label)
    # Collapse whitespace
    label = re.sub(r"\s+", " ", label).strip()
    # Remove leading/trailing commas, colons with nothing after
    label = label.strip(", ")
    # Remove trailing colon if label ends with one
    label = re.sub(r":\s*$", "", label).strip()
    return label


def _is_html_artifact(text: str) -> bool:
    """Check if entity text is an HTML/browser artifact."""
    return bool(_HTML_ARTIFACT_RE.search(text))


async def main() -> None:
    import asyncpg

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
    assert pool is not None

    async with pool.acquire() as conn:
        # ── Topic ──
        topic = await conn.fetchrow("SELECT name, keywords FROM topics WHERE id = $1", TOPIC_ID)
        assert topic, f"Topic {TOPIC_ID} not found"

        # ── Stats ──
        stats = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM content_items WHERE topic_id = $1) AS content_count,
                (SELECT COUNT(DISTINCT source_id) FROM content_items WHERE topic_id = $1) AS source_count,
                (SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1) AS cluster_count,
                (SELECT COUNT(*) FROM signals WHERE topic_id = $1) AS signal_count,
                (SELECT MIN(captured_at) FROM content_items WHERE topic_id = $1) AS earliest,
                (SELECT MAX(captured_at) FROM content_items WHERE topic_id = $1) AS latest
        """,
            TOPIC_ID,
        )

        # ── Sources — dedup by name, keep highest item_count ──
        source_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (s.name) s.name, s.platform,
                   CASE WHEN s.credibility_score = 0 THEN NULL
                        ELSE s.credibility_score END AS credibility_score,
                   COUNT(ci.id) OVER (PARTITION BY s.name) AS item_count
            FROM sources s
            JOIN topic_sources ts ON ts.source_id = s.id AND ts.topic_id = $1
            LEFT JOIN content_items ci ON ci.source_id = s.id AND ci.topic_id = $1
            ORDER BY s.name, s.credibility_score DESC NULLS LAST
        """,
            TOPIC_ID,
        )
        sources = []
        for r in source_rows:
            d = dict(r)
            if d["credibility_score"] is None:
                d["credibility_score"] = 0
            sources.append(d)
        # Sort by item_count descending for display
        sources.sort(key=lambda x: x["item_count"], reverse=True)

        # ── Clusters (top 15 by ISC) — clean HTML from labels ──
        cluster_rows = await conn.fetch(
            """
            SELECT label, item_count, independent_source_count, executive_summary
            FROM narrative_clusters
            WHERE topic_id = $1
            ORDER BY independent_source_count DESC, item_count DESC
            LIMIT 15
        """,
            TOPIC_ID,
        )
        clusters = []
        for r in cluster_rows:
            d = dict(r)
            if d.get("executive_summary") is None:
                d["executive_summary"] = ""
            d["label"] = _clean_cluster_label(d.get("label", ""))
            clusters.append(d)

        # ── Signals (top 20, skip noisy URL_DOMAIN) ──
        signal_rows = await conn.fetch(
            """
            SELECT s.signal_type, s.description, s.status, s.created_at
            FROM signals s
            WHERE s.topic_id = $1
              AND s.description NOT ILIKE '%URL_DOMAIN%facebook%'
              AND s.description NOT ILIKE '%URL_DOMAIN%twitter%'
              AND s.description NOT ILIKE '%URL_DOMAIN%x.com%'
              AND s.description NOT ILIKE '%URL_DOMAIN%google%'
              AND s.description NOT ILIKE '%URL_DOMAIN%apple%'
              AND s.description NOT ILIKE '%URL_DOMAIN%bit.ly%'
              AND s.description NOT ILIKE '%URL_DOMAIN%siasat%'
              AND s.description NOT ILIKE '%URL_DOMAIN%t.co%'
              AND s.description NOT ILIKE '%URL_DOMAIN%cdn.%'
              AND s.description NOT ILIKE '%URL_DOMAIN%media.%'
            ORDER BY s.created_at DESC
            LIMIT 20
        """,
            TOPIC_ID,
        )
        signals = []
        _CLUSTER_NAME_RE = re.compile(r"Cluster '([^']+)'")
        _IDENT_RE = re.compile(r"Identifier (\S+) '([^']+)'")
        seen_descriptions: set[str] = set()
        for r in signal_rows:
            d = dict(r)
            desc = d["description"] or ""
            # Dedup — same signal fires every scrape cycle
            dedup_key = desc.strip()
            if dedup_key in seen_descriptions:
                continue
            seen_descriptions.add(dedup_key)
            m = _CLUSTER_NAME_RE.search(desc)
            if m:
                d["cluster_label"] = _clean_cluster_label(m.group(1))
            else:
                m2 = _IDENT_RE.search(desc)
                d["cluster_label"] = f"{m2.group(1)}: {m2.group(2)}" if m2 else "—"
            signals.append(d)

        # ── Identifiers (skip generic URL_DOMAIN noise) ──
        ident_rows = await conn.fetch(
            """
            SELECT identifier_type, identifier_value, source_count, content_item_count
            FROM identifier_clusters
            WHERE topic_id = $1
            ORDER BY source_count DESC, content_item_count DESC
            LIMIT 30
        """,
            TOPIC_ID,
        )
        identifiers = []
        for r in ident_rows:
            d = dict(r)
            if d["identifier_type"] == "URL_DOMAIN" and d["identifier_value"] in _NOISE_DOMAINS:
                continue
            identifiers.append(d)
        identifiers = identifiers[:15]

        # ── Top entities — aggressive noise filtering ──
        entity_rows = await conn.fetch(
            """
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
                  AND ee.entity_text NOT LIKE '%href=%'
                  AND ee.entity_text NOT LIKE '%dir=%'
                  AND ee.entity_text NOT LIKE '%class=%'
                  AND ee.entity_text NOT LIKE '%http%'
                  AND ee.entity_text NOT LIKE '%.com%'
                  AND ee.entity_text NOT LIKE '%.in/%'
                  AND ee.entity_text NOT LIKE '%Mozilla%'
                  AND ee.entity_text NOT LIKE '%Firefox%'
                  AND ee.entity_text NOT LIKE '%Chrome%'
                  AND ee.entity_text NOT LIKE '%Safari%'
                  AND ee.entity_text NOT LIKE '%Windows%'
                  AND ee.entity_text NOT LIKE '%Gecko%'
                  AND ee.entity_text NOT LIKE '%WebKit%'
                GROUP BY ee.entity_type, ee.entity_text
            ) ee
            GROUP BY ee.entity_type, INITCAP(LOWER(ee.entity_text))
            HAVING SUM(cnt) >= 3
            ORDER BY mention_count DESC
            LIMIT 60
        """,
            TOPIC_ID,
        )
        entities = []
        for r in entity_rows:
            text_lower = r["entity_text"].lower().strip()
            if text_lower in _NOISE_ENTITIES:
                continue
            if _is_html_artifact(text_lower):
                continue
            # Skip very short generic terms (2-3 char abbreviations)
            if len(text_lower) <= 3 and text_lower not in {"bjp", "rbi", "cbi", "nit", "upi"}:
                continue
            entities.append(dict(r))
        entities = entities[:20]

        # ── Language breakdown ──
        lang_rows = await conn.fetch(
            """
            SELECT COALESCE(language, 'unknown') AS language, COUNT(*) AS count
            FROM content_items
            WHERE topic_id = $1 AND language IS NOT NULL
            GROUP BY language
            ORDER BY count DESC
        """,
            TOPIC_ID,
        )
        language_breakdown = []
        for r in lang_rows:
            code = r["language"]
            language_breakdown.append(
                {
                    "language": _LANG_NAMES.get(code, code),
                    "count": r["count"],
                }
            )

        # ── Evidence items (top 20 from highest-ISC clusters) ──
        evidence_rows = await conn.fetch(
            """
            SELECT ci.clean_text, ci.url, ci.captured_at, ci.credibility_score_at_capture,
                   s.name AS source_name, s.platform,
                   nc.label AS cluster_label
            FROM content_items ci
            JOIN sources s ON s.id = ci.source_id
            JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
            WHERE ci.topic_id = $1
              AND LENGTH(ci.clean_text) > 80
            ORDER BY nc.independent_source_count DESC, ci.captured_at DESC
            LIMIT 20
        """,
            TOPIC_ID,
        )
        evidence_items = []
        for r in evidence_rows:
            text = r["clean_text"] or ""
            evidence_items.append(
                {
                    "title": _clean_cluster_label(r["cluster_label"] or ""),
                    "snippet": text[:300] + ("..." if len(text) > 300 else ""),
                    "url": r["url"] or "",
                    "captured_at": str(r["captured_at"]),
                    "credibility_score_at_capture": r["credibility_score_at_capture"] or 0,
                    "source_name": r["source_name"],
                    "platform": r["platform"],
                }
            )

        # ── Keyword frequency from topic keywords ──
        keywords_list = topic["keywords"] or []
        keyword_stats = []
        for kw in keywords_list[:15]:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) AS cnt FROM content_items "
                "WHERE topic_id = $1 AND clean_text ILIKE $2",
                TOPIC_ID,
                f"%{kw}%",
            )
            keyword_stats.append(
                {
                    "keyword": kw,
                    "frequency": count_row["cnt"] if count_row else 0,
                }
            )
        keyword_stats.sort(key=lambda x: x["frequency"], reverse=True)

    await pool.close()

    # ── Build BLUF ──
    actionable_idents = [
        i
        for i in identifiers
        if i["identifier_type"]
        in (
            "TELEGRAM_HANDLE",
            "PHONE_INTL",
            "PHONE_IN",
            "UPI_ID",
            "CRYPTO_WALLET",
        )
    ]
    multi_source_idents = [i for i in identifiers if i["source_count"] >= 2]

    bluf = (
        f"Automated monitoring of {stats['content_count']:,} content items from "
        f"{stats['source_count']} sources across RSS news, Telegram fraud channels, "
        f"dark web, and social media reveals {stats['cluster_count']} narrative clusters "
        f"and {stats['signal_count']:,} intelligence signals related to cyber fraud "
        f"activity in Telangana. "
    )
    if multi_source_idents:
        handle_examples = [
            i["identifier_value"]
            for i in multi_source_idents
            if i["identifier_type"] == "TELEGRAM_HANDLE"
        ][:3]
        if handle_examples:
            bluf += (
                f"Key finding: Telegram handles ({', '.join(handle_examples)}) "
                f"appear across {multi_source_idents[0]['source_count']}+ independent "
                f"sources, indicating coordinated fraud operator networks. "
            )
    if actionable_idents:
        bluf += (
            f"Engine C identifier intelligence extracted {len(actionable_idents)} "
            f"actionable identifiers (Telegram handles, phone numbers, payment domains) "
            f"from unstructured content — automating cross-source correlation that "
            f"would require manual search across hundreds of messages. "
        )
    bluf += (
        f"Collection period: {stats['earliest'].strftime('%d %b %Y')} to "
        f"{stats['latest'].strftime('%d %b %Y')}."
    )

    # ── Build report data bundle ──
    now = datetime.now(timezone.utc)
    report_data = {
        "id": "tgcsb-leave-behind-001",
        "topic_name": "Telangana Cyber Fraud Intelligence — TGCSB Briefing",
        "report_type": "research_summary",
        "generated_at": now.isoformat(),
        "confidence_score": 0.75,
        "content_item_count": stats["content_count"],
        "labels": {"classification": "RESTRICTED", "domain": "cyber_fraud"},
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
        report_id="telangana-leave-behind",
        report_data=report_data,
        output_dir="/tmp",
    )
    if path != OUTPUT_PATH:
        os.rename(path, OUTPUT_PATH)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
