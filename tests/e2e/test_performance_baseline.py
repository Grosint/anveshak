"""Phase 8F — Performance baseline tests.

Validates that key API endpoints respond within documented SLA bounds.
These tests run against live services (make up seed-demo).

SLAs under test:
  - Health check: ≤200ms
  - Topics list: ≤500ms
  - Signals list: ≤500ms
  - Report fetch: ≤1000ms
  - Vision job fetch: ≤500ms

Run: uv run --package anveshak-tests pytest tests/e2e/test_performance_baseline.py -v -m e2e
"""

from __future__ import annotations

import time

import pytest

from .conftest import (
    API_BASE,
    DEMO_REPORT_ID,
    DEMO_VISION_JOB_ID,
    _http,
)


def _timed_get(
    url: str, headers: dict | None = None, timeout: int = 10
) -> tuple[int, dict | list, float]:
    """GET url and return (status, body, elapsed_seconds)."""
    t0 = time.monotonic()
    status, body = _http("GET", url, headers=headers, timeout=timeout)
    elapsed = time.monotonic() - t0
    return status, body, elapsed


def _measure_p50_p95(
    url: str,
    headers: dict | None = None,
    runs: int = 15,
    warmup: int = 3,
) -> tuple[float, float]:
    """Run multiple requests, return (p50, p95) in seconds."""
    latencies = []
    for _ in range(warmup + runs):
        _, _, elapsed = _timed_get(url, headers=headers)
        latencies.append(elapsed)
    # Drop warmup
    latencies = latencies[warmup:]
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    return p50, p95


# ---------------------------------------------------------------------------
# Statistical baseline latency checks (p50 + p95)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_health_check_latency():
    """8F — /health p50 ≤ 200ms, p95 ≤ 500ms."""
    p50, p95 = _measure_p50_p95(f"{API_BASE}/health")
    assert p50 < 0.200, f"/health p50={p50 * 1000:.0f}ms (SLA: 200ms)"
    assert p95 < 0.500, f"/health p95={p95 * 1000:.0f}ms (SLA: 500ms)"


@pytest.mark.e2e
def test_topics_list_latency(auth_headers):
    """8F — /topics p50 ≤ 500ms, p95 ≤ 1000ms."""
    p50, p95 = _measure_p50_p95(f"{API_BASE}/api/v1/topics", headers=auth_headers)
    assert p50 < 0.500, f"/topics p50={p50 * 1000:.0f}ms (SLA: 500ms)"
    assert p95 < 1.000, f"/topics p95={p95 * 1000:.0f}ms (SLA: 1000ms)"


@pytest.mark.e2e
def test_signals_list_latency(auth_headers):
    """8F — /signals p50 ≤ 500ms, p95 ≤ 1000ms."""
    p50, p95 = _measure_p50_p95(
        f"{API_BASE}/api/v1/signals?status=new",
        headers=auth_headers,
    )
    assert p50 < 0.500, f"/signals p50={p50 * 1000:.0f}ms (SLA: 500ms)"
    assert p95 < 1.000, f"/signals p95={p95 * 1000:.0f}ms (SLA: 1000ms)"


@pytest.mark.e2e
def test_report_fetch_latency(auth_headers):
    """8F — Report fetch p50 ≤ 1000ms, p95 ≤ 2000ms."""
    p50, p95 = _measure_p50_p95(
        f"{API_BASE}/api/v1/reports/{DEMO_REPORT_ID}",
        headers=auth_headers,
    )
    assert p50 < 1.000, f"/reports p50={p50 * 1000:.0f}ms (SLA: 1000ms)"
    assert p95 < 2.000, f"/reports p95={p95 * 1000:.0f}ms (SLA: 2000ms)"


@pytest.mark.e2e
def test_vision_job_fetch_latency(auth_headers):
    """8F — Vision job p50 ≤ 500ms, p95 ≤ 1000ms."""
    p50, p95 = _measure_p50_p95(
        f"{API_BASE}/api/v1/vision/jobs/{DEMO_VISION_JOB_ID}",
        headers=auth_headers,
    )
    assert p50 < 0.500, f"/vision p50={p50 * 1000:.0f}ms (SLA: 500ms)"
    assert p95 < 1.000, f"/vision p95={p95 * 1000:.0f}ms (SLA: 1000ms)"


# ---------------------------------------------------------------------------
# Readiness check latency (includes DB + Redis + Ollama)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_readiness_check_latency():
    """8F — /health/ready p50 ≤ 2000ms (hits DB + Redis + Ollama)."""
    p50, p95 = _measure_p50_p95(f"{API_BASE}/health/ready", runs=10, warmup=2)
    assert p50 < 2.000, f"/health/ready p50={p50 * 1000:.0f}ms (SLA: 2000ms)"
    assert p95 < 3.000, f"/health/ready p95={p95 * 1000:.0f}ms (SLA: 3000ms)"


# ---------------------------------------------------------------------------
# Rate limit headroom (ensure demo traffic doesn't approach limit)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_topics_burst_stays_within_rate_limit(auth_headers):
    """8F — 10 rapid /topics requests should all return 200, not 429."""
    for i in range(10):
        status, _, elapsed = _timed_get(f"{API_BASE}/api/v1/topics", headers=auth_headers)
        assert status == 200, f"request {i + 1}/10 got HTTP {status} — rate limit hit unexpectedly"
