"""Phase 8E — Demo arc validation tests.

Tests:
  - demo_check steps parse responses correctly
  - deepfake_score must be a float 0–1 (rule 7: never bool)
  - demo_check exits 0 on all-pass, 1 on any failure
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to sys.path so we can import demo_check directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import demo_check  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_get(responses: dict):
    """Return a fake http_get that returns pre-canned responses by URL substring.

    Longer keys take priority so more-specific URLs match before shorter ones.
    """
    def _fake(url, headers=None, timeout=5):
        for key in sorted(responses, key=len, reverse=True):
            if key in url:
                return responses[key]
        return 0, {"error": "no mock for " + url}
    return _fake


# ---------------------------------------------------------------------------
# Step 1 — Service health parsing
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_services_all_up():
    with patch.object(demo_check, "http_get", _make_http_get({
        "localhost:8000/health": (200, {"status": "ok"}),
        "localhost:8001/health": (200, {"status": "ok"}),
        "localhost:8002/health": (200, {"status": "ok"}),
        "localhost:8004/health": (200, {"status": "ok"}),
        "localhost:8005/health": (200, {"status": "ok"}),
    })):
        checks = demo_check.check_services()
    assert all(c.passed for c in checks), [c for c in checks if not c.passed]
    assert len(checks) == 5


@pytest.mark.unit
def test_check_services_one_down():
    with patch.object(demo_check, "http_get", _make_http_get({
        "localhost:8000/health": (200, {"status": "ok"}),
        "localhost:8001/health": (0, {"error": "connection refused"}),
        "localhost:8002/health": (200, {"status": "ok"}),
        "localhost:8004/health": (200, {"status": "ok"}),
        "localhost:8005/health": (200, {"status": "ok"}),
    })):
        checks = demo_check.check_services()
    failed = [c for c in checks if not c.passed]
    assert len(failed) == 1
    assert "Scraper" in failed[0].name


# ---------------------------------------------------------------------------
# Step 6 — Vision deepfake score must be a float
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_vision_deepfake_float_passes():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/vision/jobs/": (200, {"result": {"deepfake_score": 0.94}}),
    })):
        c = demo_check.check_vision_deepfake("http://localhost:8000", "fake-token")
    assert c.passed
    assert "0.94" in c.detail


@pytest.mark.unit
def test_vision_deepfake_bool_fails():
    """Rule 7: deepfake scores are probabilities, never booleans."""
    with patch.object(demo_check, "http_get", _make_http_get({
        "/vision/jobs/": (200, {"result": {"deepfake_score": True}}),
    })):
        c = demo_check.check_vision_deepfake("http://localhost:8000", "fake-token")
    assert not c.passed
    assert "not a 0" in c.detail


@pytest.mark.unit
def test_vision_deepfake_missing_fails():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/vision/jobs/": (200, {"result": {}}),
    })):
        c = demo_check.check_vision_deepfake("http://localhost:8000", "fake-token")
    assert not c.passed
    assert "missing" in c.detail


@pytest.mark.unit
def test_vision_job_404_fails():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/vision/jobs/": (404, {}),
    })):
        c = demo_check.check_vision_deepfake("http://localhost:8000", "fake-token")
    assert not c.passed
    assert "HTTP 404" in c.detail


# ---------------------------------------------------------------------------
# Step 7 — Report has generated_at
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_report_with_generated_at():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/reports": (200, [{"title": "Brief", "generated_at": "2026-04-15T10:00:00Z"}]),
    })):
        c = demo_check.check_report("http://localhost:8000", "fake-token")
    assert c.passed


@pytest.mark.unit
def test_check_report_empty_list_fails():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/reports": (200, []),
    })):
        c = demo_check.check_report("http://localhost:8000", "fake-token")
    assert not c.passed
    assert "no reports" in c.detail


@pytest.mark.unit
def test_check_report_null_generated_at_fails():
    with patch.object(demo_check, "http_get", _make_http_get({
        "/reports": (200, [{"title": "Draft", "generated_at": None}]),
    })):
        c = demo_check.check_report("http://localhost:8000", "fake-token")
    assert not c.passed
    assert "null" in c.detail


# ---------------------------------------------------------------------------
# Step 8 — Grafana health
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_grafana_healthy():
    with patch.object(demo_check, "http_get", _make_http_get({
        "localhost:3001": (200, {"database": "ok"}),
    })):
        c = demo_check.check_grafana()
    assert c.passed


@pytest.mark.unit
def test_check_grafana_unhealthy():
    with patch.object(demo_check, "http_get", _make_http_get({
        "localhost:3001": (503, {"database": "failed"}),
    })):
        c = demo_check.check_grafana()
    assert not c.passed


# ---------------------------------------------------------------------------
# main() exit code
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_main_returns_0_when_all_pass(capsys):
    """main() returns 0 when every check passes."""
    all_pass_responses = {
        "localhost:8000/health": (200, {"status": "ok"}),
        "localhost:8001/health": (200, {"status": "ok"}),
        "localhost:8002/health": (200, {"status": "ok"}),
        "localhost:8004/health": (200, {"status": "ok"}),
        "localhost:8005/health": (200, {"status": "ok"}),
        "11434/api/tags": (200, {"models": [{"name": "mistral:7b"}, {"name": "llama3.2:3b"}]}),
        "/auth/login": (200, {"access_token": "tok123"}),
        "/api/v1/topics": (200, [{"id": "1"}, {"id": "2"}, {"id": "3"}]),
        "signals?status=new": (200, [{"id": "s1"}]),
        "/vision/jobs/": (200, {"result": {"deepfake_score": 0.94}}),
        "/topics/b0000000-0000-0000-0000-000000000002/reports": (200, [{"title": "Brief", "generated_at": "2026-04-15T10:00:00Z"}]),
        "localhost:3001": (200, {"database": "ok"}),
    }

    def _fake_login(base):
        return demo_check.Check("Step 3 — Demo login", True, "OK"), "tok123"

    with patch.object(demo_check, "http_get", _make_http_get(all_pass_responses)), \
         patch.object(demo_check, "demo_login", _fake_login):
        rc = demo_check.main()
    assert rc == 0


@pytest.mark.unit
def test_main_returns_1_when_service_down(capsys):
    """main() returns 1 when a service is unreachable."""
    responses = {
        "localhost:8000/health": (0, {"error": "connection refused"}),
        "localhost:8001/health": (200, {"status": "ok"}),
        "localhost:8002/health": (200, {"status": "ok"}),
        "localhost:8004/health": (200, {"status": "ok"}),
        "localhost:8005/health": (200, {"status": "ok"}),
        "11434/api/tags": (200, {"models": [{"name": "mistral:7b"}, {"name": "llama3.2:3b"}]}),
        "/auth/login": (200, {"access_token": "tok123"}),
        "/api/v1/topics": (200, [{"id": "1"}, {"id": "2"}, {"id": "3"}]),
        "signals?status=new": (200, [{"id": "s1"}]),
        "/vision/jobs/": (200, {"result": {"deepfake_score": 0.94}}),
        "/topics/b0000000-0000-0000-0000-000000000002/reports": (200, [{"title": "Brief", "generated_at": "2026-04-15T10:00:00Z"}]),
        "localhost:3001": (200, {"database": "ok"}),
    }

    def _fake_login(base):
        return demo_check.Check("Step 3 — Demo login", True, "OK"), "tok123"

    with patch.object(demo_check, "http_get", _make_http_get(responses)), \
         patch.object(demo_check, "demo_login", _fake_login):
        rc = demo_check.main()
    assert rc == 1
