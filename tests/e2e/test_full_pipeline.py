"""Phase 8F — End-to-end pipeline tests.

Verifies the complete demo arc against live services seeded with seed_demo.sql
and analysed by the pipeline. All tests are read-only (no writes) to avoid
disturbing demo state.

Requirements: make up seed-demo demo-detect
Run: uv run --package anveshak-tests pytest tests/e2e/test_full_pipeline.py -v -m e2e
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from .conftest import (
    API_BASE,
    DEMO_REPORT_ID,
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
# Step 5 - Intelligence signal, fired by the engine rather than seeded
# ---------------------------------------------------------------------------


def _new_signals(auth_headers) -> list[dict]:
    status, body = _http(
        "GET",
        f"{API_BASE}/api/v1/signals?status=new",
        headers=auth_headers,
    )
    assert status == 200
    return body if isinstance(body, list) else body.get("items", [])


@pytest.mark.e2e
def test_signal_exists_and_new(auth_headers):
    """8F.5 - At least one signal exists with status=new."""
    signals = _new_signals(auth_headers)
    assert len(signals) >= 1, (
        "no active signals found; the seed writes none, so run `make demo-detect`"
    )


# The IDs the seed used to fabricate. Asserting on "has a cluster_id or has
# evidence" was hollow: the old seeded row had both, so it would have passed
# the very check written to catch it. These IDs are the falsifiable part.
RETIRED_SIGNAL_ID = "11000000-0000-0000-0000-000000000001"
RETIRED_CLUSTER_IDS = (
    "00000001-0000-0000-0000-000000000001",
    "00000001-0000-0000-0000-000000000002",
)


@pytest.mark.e2e
def test_no_signal_is_a_retired_seeded_row(auth_headers):
    """8F.5 - No Signal is one the seed used to write (issue #40).

    Deleting the INSERT only fixes a fresh database. A box seeded before the
    change keeps the row until a reseed retires it, so the demonstration has
    to be checked, not assumed.
    """
    for sig in _new_signals(auth_headers):
        assert sig.get("id") != RETIRED_SIGNAL_ID, (
            "the fabricated seeded Signal is still present; run `make seed-demo` to retire it"
        )
        assert sig.get("cluster_id") not in RETIRED_CLUSTER_IDS, (
            f"signal {sig.get('id')} points at a fabricated cluster {sig.get('cluster_id')}"
        )


@pytest.mark.e2e
def test_signals_name_what_they_fired_on(auth_headers):
    """8F.5 - Every Signal records what it fired on.

    Multi-source convergence names a Narrative Cluster; identifier and template
    detectors put their reference in evidence, because the cluster_id FK points
    at narrative_clusters only.
    """
    for sig in _new_signals(auth_headers):
        assert sig.get("cluster_id") or sig.get("evidence"), (
            f"signal {sig.get('id')} names nothing it fired on"
        )


@pytest.mark.e2e
def test_signal_fields(auth_headers):
    """8F.5 - Signals carry the fields the workbench renders."""
    signals = _new_signals(auth_headers)
    assert signals, "no signals to inspect; run `make demo-detect`"
    sig = signals[0]
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
    # The endpoint paginates, so the reports are under "items". Falling back to
    # an empty list on a dict body made this assertion unfalsifiable.
    reports = body if isinstance(body, list) else body.get("items", [])
    assert any(r.get("id") == DEMO_REPORT_ID for r in reports), (
        "seeded report not found in topic reports list"
    )


# ---------------------------------------------------------------------------
# Step 8 — Observability endpoints
# ---------------------------------------------------------------------------


def _observability_up(url: str) -> bool:
    """True when the observability profile is running.

    `make up-dev` starts the application stack without Prometheus or Grafana,
    so these endpoints are absent by choice rather than broken.
    """
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


@pytest.mark.e2e
def test_prometheus_scrape_endpoint_reachable():
    """8F.8 — Prometheus is reachable and scraping Anveshak jobs."""
    if not _observability_up("http://localhost:9090/-/ready"):
        pytest.skip("observability profile not running (make up-prod)")
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
    if not _observability_up("http://localhost:3001/api/health"):
        pytest.skip("observability profile not running (make up-prod)")
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
