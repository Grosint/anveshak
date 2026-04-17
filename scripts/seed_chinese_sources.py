#!/usr/bin/env python3
"""Seed Chinese-language OSINT sources and a monitoring topic into Anveshak.

Usage:
    uv run python scripts/seed_chinese_sources.py
    uv run python scripts/seed_chinese_sources.py --api-url http://localhost:8000

Sources added:
    - Xinhua (新华社) — state news agency RSS
    - Global Times Chinese (环球时报) — state tabloid RSS
    - South China Morning Post — independent HK news RSS
    - China Military Net (中国军网) — PLA official web
    - People's Daily (人民日报) — CPC official web

Topic created:
    - name: china_military_osint
    - keywords: PLA, South China Sea, military exercise, Taiwan, Xi Jinping
    - languages: ["zh"]
    - signal_threshold: 2
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _post(url: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        return exc.code, {"error": body}


def _get(url: str, token: str) -> tuple[int, dict | list]:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode()}


SOURCES = [
    {
        "name": "Xinhua News Agency",
        "url_or_handle": "http://www.xinhuanet.com/english/rss/worldnews.xml",
        "platform": "rss",
        "credibility_score": 55.0,
        "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
    },
    {
        "name": "Global Times",
        "url_or_handle": "https://www.globaltimes.cn/rss/outbrain.xml",
        "platform": "rss",
        "credibility_score": 45.0,
        "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
    },
    {
        "name": "South China Morning Post",
        "url_or_handle": "https://www.scmp.com/rss/91/feed",
        "platform": "rss",
        "credibility_score": 72.0,
        "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
    },
    {
        "name": "China Military Net (81.cn)",
        "url_or_handle": "http://www.81.cn",
        "platform": "web",
        "credibility_score": 50.0,
        "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
    },
    {
        "name": "People's Daily (人民日报)",
        "url_or_handle": "http://paper.people.com.cn",
        "platform": "web",
        "credibility_score": 50.0,
        "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
    },
]

TOPIC = {
    "name": "china_military_osint",
    "description": "PLA military activity, South China Sea developments, Taiwan Strait tensions — Chinese-language sources with automatic English translation.",
    "keywords": ["PLA", "South China Sea", "military exercise", "Taiwan", "Xi Jinping", "解放军", "南海", "台湾"],
    "languages": ["zh", "en"],
    "signal_threshold": 2,
    "labels": {"classification": "OPEN", "domain": "osint", "owner_org": "anveshak"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Chinese OSINT sources into Anveshak")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Anveshak API base URL")
    parser.add_argument("--username", default="demo@anveshak.local")
    parser.add_argument("--password", default="AnveshakDemo2024!")
    args = parser.parse_args()

    base = args.api_url.rstrip("/")
    print(f"Seeding Chinese sources → {base}")

    # --- Login ---
    status, resp = _post(f"{base}/api/v1/auth/login", {
        "username": args.username,
        "password": args.password,
    })
    if status != 200 or "access_token" not in resp:
        print(f"FAIL: Login failed ({status}): {resp}")
        return 1
    token = resp["access_token"]
    print("✓ Authenticated")

    # --- Add sources ---
    source_ids: list[str] = []
    for src in SOURCES:
        status, resp = _post(f"{base}/api/v1/sources", src, token=token)
        if status in (200, 201):
            source_ids.append(resp.get("id", ""))
            print(f"  ✓ Source added: {src['name']}")
        elif status == 409:
            print(f"  ~ Source already exists: {src['name']}")
        else:
            print(f"  ✗ Source failed ({status}): {src['name']} — {resp}")

    # --- Create topic ---
    status, resp = _post(f"{base}/api/v1/topics", TOPIC, token=token)
    if status in (200, 201):
        topic_id = resp.get("id")
        print(f"✓ Topic created: {TOPIC['name']} (id={topic_id})")
    elif status == 409:
        print(f"~ Topic already exists: {TOPIC['name']}")
        # fetch existing topic id
        _, topics_resp = _get(f"{base}/api/v1/topics", token)
        topic_id = next(
            (t["id"] for t in (topics_resp if isinstance(topics_resp, list) else [])
             if t.get("name") == TOPIC["name"]),
            None,
        )
    else:
        print(f"✗ Topic creation failed ({status}): {resp}")
        topic_id = None

    print()
    print("Done. Next steps:")
    print("  1. Ensure Ollama has qwen2:7b:  ollama pull qwen2:7b")
    print("  2. Bring up the stack:          make up")
    print("  3. Run the migration:           make migrate")
    print(f"  4. Trigger scrape (replace TOPIC_ID with actual id):")
    print(f"     curl -X POST {base}/api/v1/topics/{topic_id or '<TOPIC_ID>'}/scrape -H 'Authorization: Bearer <TOKEN>'")
    print("  5. After scrape+analyse: check translated_text in DB:")
    print("     SELECT language, translation_model, LEFT(translated_text, 100)")
    print("     FROM content_items WHERE language = 'zh' LIMIT 5;")

    return 0


if __name__ == "__main__":
    sys.exit(main())
