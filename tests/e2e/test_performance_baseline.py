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
import urllib.request
import urllib.parse
import json

import pytest

from .conftest import (
    API_BASE,
    DEMO_TOPIC_UAV,
    DEMO_REPORT_ID,
    DEMO_VISION_JOB_ID,
    _http,
)


def _timed_get(url: str, headers: dict | None = None, timeout: int = 10) -> tuple[int, dict | list, float]:
    """GET url and return (status, body, elapsed_seconds)."""
    t0 = time.monotonic()
    status, body = _http("GET", url, headers=headers, timeout=timeout)
    elapsed = time.monotonic() - t0
    return status, body, elapsed


# ---------------------------------------------------------------------------
# Baseline latency checks
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_health_check_latency():
    """8F — /health responds in ≤200ms (p50 SLA)."""
    status, body, elapsed = _timed_get(f"{API_BASE}/health")
    assert status == 200
    assert elapsed < 0.200, f"/health took {elapsed*1000:.0f}ms (SLA: 200ms)"


@pytest.mark.e2e
def test_topics_list_latency(auth_headers):
    """8F — /topics list responds in ≤500ms."""
    status, body, elapsed = _timed_get(f"{API_BASE}/api/v1/topics", headers=auth_headers)
    assert status == 200
    assert elapsed < 0.500, f"/topics took {elapsed*1000:.0f}ms (SLA: 500ms)"


@pytest.mark.e2e
def test_signals_list_latency(auth_headers):
    """8F — /signals list responds in ≤500ms."""
    status, body, elapsed = _timed_get(
        f"{API_BASE}/api/v1/signals?status=new",
        headers=auth_headers,
    )
    assert status == 200
    assert elapsed < 0.500, f"/signals took {elapsed*1000:.0f}ms (SLA: 500ms)"


@pytest.mark.e2e
def test_report_fetch_latency(auth_headers):
    """8F — Report fetch responds in ≤1000ms."""
    status, body, elapsed = _timed_get(
        f"{API_BASE}/api/v1/reports/{DEMO_REPORT_ID}",
        headers=auth_headers,
    )
    assert status == 200
    assert elapsed < 1.000, f"/reports/{DEMO_REPORT_ID} took {elapsed*1000:.0f}ms (SLA: 1000ms)"


@pytest.mark.e2e
def test_vision_job_fetch_latency(auth_headers):
    """8F — Vision job status fetch responds in ≤500ms."""
    status, body, elapsed = _timed_get(
        f"{API_BASE}/api/v1/vision/jobs/{DEMO_VISION_JOB_ID}",
        headers=auth_headers,
    )
    assert status == 200
    assert elapsed < 0.500, f"/vision/jobs/{DEMO_VISION_JOB_ID} took {elapsed*1000:.0f}ms (SLA: 500ms)"


# ---------------------------------------------------------------------------
# Readiness check latency (includes DB + Redis + Ollama)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_readiness_check_latency():
    """8F — /health/ready responds in ≤2000ms (hits DB + Redis + Ollama)."""
    status, body, elapsed = _timed_get(f"{API_BASE}/health/ready", timeout=15)
    assert status == 200, f"readiness degraded: {body}"
    assert elapsed < 2.000, f"/health/ready took {elapsed*1000:.0f}ms (SLA: 2000ms)"


# ---------------------------------------------------------------------------
# Rate limit headroom (ensure demo traffic doesn't approach limit)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_topics_burst_stays_within_rate_limit(auth_headers):
    """8F — 10 rapid /topics requests should all return 200, not 429."""
    for i in range(10):
        status, _, elapsed = _timed_get(f"{API_BASE}/api/v1/topics", headers=auth_headers)
        assert status == 200, f"request {i+1}/10 got HTTP {status} — rate limit hit unexpectedly"
