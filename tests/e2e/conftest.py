"""E2E test fixtures — Phase 8F.

pytest.mark.e2e — requires running Docker Compose services with seeded demo data.

  make up seed-demo
  uv run --package anveshak-tests pytest tests/e2e/ -v -m e2e
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

API_BASE = "http://localhost:8000"
DEMO_EMAIL = "demo@anveshak.local"
DEMO_PASSWORD = "AnveshakDemo2024!"

# Seeded demo IDs (from seed_demo.sql)
DEMO_TOPIC_UAV = "b0000000-0000-0000-0000-000000000002"
DEMO_TOPIC_DEEPFAKE = "b0000000-0000-0000-0000-000000000003"
DEMO_REPORT_ID = "22000000-0000-0000-0000-000000000001"
DEMO_VISION_JOB_ID = "f0000000-0000-0000-0000-000000000001"
DEMO_SIGNAL_ID = "11000000-0000-0000-0000-000000000001"


def _http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 10) -> tuple[int, dict | list]:
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body


@pytest.fixture(scope="session")
def api_token() -> str:
    """Obtain a JWT for the demo analyst account."""
    data = json.dumps({
        "username": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
    }).encode()
    status, body = _http("POST", f"{API_BASE}/api/v1/auth/login", data=data,
                         headers={"Content-Type": "application/json"})
    if status != 200 or not body.get("access_token"):
        pytest.skip(f"Demo login failed (HTTP {status}) — is `make up seed-demo` done?")
    return body["access_token"]


@pytest.fixture(scope="session")
def auth_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
