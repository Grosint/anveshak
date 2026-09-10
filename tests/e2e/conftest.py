"""E2E test fixtures — Phase 8F.

pytest.mark.e2e - requires running Docker Compose services with seeded demo
data and detection already run over it. The seed writes content only, so
Narrative Clusters and Signals exist only after demo-detect.

  make up seed-demo demo-detect
  uv run --package anveshak-tests pytest tests/e2e/ -v -m e2e
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest

API_BASE = "http://localhost:8000"
# Demonstration credentials come from the environment - issue #41.
# scripts/seed_demo_org.py seeds these; nothing here carries a password.
DEMO_EMAIL = os.environ.get("ANVESHAK_DEMO_ANALYST_USERNAME", "demo@anveshak.local")
DEMO_PASSWORD = os.environ.get("ANVESHAK_DEMO_ANALYST_PASSWORD", "")

if not DEMO_PASSWORD:
    # Without it every test in this layer fails as HTTP 401, which hides
    # the cause behind a login failure.
    pytest.skip("ANVESHAK_DEMO_ANALYST_PASSWORD is not set - see .env.example", allow_module_level=True)

# Seeded demo IDs (from seed_demo.sql)
DEMO_TOPIC_UAV = "b0000000-0000-0000-0000-000000000002"
DEMO_REPORT_ID = "22000000-0000-0000-0000-000000000001"
DEMO_VISION_JOB_ID = "f0000000-0000-0000-0000-000000000001"

# There is deliberately no DEMO_SIGNAL_ID. A Signal the seed wrote would be
# decoration, so Signal IDs are whatever the engine assigned at detection time
# and the tests read them from the API. See issue #40.


def _http(
    method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 10
) -> tuple[int, dict | list]:
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
    data = json.dumps(
        {
            "username": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
        }
    ).encode()
    status, body = _http(
        "POST",
        f"{API_BASE}/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    if status != 200 or not body.get("access_token"):
        pytest.skip(f"Demo login failed (HTTP {status}) — is `make up seed-demo` done?")
    return body["access_token"]


@pytest.fixture(scope="session")
def auth_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
