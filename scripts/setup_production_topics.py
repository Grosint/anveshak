#!/usr/bin/env python3
"""Set up 4 production validation topics with ~21 sources for 7-10 day monitoring.

Usage:
    python scripts/setup_production_topics.py
    python scripts/setup_production_topics.py --api-url http://localhost:8000
    python scripts/setup_production_topics.py --dry-run

Topics:
    1. India-China LAC Military Posturing
    2. Pakistan Cross-Border Terror & LoC Activity
    3. Indian Ocean Maritime Security & Chinese Naval Presence
    4. Disinformation & Info Ops Targeting India

Sources: 11 RSS + 6 web + 3 Telegram + 1 X/Twitter = 21 sources
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no external deps needed on VM)
# ---------------------------------------------------------------------------


def _post(url: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def _get(url: str, token: str) -> tuple[int, list | dict]:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode()}


# ---------------------------------------------------------------------------
# Topic definitions
# ---------------------------------------------------------------------------

TOPICS = [
    {
        "name": "India-China LAC Military Posturing",
        "keywords": [
            "LAC",
            "Line of Actual Control",
            "Ladakh",
            "Aksai Chin",
            "Depsang",
            "PLA",
            "India China border",
            "Galwan",
            "Pangong",
            "Arunachal",
            "Tawang",
            "Chinese military",
            "India China standoff",
            "eastern Ladakh",
            "border infrastructure",
        ],
        "languages": ["en", "hi", "zh"],
        "signal_threshold": 2,
        "credibility_min": 30.0,
        "scheduled_report_cron": "0 3 * * *",
        "scheduled_report_type": "intelligence_brief",
    },
    {
        "name": "Pakistan Cross-Border Terror & LoC Activity",
        "keywords": [
            "LoC",
            "Line of Control",
            "Kashmir",
            "cross-border",
            "infiltration",
            "ceasefire violation",
            "Pakistan terrorism",
            "LeT",
            "JeM",
            "Jaish",
            "Lashkar",
            "IED",
            "encounter",
            "Pulwama",
            "Pahalgam",
            "drone smuggling",
            "terror funding",
            "FATF Pakistan",
        ],
        "languages": ["en", "hi", "ur"],
        "signal_threshold": 2,
        "credibility_min": 30.0,
        "scheduled_report_cron": "0 3 * * *",
        "scheduled_report_type": "intelligence_brief",
    },
    {
        "name": "Indian Ocean Maritime Security & Chinese Naval Presence",
        "keywords": [
            "Indian Ocean",
            "IOR",
            "South China Sea",
            "Chinese navy",
            "PLA Navy",
            "Hambantota",
            "String of Pearls",
            "Djibouti",
            "submarine",
            "Indian Navy",
            "INS",
            "Quad naval",
            "Malabar exercise",
            "maritime surveillance",
            "PLAN",
            "aircraft carrier",
            "Andaman Nicobar",
        ],
        "languages": ["en", "hi"],
        "signal_threshold": 2,
        "credibility_min": 30.0,
        "scheduled_report_cron": "0 3 * * *",
        "scheduled_report_type": "intelligence_brief",
    },
    {
        "name": "Disinformation & Info Ops Targeting India",
        "keywords": [
            "deepfake India",
            "disinformation India",
            "fake news military",
            "propaganda India",
            "influence operation",
            "information warfare",
            "AI generated",
            "manipulated media",
            "fact check India",
            "ISPR propaganda",
            "anti-India narrative",
            "social media manipulation",
            "coordinated inauthentic",
        ],
        "languages": ["en", "hi"],
        "signal_threshold": 2,
        "credibility_min": 25.0,
        "scheduled_report_cron": "0 3 * * *",
        "scheduled_report_type": "intelligence_brief",
    },
]

# Topic index aliases for readability: 0=LAC, 1=LoC, 2=IOR, 3=Disinfo
_ALL = [0, 1, 2, 3]

# ---------------------------------------------------------------------------
# Source definitions — each has a list of topic indices it should link to
# ---------------------------------------------------------------------------

SOURCES = [
    # --- Tier 1: RSS feeds (platform: "rss") ---
    {
        "name": "Reuters World",
        "url_or_handle": "https://feeds.reuters.com/reuters/worldNews",
        "platform": "rss",
        "credibility_score": 85.0,
        "topic_indices": _ALL,
    },
    {
        "name": "Al Jazeera",
        "url_or_handle": "https://www.aljazeera.com/xml/rss/all.xml",
        "platform": "rss",
        "credibility_score": 72.0,
        "topic_indices": _ALL,
    },
    {
        "name": "NDTV India",
        "url_or_handle": "https://feeds.feedburner.com/ndtvnews-india-news",
        "platform": "rss",
        "credibility_score": 70.0,
        "topic_indices": [0, 1, 3],
    },
    {
        "name": "The Hindu National",
        "url_or_handle": "https://www.thehindu.com/news/national/feeder/default.rss",
        "platform": "rss",
        "credibility_score": 78.0,
        "topic_indices": [0, 1, 2],
    },
    {
        "name": "Times of India",
        "url_or_handle": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "platform": "rss",
        "credibility_score": 65.0,
        "topic_indices": [0, 1, 3],
    },
    {
        "name": "Dawn (Pakistan)",
        "url_or_handle": "https://www.dawn.com/feeds/home",
        "platform": "rss",
        "credibility_score": 55.0,
        "topic_indices": [1],
    },
    {
        "name": "South China Morning Post",
        "url_or_handle": "https://www.scmp.com/rss/91/feed",
        "platform": "rss",
        "credibility_score": 74.0,
        "topic_indices": [0, 2],
    },
    {
        "name": "The Diplomat",
        "url_or_handle": "https://thediplomat.com/feed/",
        "platform": "rss",
        "credibility_score": 80.0,
        "topic_indices": [0, 2],
    },
    {
        "name": "Defense News",
        "url_or_handle": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
        "platform": "rss",
        "credibility_score": 82.0,
        "topic_indices": [0, 1, 2],
    },
    {
        "name": "BBC World",
        "url_or_handle": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "platform": "rss",
        "credibility_score": 88.0,
        "topic_indices": _ALL,
    },
    {
        "name": "Livemint",
        "url_or_handle": "https://www.livemint.com/rss/news",
        "platform": "rss",
        "credibility_score": 68.0,
        "topic_indices": [0, 1, 3],
    },
    # --- Tier 2: Web sources (platform: "web") ---
    {
        "name": "GlobalSecurity.org",
        "url_or_handle": "https://www.globalsecurity.org",
        "platform": "web",
        "credibility_score": 82.0,
        "topic_indices": [0, 1, 2],
    },
    {
        "name": "Indian Defence Research Wing",
        "url_or_handle": "https://idrw.org",
        "platform": "web",
        "credibility_score": 60.0,
        "topic_indices": [0, 1],
    },
    {
        "name": "Janes",
        "url_or_handle": "https://www.janes.com",
        "platform": "web",
        "credibility_score": 91.0,
        "topic_indices": [0, 2],
    },
    {
        "name": "The Wire",
        "url_or_handle": "https://thewire.in",
        "platform": "web",
        "credibility_score": 65.0,
        "topic_indices": [1, 3],
    },
    {
        "name": "Bellingcat",
        "url_or_handle": "https://www.bellingcat.com",
        "platform": "web",
        "credibility_score": 85.0,
        "topic_indices": [3],
    },
    {
        "name": "India Today",
        "url_or_handle": "https://www.indiatoday.in",
        "platform": "web",
        "credibility_score": 62.0,
        "topic_indices": [0, 1, 3],
    },
    # --- Tier 3: Social (Telegram + X/Twitter) ---
    {
        "name": "Telegram: Defence Updates",
        "url_or_handle": "@defence_updates",
        "platform": "telegram",
        "credibility_score": 38.0,
        "topic_indices": [0, 1],
    },
    {
        "name": "Telegram: Indian OSINT",
        "url_or_handle": "@indian_osint",
        "platform": "telegram",
        "credibility_score": 42.0,
        "topic_indices": [0, 1, 3],
    },
    {
        "name": "Telegram: China Military Watch",
        "url_or_handle": "@china_military",
        "platform": "telegram",
        "credibility_score": 40.0,
        "topic_indices": [0, 2],
    },
    {
        "name": "X: India Defence Keywords",
        "url_or_handle": "india_defence_osint",
        "platform": "twitter",
        "credibility_score": 35.0,
        "topic_indices": _ALL,
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set up production validation topics and sources",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Anveshak API base URL (default: http://localhost:8000)",
    )
    parser.add_argument("--username", default="demo@anveshak.local")
    parser.add_argument("--password", default="AnveshakDemo2024!")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without calling API",
    )
    args = parser.parse_args()
    base = args.api_url.rstrip("/")

    # --- Dry run ---
    if args.dry_run:
        print("=== DRY RUN ===\n")
        for i, topic in enumerate(TOPICS):
            linked = [s["name"] for s in SOURCES if i in s["topic_indices"]]
            print(f"TOPIC {i + 1}: {topic['name']}")
            print(f"  keywords:  {len(topic['keywords'])} terms")
            print(f"  languages: {topic['languages']}")
            print(f"  threshold: ISC >= {topic['signal_threshold']}")
            print(
                f"  report:    {topic['scheduled_report_cron']} ({topic['scheduled_report_type']})"
            )
            print(f"  sources:   {len(linked)}")
            for name in linked:
                src = next(s for s in SOURCES if s["name"] == name)
                print(f"    - [{src['platform']:8s}] {name} (cred={src['credibility_score']})")
            print()
        platforms = {}
        for s in SOURCES:
            platforms.setdefault(s["platform"], []).append(s["name"])
        print("PLATFORM SUMMARY:")
        for plat, names in platforms.items():
            print(f"  {plat}: {len(names)}")
        print(f"\nTotal: {len(TOPICS)} topics, {len(SOURCES)} sources")
        return 0

    # --- Authenticate ---
    print(f"Setting up production validation → {base}\n")
    status_code, resp = _post(
        f"{base}/api/v1/auth/login",
        {
            "username": args.username,
            "password": args.password,
        },
    )
    if status_code != 200 or "access_token" not in resp:
        print(f"FAIL: Login failed ({status_code}): {resp}")
        return 1
    token = resp["access_token"]
    print("Authenticated\n")

    # --- Check existing topics (for idempotency) ---
    _, existing_topics = _get(f"{base}/api/v1/topics", token)
    existing_names: dict[str, str] = {}
    if isinstance(existing_topics, list):
        existing_names = {t["name"]: t["id"] for t in existing_topics}

    # --- Check existing sources ---
    _, existing_sources = _get(f"{base}/api/v1/sources", token)
    existing_urls: dict[str, str] = {}
    if isinstance(existing_sources, list):
        existing_urls = {s["url_or_handle"]: s["id"] for s in existing_sources}

    # --- Create topics ---
    topic_ids: list[str | None] = []
    for topic in TOPICS:
        if topic["name"] in existing_names:
            tid = existing_names[topic["name"]]
            print(f"  ~ Topic exists: {topic['name']} (id={tid[:8]}...)")
            topic_ids.append(tid)
            continue

        payload = {
            "name": topic["name"],
            "keywords": topic["keywords"],
            "languages": topic["languages"],
            "signal_threshold": topic["signal_threshold"],
            "credibility_min": topic["credibility_min"],
            "scheduled_report_cron": topic["scheduled_report_cron"],
            "scheduled_report_type": topic["scheduled_report_type"],
        }
        sc, resp = _post(f"{base}/api/v1/topics", payload, token=token)
        if sc in (200, 201):
            tid = resp.get("id", "")
            topic_ids.append(tid)
            print(f"  + Topic created: {topic['name']} (id={tid[:8]}...)")
        else:
            print(f"  x Topic FAILED ({sc}): {topic['name']} — {resp}")
            topic_ids.append(None)

    print()

    # --- Create sources and link to topics ---
    source_results: list[dict] = []
    for src in SOURCES:
        # Resolve topic IDs for this source
        link_topic_ids = [
            topic_ids[i]
            for i in src["topic_indices"]
            if i < len(topic_ids) and topic_ids[i] is not None
        ]

        if src["url_or_handle"] in existing_urls:
            sid = existing_urls[src["url_or_handle"]]
            print(f"  ~ Source exists: {src['name']} (id={sid[:8]}...)")
            source_results.append({"name": src["name"], "id": sid, "status": "exists"})
            # Still link to any new topics
            for tid in link_topic_ids:
                _post(f"{base}/api/v1/topics/{tid}/sources/{sid}", {}, token=token)
            continue

        payload = {
            "name": src["name"],
            "url_or_handle": src["url_or_handle"],
            "platform": src["platform"],
            "credibility_score": src["credibility_score"],
            "topic_ids": link_topic_ids,
        }
        sc, resp = _post(f"{base}/api/v1/sources", payload, token=token)
        if sc in (200, 201):
            sid = resp.get("id", "")
            health = resp.get("health_status", "?")
            warn = resp.get("warning", "")
            status_str = f"created (health={health})"
            if warn:
                status_str += f" WARNING: {warn}"
            print(f"  + Source: {src['name']} — {status_str}")
            source_results.append({"name": src["name"], "id": sid, "status": status_str})
        elif sc == 422:
            detail = resp.get("detail", resp.get("error", ""))
            print(f"  x Source FAILED ({sc}): {src['name']} — {detail}")
            source_results.append({"name": src["name"], "id": None, "status": f"failed: {detail}"})
        else:
            print(f"  x Source FAILED ({sc}): {src['name']} — {resp}")
            source_results.append({"name": src["name"], "id": None, "status": f"failed ({sc})"})

    print()

    # --- Verify ---
    print("=== VERIFICATION ===\n")
    for i, topic in enumerate(TOPICS):
        tid = topic_ids[i]
        if not tid:
            print(f"TOPIC {i + 1}: {topic['name']} — SKIPPED (creation failed)")
            continue
        _, sources = _get(f"{base}/api/v1/topics/{tid}/sources", token)
        count = len(sources) if isinstance(sources, list) else 0
        platforms = set()
        if isinstance(sources, list):
            platforms = {s.get("platform", "?") for s in sources}
        expected = sum(1 for s in SOURCES if i in s["topic_indices"])
        status_str = "OK" if count >= expected else f"WARN (expected {expected})"
        print(f"TOPIC {i + 1}: {topic['name']}")
        print(f"  Sources linked: {count} ({status_str})")
        print(f"  Platforms: {', '.join(sorted(platforms))} (ISC potential: {len(platforms)})")
        print()

    # --- Summary ---
    created = sum(1 for r in source_results if "created" in r["status"])
    existing = sum(1 for r in source_results if r["status"] == "exists")
    failed = sum(1 for r in source_results if "failed" in r["status"])
    print(f"SUMMARY: {created} created, {existing} already existed, {failed} failed")
    print()
    print("Next steps:")
    print("  1. Verify containers: make ps")
    print("  2. Watch scraper logs: make logs-scrape-web-scheduler")
    print("  3. Check first content in ~5 min: GET /api/v1/topics/<id>/content")
    print("  4. Run diagnostics tomorrow: python scripts/pipeline_health.py")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
