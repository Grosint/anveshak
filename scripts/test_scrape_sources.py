"""Source connectivity test — runs INSIDE the scrape-web-scheduler container.

Tests RSS, web, and onion fetching using the exact same code paths
as production scraping. Outputs JSON to stdout for the host orchestrator.

Usage (from host):
    docker exec anveshak-scrape-web-scheduler-1 python /tmp/test_scrape_sources.py
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import time
import traceback
from typing import Any

# Ensure HOME is set — Crawl4AI / Playwright need a writable home dir
if not os.environ.get("HOME") or os.environ["HOME"] == "/nonexistent":
    os.environ["HOME"] = "/tmp"

# Suppress log output to stderr so JSON on stdout is clean
os.environ["LOG_LEVEL"] = "ERROR"

# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

RSS_SOURCES = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NDTV India", "https://feeds.feedburner.com/ndtvnews-india-news"),
    ("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("Bellingcat", "https://www.bellingcat.com/feed/"),
    ("Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("The Diplomat", "https://thediplomat.com/feed/"),
    ("Livemint News", "https://www.livemint.com/rss/news"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),
    ("SCMP Asia", "https://www.scmp.com/rss/91/feed"),
]

WEB_SOURCES = [
    ("globalsecurity.org", "https://www.globalsecurity.org"),
    ("idrw.org", "https://idrw.org"),
    ("janes.com", "https://www.janes.com"),
    ("livemint.com", "https://www.livemint.com"),
    ("thewire.in", "https://thewire.in"),
]

ONION_SOURCES = [
    ("Tor Project Onion", "http://2gzyxa5ihm7nsber64ilibmccyxpbjufoir247jkoebi7wy3qkgecdid.onion"),
    ("BBC Tor Mirror", "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion/"),
]


def _result(
    source_type: str, name: str, passed: bool, chars: int, reason: str, elapsed: float,
) -> dict[str, Any]:
    return {
        "type": source_type,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "chars": chars,
        "reason": reason,
        "elapsed_s": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# RSS tests — uses real fetch_rss_items()
# ---------------------------------------------------------------------------

async def test_rss(name: str, url: str) -> dict:
    from anveshak.scraper.rss import fetch_rss_items

    t0 = time.monotonic()
    try:
        items = await fetch_rss_items(url)
        elapsed = time.monotonic() - t0
        if not items:
            return _result("rss", name, False, 0, "No entries parsed", elapsed)
        total_chars = sum(len(it.raw_text) for it in items)
        return _result(
            "rss", name, True, total_chars,
            f"{len(items)} entries parsed", elapsed,
        )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        return _result("rss", name, False, 0, str(exc)[:120], elapsed)


# ---------------------------------------------------------------------------
# Web tests — uses real create_shared_crawler() + fetch_url_with_crawler()
# ---------------------------------------------------------------------------

async def test_web_all(sources: list[tuple[str, str]]) -> list[dict]:
    """Test all web sources sharing one Crawl4AI browser instance (same as production)."""
    from anveshak.scraper.fetch import create_shared_crawler, fetch_url_with_crawler

    results = []
    try:
        async with create_shared_crawler() as (crawler, run_cfg):
            for name, url in sources:
                t0 = time.monotonic()
                try:
                    text = await fetch_url_with_crawler(url, crawler, run_cfg)
                    elapsed = time.monotonic() - t0
                    if text and len(text.strip()) >= 200:
                        results.append(_result(
                            "web", name, True, len(text),
                            "Crawl4AI extracted", elapsed,
                        ))
                    elif text:
                        results.append(_result(
                            "web", name, False, len(text),
                            f"Too short ({len(text)} chars, need 200+)", elapsed,
                        ))
                    else:
                        results.append(_result(
                            "web", name, False, 0, "No text extracted", elapsed,
                        ))
                except Exception as exc:
                    elapsed = time.monotonic() - t0
                    results.append(_result("web", name, False, 0, str(exc)[:120], elapsed))
    except Exception as exc:
        # Browser failed to start — mark all as failed
        for name, url in sources:
            results.append(_result("web", name, False, 0, f"Browser init failed: {str(exc)[:80]}", 0))
    return results


# ---------------------------------------------------------------------------
# Onion tests — uses real create_tor_crawler() + fetch_url_via_tor()
# ---------------------------------------------------------------------------

async def test_onion_all(sources: list[tuple[str, str]]) -> list[dict]:
    """Test onion sources through Tor using the real dark web fetch path."""
    from anveshak.scraper.fetch import create_tor_crawler, fetch_url_via_tor, validate_onion_url
    from anveshak.scraper.settings import settings

    results = []

    # Pre-check: is Tor proxy reachable?
    tor_host = "tor-proxy"
    tor_port = 9050
    try:
        parsed_proxy = settings.darkweb_tor_proxy_url
        if "://" in parsed_proxy:
            host_port = parsed_proxy.split("://")[1]
            if ":" in host_port:
                tor_host, tor_port = host_port.split(":")
                tor_port = int(tor_port)
    except Exception:
        pass

    t0 = time.monotonic()
    try:
        sock = socket.create_connection((tor_host, tor_port), timeout=10)
        sock.close()
        tor_reachable = True
        tor_elapsed = round(time.monotonic() - t0, 1)
    except Exception as exc:
        tor_reachable = False
        tor_elapsed = round(time.monotonic() - t0, 1)
        for name, url in sources:
            results.append(_result(
                "onion", name, False, 0,
                f"Tor proxy unreachable ({tor_host}:{tor_port}): {str(exc)[:60]}", tor_elapsed,
            ))
        return results

    # Tor proxy is reachable — test each onion source
    try:
        async with create_tor_crawler() as (crawler, run_cfg):
            for name, url in sources:
                t0 = time.monotonic()
                try:
                    validate_onion_url(url)
                    text = await fetch_url_via_tor(url, crawler, run_cfg)
                    elapsed = time.monotonic() - t0
                    if text and len(text.strip()) >= 50:
                        results.append(_result(
                            "onion", name, True, len(text),
                            "Tor circuit OK", elapsed,
                        ))
                    elif text:
                        results.append(_result(
                            "onion", name, False, len(text),
                            f"Too short ({len(text)} chars)", elapsed,
                        ))
                    else:
                        results.append(_result(
                            "onion", name, False, 0, "No text extracted via Tor", elapsed,
                        ))
                except ValueError as exc:
                    elapsed = time.monotonic() - t0
                    results.append(_result("onion", name, False, 0, f"DNS leak check: {exc}", elapsed))
                except Exception as exc:
                    elapsed = time.monotonic() - t0
                    results.append(_result("onion", name, False, 0, str(exc)[:120], elapsed))
    except Exception as exc:
        for name, url in sources:
            if not any(r["name"] == name for r in results):
                results.append(_result("onion", name, False, 0, f"Tor browser failed: {str(exc)[:80]}", 0))
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> list[dict]:
    results: list[dict] = []

    # RSS — sequential, each creates its own httpx client (same as production)
    for name, url in RSS_SOURCES:
        results.append(await test_rss(name, url))

    # Web — shared browser (same as production scrape_topic job)
    results.extend(await test_web_all(WEB_SOURCES))

    # Onion — shared Tor browser (same as production scrape_darkweb_topic job)
    results.extend(await test_onion_all(ONION_SOURCES))

    return results


if __name__ == "__main__":
    # Redirect stderr to suppress log noise — JSON goes to stdout only
    import io
    sys.stderr = io.TextIOWrapper(open(os.devnull, "wb"), write_through=True)

    try:
        results = asyncio.run(main())
        # Write to fd 1 directly to bypass any buffering issues
        sys.__stdout__.write(json.dumps(results))
        sys.__stdout__.write("\n")
        sys.__stdout__.flush()
    except Exception:
        # If something crashes entirely, output an error result
        print(json.dumps([{
            "type": "error",
            "name": "scraper_test",
            "status": "FAIL",
            "chars": 0,
            "reason": traceback.format_exc()[-200:],
            "elapsed_s": 0,
        }]))
        sys.exit(1)
