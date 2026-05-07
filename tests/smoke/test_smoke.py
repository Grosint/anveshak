"""Smoke tests — run in < 30s after every deploy.

Verifies all services are reachable and healthy.
Run: make test-smoke
"""
from __future__ import annotations

import json
import urllib.request

import pytest

pytestmark = pytest.mark.smoke

API_BASE = "http://localhost:8000"
OLLAMA_BASE = "http://localhost:11434"


def _get(url: str, timeout: int = 10) -> tuple[int, dict | list | str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        pytest.fail(f"Cannot reach {url}: {e}")


def test_api_health():
    """/health returns 200."""
    status, _ = _get(f"{API_BASE}/health")
    assert status == 200


def test_api_readiness():
    """/health/ready returns 200 with postgres and redis OK."""
    status, body = _get(f"{API_BASE}/health/ready")
    assert status == 200
    assert body["status"] == "ready", f"Not ready: {body}"
    assert body["checks"]["postgres"] == "ok", "PostgreSQL not healthy"
    assert body["checks"]["redis"] == "ok", "Redis not healthy"


def test_ollama_has_model():
    """Ollama has at least one model loaded."""
    status, body = _get(f"{OLLAMA_BASE}/api/tags")
    assert status == 200
    models = body.get("models", [])
    assert len(models) >= 1, "No Ollama models loaded"


def test_prometheus_reachable():
    """Prometheus is scraping."""
    status, _ = _get("http://localhost:9090/-/ready")
    assert status == 200


def test_grafana_healthy():
    """Grafana is running."""
    status, body = _get("http://localhost:3001/api/health")
    assert status == 200
    assert body.get("database") == "ok"
