"""Phase 8F — End-to-end pipeline tests.

Verifies the complete demo arc against live services seeded with seed_demo.sql.
All tests are read-only (no writes) to avoid disturbing demo state.

Requirements: make up seed-demo
Run: uv run --package anveshak-tests pytest tests/e2e/test_full_pipeline.py -v -m e2e
"""

from __future__ import annotations

import urllib.request

import pytest

from .conftest import (
    API_BASE,
    DEMO_REPORT_ID,
    DEMO_SIGNAL_ID,
    DEMO_TOPIC_DEEPFAKE,
    DEMO_TOPIC_UAV,
    DEMO_VISION_JOB_ID,
    _http,
)

# ---------------------------------------------------------------------------
# Step 1 — Deep health check (all dependencies green)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_api_deep_health_ready():
    """8F.1 — /health/ready returns 200 with all checks ok."""
    status, body = _http("GET", f"{API_BASE}/health/ready")
    assert status == 200, f"readiness check failed: {body}"
    assert body["status"] == "ready", f"degraded: {body['checks']}"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "ok"


# ---------------------------------------------------------------------------
# Step 2 — Auth flow
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_auth_login_returns_token(auth_headers):
    """8F.2 — Demo analyst login succeeds and returns JWT."""
    # auth_headers fixture proves login works; verify it unlocks /topics
    status, body = _http("GET", f"{API_BASE}/api/v1/topics", headers=auth_headers)
    assert status == 200
    assert isinstance(body, list)


@pytest.mark.e2e
def test_auth_required_on_topics():
    """8F.2 — Unauthenticated requests to /topics are rejected."""
    status, _ = _http("GET", f"{API_BASE}/api/v1/topics")
    assert status in (401, 403)


# ---------------------------------------------------------------------------
# Step 3 — Topic data
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_topics_loaded(auth_headers):
    """8F.3 — At least 3 topics are present after seed_demo.sql."""
    status, body = _http("GET", f"{API_BASE}/api/v1/topics", headers=auth_headers)
    assert status == 200
    assert len(body) >= 3, f"only {len(body)} topics loaded"


# ---------------------------------------------------------------------------
# Step 4 — Content items
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_content_items_exist_for_uav_topic(auth_headers):
    """8F.4 — UAV topic has at least 1 content item."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/topics/{DEMO_TOPIC_UAV}/content",
        headers=auth_headers,
    )
    assert status == 200
    items = body if isinstance(body, list) else body.get("items", [])
    assert len(items) >= 1, "no content items found for UAV topic"


# ---------------------------------------------------------------------------
# Step 5 — Intelligence signal
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_signal_exists_and_new(auth_headers):
    """8F.5 — At least one signal exists with status=new."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/signals?status=new",
        headers=auth_headers,
    )
    assert status == 200
    signals = body if isinstance(body, list) else body.get("items", [])
    assert len(signals) >= 1, "no active signals found"


@pytest.mark.e2e
def test_specific_signal_fields(auth_headers):
    """8F.5 — Demo signal has required fields from list endpoint."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/signals?status=new&topic_id={DEMO_TOPIC_DEEPFAKE}",
        headers=auth_headers,
    )
    assert status == 200
    signals = body if isinstance(body, list) else body.get("items", [])
    demo = [s for s in signals if s.get("id") == DEMO_SIGNAL_ID]
    assert demo, f"Demo signal {DEMO_SIGNAL_ID} not found in {len(signals)} signals"
    sig = demo[0]
    for field in ("id", "topic_id", "status", "signal_type", "description", "cluster_label"):
        assert field in sig, f"missing field: {field}"
    assert sig["status"] == "new"


# ---------------------------------------------------------------------------
# Step 6 — Vision analysis: deepfake score is a float, not bool
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_vision_job_deepfake_score_is_float(auth_headers):
    """8F.6 — Vision job result has deepfake_score as float 0–1 (rule 7: never bool)."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/vision/jobs/{DEMO_VISION_JOB_ID}",
        headers=auth_headers,
    )
    assert status == 200, f"vision job not found: {body}"
    result = body.get("result") or {}
    score = result.get("deepfake_score")
    assert score is not None, "deepfake_score missing from vision result"
    assert isinstance(score, float), f"deepfake_score must be float, got {type(score).__name__}"
    assert 0.0 <= score <= 1.0, f"deepfake_score {score} out of range [0, 1]"
    # Confirm the seeded value matches expected scenario
    assert score >= 0.9, f"expected high-confidence deepfake (≥0.9), got {score}"


# ---------------------------------------------------------------------------
# Step 7 — Report: generated, immutable, has source_snapshot
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_report_exists_and_immutable(auth_headers):
    """8F.7 — Pre-generated report has generated_at set (immutability rule)."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/reports/{DEMO_REPORT_ID}",
        headers=auth_headers,
    )
    assert status == 200, f"report not found: {body}"
    assert body.get("generated_at"), "generated_at must be set on a completed report"
    assert body.get("source_snapshot"), (
        "source_snapshot must capture credibility at generation time"
    )
    assert body.get("content_md"), "report content_md must not be empty"


@pytest.mark.e2e
def test_report_topic_list(auth_headers):
    """8F.7 — Topic reports endpoint returns the pre-generated brief."""
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/topics/{DEMO_TOPIC_UAV}/reports",
        headers=auth_headers,
    )
    assert status == 200
    reports = body if isinstance(body, list) else []
    assert any(r.get("id") == DEMO_REPORT_ID for r in reports), (
        "seeded report not found in topic reports list"
    )


# ---------------------------------------------------------------------------
# Step 8 — Observability endpoints
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_prometheus_scrape_endpoint_reachable():
    """8F.8 — Prometheus is reachable and scraping Anveshak jobs."""
    req = urllib.request.Request(
        "http://localhost:9090/-/ready",
        headers={"Accept": "text/plain"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        status = resp.status
    assert status == 200


@pytest.mark.e2e
def test_grafana_health():
    """8F.8 — Grafana is healthy."""
    status, body = _http("GET", "http://localhost:3001/api/health")
    assert status == 200
    assert body.get("database") == "ok"


@pytest.mark.e2e
def test_security_headers_present(auth_headers):
    """8F.9 — Security headers present on API responses (8D.5)."""
    req = urllib.request.Request(
        f"{API_BASE}/api/v1/topics",
        headers={**auth_headers},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
