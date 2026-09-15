#!/usr/bin/env python3
"""Demo readiness verification script — 8-step arc (8E).

Verifies the full demo scenario is loaded and functional before presenting
to iDEX ADITI reviewers.

Usage:
    make demo-check
    python scripts/demo_check.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Demonstration credentials come from the environment - issue #41.
# scripts/seed_demo_org.py seeds these; nothing here carries a password.
REDIS_CONTAINER = os.environ.get("ANVESHAK_REDIS_CONTAINER", "anveshak-redis-1")
DEMO_USER = os.environ.get("ANVESHAK_DEMO_ANALYST_USERNAME", "demo@anveshak.local")
DEMO_PASS = os.environ.get("ANVESHAK_DEMO_ANALYST_PASSWORD", "")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def http_get(url: str, headers: dict | None = None, timeout: int = 5) -> tuple[int, dict | list]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                body = json.loads(raw)
            except Exception:
                body = {"_text": raw}
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def _authed_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Step 1 — All 5 Anveshak services healthy
# ---------------------------------------------------------------------------


def check_services() -> list[Check]:
    checks = []
    services = [
        ("API", "http://localhost:8000/health"),
        ("Scraper", "http://localhost:8001/health"),
        ("Social", "http://localhost:8002/health"),
        ("Analyst", "http://localhost:8007/health"),
    ]
    for name, url in services:
        status, body = http_get(url)
        passed = status == 200
        checks.append(
            Check(
                f"Step 1 — {name} service",
                passed,
                (
                    f"HTTP {status}"
                    if passed
                    else f"HTTP {status} — {body.get('error', body.get('detail', 'no response'))}"
                ),
            )
        )
    checks.append(_check_reporter_heartbeat())
    return checks


# The reporter is a pure ARQ worker. It publishes 8006 for Prometheus, which
# answers 200 on every path, and 8005 is not published at all, so neither port
# can say whether the worker is alive. Its heartbeat key is the same thing the
# compose healthcheck reads through sdk/arq_health.sh.
REPORTER_HEARTBEAT_KEY = "arq:reporter:health-check"
REPORTER_HEARTBEAT_MAX_AGE_S = 60


def _check_reporter_heartbeat() -> Check:
    name = "Step 1 — Reporter worker"
    try:
        raw = subprocess.run(
            [
                "docker",
                "exec",
                REDIS_CONTAINER,
                "redis-cli",
                "GET",
                REPORTER_HEARTBEAT_KEY,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(name, False, f"could not read {REPORTER_HEARTBEAT_KEY}: {exc}")

    if raw.returncode != 0:
        return Check(name, False, f"redis-cli failed: {raw.stderr.strip() or 'no output'}")

    beat = raw.stdout.strip()
    if not beat:
        return Check(name, False, f"no heartbeat at {REPORTER_HEARTBEAT_KEY}")

    # ARQ writes the key with a TTL, so a value present at all is a beat inside
    # that TTL. Report what it says, since the ongoing/queued counts are the
    # thing an operator wants before a demonstration.
    return Check(name, True, beat)


# ---------------------------------------------------------------------------
# Step 2 — Ollama models loaded
# ---------------------------------------------------------------------------


def check_ollama_models() -> list[Check]:
    status, body = http_get("http://localhost:11434/api/tags")
    if status != 200:
        return [Check("Step 2 — Ollama endpoint", False, f"HTTP {status}")]

    models = [
        m.get("name", "") for m in (body if isinstance(body, list) else body.get("models", []))
    ]
    configured_model = os.environ.get("OLLAMA_MODEL", "qwen2:7b")
    found = any(configured_model in m for m in models)
    return [
        Check(
            f"Step 2 — Ollama model: {configured_model}",
            found,
            (
                "loaded"
                if found
                else f"not found — run: docker exec anveshak-ollama ollama pull {configured_model}"
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Step 3 — Demo login
# ---------------------------------------------------------------------------


def demo_login(base: str) -> tuple[Check, str | None]:
    if not DEMO_PASS:
        # An empty password posts fine and comes back 401, which reads like a
        # broken API rather than a missing variable.
        return (
            Check("Step 3 — Demo login", False, "ANVESHAK_DEMO_ANALYST_PASSWORD is not set"),
            None,
        )
    try:
        data = json.dumps(
            {
                "username": DEMO_USER,
                "password": DEMO_PASS,
            }
        ).encode()
        req = urllib.request.Request(
            f"{base}/api/v1/auth/login",
            data=data,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            token = body.get("access_token")
    except Exception as e:
        return Check("Step 3 — Demo login", False, str(e)), None

    passed = bool(token)
    return (
        Check("Step 3 — Demo login", passed, "OK" if passed else "no access_token returned"),
        token,
    )


# ---------------------------------------------------------------------------
# Step 4 — Topics loaded (≥3)
# ---------------------------------------------------------------------------


def check_topics(base: str, token: str) -> Check:
    status, body = http_get(f"{base}/api/v1/topics", headers=_authed_headers(token))
    count = len(body) if isinstance(body, list) else body.get("total", 0)
    passed = status == 200 and count >= 3
    return Check(
        "Step 4 — Demo topics",
        passed,
        f"{count} topics loaded (need ≥3)" if status == 200 else f"HTTP {status}",
    )


# ---------------------------------------------------------------------------
# Step 5 — Intelligence signal exists (≥1 active signal)
#
# The seed writes no Signals (issue #40), so a count of zero means detection
# has not run yet rather than that the demo data is missing. The fix is to run
# the engine, never to seed a row that looks like its output.
# ---------------------------------------------------------------------------


def check_signals(base: str, token: str) -> Check:
    status, body = http_get(f"{base}/api/v1/signals?status=new", headers=_authed_headers(token))
    if status != 200:
        return Check("Step 5 — Intelligence signals", False, f"HTTP {status}")

    signals = body if isinstance(body, list) else body.get("items", [])
    count = len(signals)
    if count == 0:
        return Check(
            "Step 5 — Intelligence signals",
            False,
            "0 active signals; run `make demo-detect` to run the pipeline over the seeded corpus",
        )
    return Check(
        "Step 5 — Intelligence signals",
        True,
        f"{count} active signal(s), fired by the Signal engine",
    )


# ---------------------------------------------------------------------------
# Step 6 — Vision analysis: deepfake score is a float (not bool)
# ---------------------------------------------------------------------------


def check_vision_deepfake(base: str, token: str) -> Check:
    # The demo vision job result for content item e0000000-...-000000000003
    job_id = "f0000000-0000-0000-0000-000000000001"
    status, body = http_get(
        f"{base}/api/v1/vision/jobs/{job_id}",
        headers=_authed_headers(token),
    )
    if status != 200:
        return Check(
            "Step 6 — Vision deepfake score",
            False,
            f"HTTP {status} (seed_demo.sql may not be loaded)",
        )

    result = body.get("result") or {}
    score = result.get("deepfake_score")
    if score is None:
        return Check("Step 6 — Vision deepfake score", False, "deepfake_score missing from result")

    is_float = isinstance(score, float) and 0.0 <= score <= 1.0
    return Check(
        "Step 6 — Vision deepfake score",
        is_float,
        (
            f"deepfake_score={score} (float ✓)"
            if is_float
            else f"deepfake_score={score!r} is not a 0–1 float"
        ),
    )


# ---------------------------------------------------------------------------
# Step 7 — Report exists with generated_at set
# ---------------------------------------------------------------------------


def check_report(base: str, token: str) -> Check:
    topic_id = "b0000000-0000-0000-0000-000000000002"
    status, body = http_get(
        f"{base}/api/v1/topics/{topic_id}/reports",
        headers=_authed_headers(token),
    )
    if status != 200:
        return Check("Step 7 — Intelligence report", False, f"HTTP {status}")

    # The endpoint paginates, so the reports are under "items". Falling back to
    # an empty list on a dict body reported a seeded report as missing.
    reports = body if isinstance(body, list) else body.get("items", [])
    if not reports:
        return Check(
            "Step 7 — Intelligence report",
            False,
            "no reports found for UAV topic (seed_demo.sql may not be loaded)",
        )

    first = reports[0]
    has_generated_at = bool(first.get("generated_at"))
    return Check(
        "Step 7 — Intelligence report",
        has_generated_at,
        (
            f"report '{first.get('title', '')[:50]}...' generated_at set ✓"
            if has_generated_at
            else "generated_at is null"
        ),
    )


# ---------------------------------------------------------------------------
# Step 8 — Grafana health
# ---------------------------------------------------------------------------


def check_grafana() -> Check:
    """Grafana health, optional.

    The observability profile is off under `make up-dev`, so an unreachable
    Grafana is a deployment choice rather than a fault. A Grafana that answers
    but reports a broken database is still a failure.
    """
    status, body = http_get("http://localhost:3001/api/health")
    if status == 0:
        return Check(
            "Step 8 — Grafana health",
            True,
            "observability profile not running (make up-prod to enable)",
        )
    passed = status == 200 and body.get("database") == "ok"
    return Check(
        "Step 8 — Grafana health",
        passed,
        f"database={body.get('database')}" if status == 200 else f"HTTP {status}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    base = "http://localhost:8000"

    print("=" * 60)
    print("ANVESHAK — Demo Readiness Check (8-step arc)")
    print("=" * 60)
    print()

    all_checks: list[Check] = []

    def _print(c: Check) -> None:
        all_checks.append(c)
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")

    # Step 1 — Services
    print("Step 1 — Service health:")
    for c in check_services():
        _print(c)

    # Step 2 — Ollama
    print()
    print("Step 2 — Ollama models:")
    for c in check_ollama_models():
        _print(c)

    # Step 3 — Login
    print()
    print("Step 3 — Authentication:")
    login_check, token = demo_login(base)
    _print(login_check)

    if not token:
        print()
        print("BLOCKED: Cannot proceed without a valid demo token.")
        print("  Ensure seed_demo.sql has been loaded: make seed-demo")
        return 1

    # Steps 4-8 require auth
    print()
    print("Step 4 — Demo data:")
    _print(check_topics(base, token))

    print()
    print("Step 5 — Intelligence signals:")
    _print(check_signals(base, token))

    print()
    print("Step 6 — Vision analysis:")
    _print(check_vision_deepfake(base, token))

    print()
    print("Step 7 — Report generation:")
    _print(check_report(base, token))

    print()
    print("Step 8 — Observability:")
    _print(check_grafana())

    # Summary
    print()
    failures = [c for c in all_checks if not c.passed]
    if failures:
        print(f"RESULT: NOT READY — {len(failures)} check(s) failed")
        print()
        print("Fix:")
        for f in failures:
            print(f"  - {f.name}: {f.detail}")
        return 1

    print("RESULT: READY FOR DEMO")
    print()
    print("  Analyst workbench: http://localhost:3000")
    print(f"  Login:             {DEMO_USER} / the password in ANVESHAK_DEMO_ANALYST_PASSWORD")
    print("  Prometheus:        http://localhost:9090")
    print("  Grafana:           http://localhost:3001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
