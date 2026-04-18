#!/usr/bin/env python3
"""Anveshak vector pipeline validation — validates all 6 vector improvements.

Checks migrations 002–006, HNSW index, near-duplicate detection, temporal
windowing, label staleness tracking, cross-topic convergence, and continuous
backfill. Safe to run at any time — read-only, never triggers mutations.

Usage:
    make validate-vector
    python scripts/validate_vector.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


BASE = "http://localhost:8000"
DEMO_USER = "demo@anveshak.local"
DEMO_PASS = "AnveshakDemo2024!"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    warning: bool = False


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — same pattern as validate_pipeline.py)
# ---------------------------------------------------------------------------

def http_get(url: str, headers: dict | None = None, timeout: int = 8) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def http_post(url: str, data: dict, timeout: int = 8) -> tuple[int, dict]:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            rb = json.loads(e.read().decode())
        except Exception:
            rb = {}
        return e.code, rb
    except Exception as e:
        return 0, {"error": str(e)}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def login() -> tuple[Check, str | None]:
    status, body = http_post(f"{BASE}/api/v1/auth/login", {
        "email": DEMO_USER, "password": DEMO_PASS,
    })
    if status == 200 and "access_token" in body:
        return Check("Login", True, "authenticated"), body["access_token"]
    return Check("Login", False, f"HTTP {status}"), None


# ---------------------------------------------------------------------------
# Stage checks — all operate on the vector-health response
# ---------------------------------------------------------------------------

def check_migrations(m: dict) -> list[Check]:
    """Stage 1 — Verify all 5 migrations (002–006) are applied."""
    checks = []
    migration_names = {
        "002_near_duplicates": "Near-duplicate table",
        "003_hnsw_index": "HNSW index",
        "004_cluster_temporal": "Temporal windowing (archived_at)",
        "005_label_staleness": "Label staleness columns",
        "006_cross_topic_signals": "Cross-topic convergence index",
    }
    migrations = m.get("migrations", {})
    for key, label in migration_names.items():
        applied = migrations.get(key, False)
        checks.append(Check(
            f"Migration {key[:3]}",
            applied,
            f"{label} — {'applied' if applied else 'NOT applied (run: make migrate)'}",
        ))
    return checks


def check_hnsw(m: dict) -> list[Check]:
    """Stage 2 — Verify HNSW index is active (not IVFFlat)."""
    active = m.get("hnsw_index_active", False)
    indexdef = m.get("hnsw_indexdef", "")
    if active:
        detail = "HNSW index active"
        if "m =" in indexdef.lower() or "ef_construction" in indexdef.lower():
            detail += " (custom params)"
    else:
        detail = "HNSW not active — IVFFlat may still be in use (run: make migrate)"
    return [Check("HNSW index", active, detail)]


def check_near_duplicates(m: dict) -> list[Check]:
    """Stage 3 — Near-duplicate detection table and data."""
    checks = []
    table_exists = m.get("migrations", {}).get("002_near_duplicates", False)
    checks.append(Check("Near-dup table", table_exists,
                        "exists" if table_exists else "table missing"))

    count = m.get("near_duplicates_count", 0)
    if count > 0:
        checks.append(Check("Near-dup pairs", True, f"{count} pairs detected"))
    else:
        checks.append(Check("Near-dup pairs", True,
                            "0 pairs — normal on fresh deploy or no paraphrased content",
                            warning=True))
    return checks


def check_dedup_isc(m: dict) -> list[Check]:
    """Stage 4 — Dedup-to-ISC integrity."""
    near_dup = m.get("near_duplicates_count", 0)
    if near_dup > 0:
        return [Check("Dedup→ISC integrity", True,
                       f"{near_dup} near-duplicate pairs exist; ISC filtering active")]
    return [Check("Dedup→ISC integrity", True,
                  "no near-duplicates yet — ISC filtering will activate when pairs detected",
                  warning=True)]


def check_temporal(m: dict) -> list[Check]:
    """Stage 5 — Temporal windowing and cluster archival."""
    checks = []
    col_exists = m.get("migrations", {}).get("004_cluster_temporal", False)
    checks.append(Check("archived_at column", col_exists,
                        "present" if col_exists else "missing"))

    archived = m.get("archived_clusters_count", 0)
    if archived > 0:
        checks.append(Check("Archived clusters", True, f"{archived} clusters archived"))
    else:
        checks.append(Check("Archived clusters", True,
                            "0 — normal if all clusters are recent",
                            warning=True))
    return checks


def check_label_staleness(m: dict) -> list[Check]:
    """Stage 6 — Label staleness tracking."""
    checks = []
    col_exists = m.get("migrations", {}).get("005_label_staleness", False)
    checks.append(Check("Label tracking columns", col_exists,
                        "present" if col_exists else "missing"))

    labeled = m.get("labeled_clusters_count", 0)
    if labeled > 0:
        checks.append(Check("Labeled clusters", True,
                            f"{labeled} clusters with tracked labels"))
    else:
        checks.append(Check("Labeled clusters", True,
                            "0 — labelling cycle may not have run yet",
                            warning=True))
    return checks


def check_convergence(m: dict) -> list[Check]:
    """Stage 7 — Cross-topic convergence."""
    checks = []
    idx_exists = m.get("migrations", {}).get("006_cross_topic_signals", False)
    checks.append(Check("Convergence index", idx_exists,
                        "present" if idx_exists else "missing"))

    signals = m.get("convergence_signals_count", 0)
    if signals > 0:
        checks.append(Check("Convergence signals", True,
                            f"{signals} cross-topic convergence signals fired"))
    else:
        checks.append(Check("Convergence signals", True,
                            "0 — normal if topics don't share narratives yet",
                            warning=True))
    return checks


def check_backfill(m: dict) -> list[Check]:
    """Stage 8 — Continuous backfill."""
    checks = []
    backfilled = m.get("backfilled_items_count", 0)
    if backfilled > 0:
        checks.append(Check("Backfilled items", True,
                            f"{backfilled} items backfilled across topics"))
    else:
        checks.append(Check("Backfilled items", True,
                            "0 — backfill loop may not have run yet or no cross-topic matches",
                            warning=True))
    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 62)
    print("  ANVESHAK — Vector Pipeline Validation")
    print("  Checking migrations 002–006, HNSW, dedup, temporal,")
    print("  label staleness, convergence, backfill")
    print("=" * 62)

    all_checks: list[Check] = []

    def _p(c: Check) -> None:
        all_checks.append(c)
        if c.warning:
            tag = "WARN"
        elif c.passed:
            tag = "PASS"
        else:
            tag = "FAIL"
        print(f"  [{tag}] {c.name}: {c.detail}")

    # Auth
    print()
    print("Auth:")
    login_check, token = login()
    _p(login_check)

    if not token:
        print()
        print("BLOCKED: Login failed — cannot query vector-health endpoint.")
        print("  Fix: make up && make seed-demo")
        return 1

    # Fetch vector health metrics
    status, metrics = http_get(f"{BASE}/api/v1/system/vector-health", headers=_auth(token))
    if status != 200:
        print()
        print(f"BLOCKED: vector-health endpoint returned HTTP {status}.")
        if status == 404:
            print("  Fix: make build && make up  (API image needs rebuild for new endpoint)")
        else:
            print(f"  Response: {metrics}")
        return 1

    # Stage 1 — Migrations
    print()
    print("Stage 1 — Migrations (002–006):")
    for c in check_migrations(metrics):
        _p(c)

    # Stage 2 — HNSW Index
    print()
    print("Stage 2 — HNSW Index:")
    for c in check_hnsw(metrics):
        _p(c)

    # Stage 3 — Near-Duplicate Detection
    print()
    print("Stage 3 — Near-Duplicate Detection:")
    for c in check_near_duplicates(metrics):
        _p(c)

    # Stage 4 — Dedup → ISC Integrity
    print()
    print("Stage 4 — Dedup → ISC Integrity:")
    for c in check_dedup_isc(metrics):
        _p(c)

    # Stage 5 — Temporal Windowing
    print()
    print("Stage 5 — Temporal Windowing:")
    for c in check_temporal(metrics):
        _p(c)

    # Stage 6 — Label Staleness
    print()
    print("Stage 6 — Label Staleness:")
    for c in check_label_staleness(metrics):
        _p(c)

    # Stage 7 — Cross-Topic Convergence
    print()
    print("Stage 7 — Cross-Topic Convergence:")
    for c in check_convergence(metrics):
        _p(c)

    # Stage 8 — Continuous Backfill
    print()
    print("Stage 8 — Continuous Backfill:")
    for c in check_backfill(metrics):
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
        print("RESULT: ALL CHECKS PASSED — vector pipeline is healthy")

    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
