#!/usr/bin/env python3
"""Anveshak pipeline validation script — on-demand E2E health check.

Validates all 5 PS-18 modules (M1–M5) are alive and producing real results
against live DB data. Safe to run at any time — read-only, never triggers
LLM jobs or mutations.

Usage:
    make validate
    python scripts/validate_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


BASE = "http://localhost:8000"
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    warning: bool = False  # warning = shown but does not count as failure


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — same pattern as demo_check.py)
# ---------------------------------------------------------------------------

def http_get(url: str, headers: dict | None = None, timeout: int = 8) -> tuple[int, dict | list]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"_text": raw}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Stage 1 — Infrastructure
# ---------------------------------------------------------------------------

def check_services() -> list[Check]:
    services = [
        ("API",      "http://localhost:8000/health"),
        ("Scraper",  "http://localhost:8001/health"),
        ("Social",   "http://localhost:8002/health"),
        ("Analyst",  "http://localhost:8007/health"),
        ("Reporter", "http://localhost:8005/health"),
    ]
    checks = []
    for name, url in services:
        status, body = http_get(url)
        passed = status == 200
        detail = "healthy" if passed else f"HTTP {status} — {body.get('error', body.get('detail', 'no response'))}"
        checks.append(Check(f"{name} service", passed, detail))
    return checks


def check_ollama() -> Check:
    status, body = http_get("http://localhost:11434/api/tags")
    if status != 200:
        return Check("Ollama", False, f"HTTP {status} — Ollama not reachable")
    models = [m.get("name", "") for m in (body if isinstance(body, list) else body.get("models", []))]
    if not models:
        configured_model = os.environ.get("OLLAMA_MODEL", "qwen2:7b")
        return Check("Ollama", False, f"no models loaded — run: docker exec anveshak-ollama ollama pull {configured_model}")
    return Check("Ollama", True, f"{len(models)} model(s) loaded: {', '.join(models[:3])}")


# ---------------------------------------------------------------------------
# Stage 2 — Authentication
# ---------------------------------------------------------------------------

def login() -> tuple[Check, str | None]:
    try:
        data = json.dumps({"username": DEMO_USER, "password": DEMO_PASS}).encode()
        req = urllib.request.Request(
            f"{BASE}/api/v1/auth/login",
            data=data,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
            token = body.get("access_token")
    except Exception as e:
        return Check("Login", False, str(e)), None

    passed = bool(token)
    return Check("Login", passed, "OK" if passed else "no access_token — check seed_demo.sql is loaded"), token


# ---------------------------------------------------------------------------
# Stage 3 — Corpus health (via pipeline-health endpoint)
# ---------------------------------------------------------------------------

def check_corpus(metrics: dict) -> list[Check]:
    checks = []

    total = metrics.get("content_items_total", 0)
    checks.append(Check(
        "Content items total",
        total >= 10,
        f"{total} items (need ≥10)" if total < 10 else f"{total} items ✓",
    ))

    embedded = metrics.get("content_items_embedded", 0)
    pct = (embedded / total * 100) if total > 0 else 0.0
    checks.append(Check(
        "Embedding coverage",
        pct >= 80.0,
        f"{embedded}/{total} embedded ({pct:.1f}%) — need ≥80%" if pct < 80 else f"{embedded}/{total} ({pct:.1f}%) ✓",
    ))

    last_24h = metrics.get("content_items_last_24h", 0)
    checks.append(Check(
        "Items ingested last 24h",
        last_24h >= 1,
        f"{last_24h} items in last 24h — pipeline may be stalled (check scraper/social logs)" if last_24h == 0
        else f"{last_24h} items in last 24h ✓ (pipeline is running)",
    ))

    return checks


# ---------------------------------------------------------------------------
# Stage 4 — Intelligence layer
# ---------------------------------------------------------------------------

def check_intelligence(metrics: dict) -> list[Check]:
    checks = []

    clusters = metrics.get("narrative_clusters_total", 0)
    checks.append(Check(
        "Narrative clusters",
        clusters >= 1,
        f"{clusters} clusters (need ≥1 — analyst worker must have run)" if clusters == 0 else f"{clusters} clusters ✓",
    ))

    signals = metrics.get("signals_last_30d", 0)
    checks.append(Check(
        "Signals last 30 days",
        signals >= 1,
        f"{signals} signals in last 30d — no threshold crossings yet" if signals == 0 else f"{signals} signal(s) ✓",
    ))

    return checks


# ---------------------------------------------------------------------------
# Stage 5 — Reports
# ---------------------------------------------------------------------------

def check_reports(metrics: dict) -> list[Check]:
    reports = metrics.get("reports_last_30d", 0)
    return [Check(
        "Reports generated (last 30 days)",
        reports >= 1,
        f"{reports} — trigger one via Reports page once corpus has ≥20 items" if reports == 0
        else f"{reports} report(s) generated ✓",
    )]


# ---------------------------------------------------------------------------
# Stage 6 — Source health
# ---------------------------------------------------------------------------

def check_sources(metrics: dict) -> list[Check]:
    checks = []

    active = metrics.get("sources_active", 0)
    checks.append(Check(
        "Active sources",
        active >= 1,
        f"{active} active sources (need ≥1 — add sources via Sources page)" if active == 0
        else f"{active} active source(s) ✓",
    ))

    down = metrics.get("sources_down", 0)
    # Down sources are a warning, not a hard failure
    checks.append(Check(
        "Sources down",
        True,
        f"{down} source(s) currently down — check Sources page for details" if down > 0 else "0 sources down ✓",
        warning=(down > 0),
    ))

    return checks


# ---------------------------------------------------------------------------
# Stage 7 — Multilingual pipeline
# ---------------------------------------------------------------------------

def check_multilingual(metrics: dict) -> list[Check]:
    """Verify the translation pipeline has processed non-English content."""
    checks = []

    zh_items = metrics.get("content_items_zh", 0)
    checks.append(Check(
        "Chinese content items",
        zh_items >= 0,   # warning only — may be 0 if no Chinese sources seeded yet
        f"{zh_items} Chinese-language items in corpus"
        + (" — seed Chinese sources: uv run python scripts/seed_chinese_sources.py" if zh_items == 0 else " ✓"),
        warning=(zh_items == 0),
    ))

    translated = metrics.get("content_items_translated", 0)
    if zh_items > 0:
        pct = (translated / zh_items * 100) if zh_items > 0 else 0.0
        checks.append(Check(
            "Translation coverage (zh→en)",
            pct >= 80.0,
            f"{translated}/{zh_items} Chinese items translated ({pct:.1f}%) — need ≥80%"
            if pct < 80 else f"{translated}/{zh_items} translated ({pct:.1f}%) ✓",
        ))
    else:
        checks.append(Check(
            "Translation coverage (zh→en)",
            True,
            "No Chinese items yet — skipped",
            warning=True,
        ))

    zh_entities = metrics.get("extracted_entities_zh", 0)
    checks.append(Check(
        "English entities from Chinese sources",
        zh_entities >= 0,
        f"{zh_entities} English entities extracted from Chinese content"
        + (" — analyst worker may not have run yet" if zh_entities == 0 and zh_items > 0 else "")
        + (" ✓" if zh_entities > 0 else ""),
        warning=(zh_entities == 0 and zh_items > 0),
    ))

    return checks


# ---------------------------------------------------------------------------
# Stage 8 — Trackers
# ---------------------------------------------------------------------------

def check_trackers(token: str) -> list[Check]:
    """Validate tracker subsystem: API reachable, schema exists, matching loop running."""
    checks = []

    # Check API endpoint responds (admin sees all orgs, may be empty list)
    status, body = http_get(f"{BASE}/api/v1/trackers", headers=_auth(token))
    checks.append(Check(
        "Trackers API",
        status == 200,
        f"HTTP {status}" if status != 200 else f"{len(body)} tracker(s) across all orgs",
    ))

    # Check scheduler logs for tracker matching loop
    # (this is a best-effort check — looks for the log message in recent scheduler output)
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail=200", "anveshak-analyse-scheduler-1"],
            capture_output=True, text=True, timeout=5,
        )
        logs = result.stdout + result.stderr
        loop_running = "tracker_matching_loop.started" in logs
        checks.append(Check(
            "Tracker matching loop",
            loop_running,
            "running ✓" if loop_running else "not found in scheduler logs — check scheduler rebuild",
            warning=not loop_running,
        ))

        # Check if matching has produced results
        cycle_done = "tracker_matching_loop.cycle_done" in logs
        if cycle_done:
            checks.append(Check("Tracker auto-matching", True, "cycle completed ✓"))
        else:
            checks.append(Check(
                "Tracker auto-matching",
                True,
                "no matches yet — may need active trackers with centroids",
                warning=True,
            ))
    except Exception:
        checks.append(Check(
            "Tracker matching loop",
            True,
            "could not check scheduler logs — skipped",
            warning=True,
        ))

    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("=" * 62)
    print("ANVESHAK — Pipeline Validation")
    print(f"Run at: {now}")
    print("=" * 62)

    all_checks: list[Check] = []

    def _p(c: Check) -> None:
        all_checks.append(c)
        tag = "WARN" if c.warning else ("PASS" if c.passed else "FAIL")
        print(f"  [{tag}] {c.name}: {c.detail}")

    # Stage 1 — Infrastructure
    print()
    print("Stage 1 — Infrastructure:")
    for c in check_services():
        _p(c)
    _p(check_ollama())

    # Stage 2 — Auth (needed for pipeline-health endpoint)
    print()
    print("Stage 2 — Authentication:")
    login_check, token = login()
    _p(login_check)

    if not token:
        print()
        # If Stage 1 already showed API down, the login failure is a consequence not a cause
        api_up = any(c.name == "API service" and c.passed for c in all_checks)
        if not api_up:
            print("BLOCKED: API is not reachable — start the stack first.")
            print("  Fix: make up")
        else:
            print("BLOCKED: Login failed — demo credentials may not be seeded.")
            print("  Fix: make seed-demo")
        return 1

    # Fetch all metrics in one call
    status, metrics = http_get(f"{BASE}/api/v1/system/pipeline-health", headers=_auth(token))
    if status != 200:
        print()
        print(f"BLOCKED: pipeline-health endpoint returned HTTP {status}.")
        print("  Fix: make build && make up  (API image may need a rebuild)")
        return 1

    # Stage 3 — Corpus
    print()
    print("Stage 3 — Corpus health:")
    for c in check_corpus(metrics):
        _p(c)

    # Stage 4 — Intelligence
    print()
    print("Stage 4 — Intelligence layer:")
    for c in check_intelligence(metrics):
        _p(c)

    # Stage 5 — Reports
    print()
    print("Stage 5 — Reports:")
    for c in check_reports(metrics):
        _p(c)

    # Stage 6 — Sources
    print()
    print("Stage 6 — Source health:")
    for c in check_sources(metrics):
        _p(c)

    # Stage 7 — Multilingual pipeline
    print()
    print("Stage 7 — Multilingual pipeline:")
    for c in check_multilingual(metrics):
        _p(c)

    # Stage 8 — Trackers
    print()
    print("Stage 8 — Trackers:")
    for c in check_trackers(token):
        _p(c)

    # Summary
    failures = [c for c in all_checks if not c.passed and not c.warning]
    warnings = [c for c in all_checks if c.warning]

    print()
    print("=" * 62)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED")
        print()
        print("Fix:")
        for f in failures:
            print(f"  - {f.name}: {f.detail}")
        return 1

    if warnings:
        print(f"RESULT: ALL CHECKS PASSED  ({len(warnings)} warning(s))")
        for w in warnings:
            print(f"  WARN: {w.name}: {w.detail}")
    else:
        print("RESULT: ALL CHECKS PASSED — pipeline is healthy")

    print()
    print(f"  Analyst workbench: http://localhost:3000")
    print(f"  Login:             {DEMO_USER} / {DEMO_PASS}")
    print(f"  Grafana:           http://localhost:3001")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
