"""Phase 8D — API security hardening tests (8D.8).

Tests:
  - Security headers present on all responses
  - Rate limiter returns 429 when limit exceeded
  - Cache-Control: no-store on auth routes
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anveshak.api.middleware.security import SecurityHeadersMiddleware
from anveshak.api.middleware.rate_limit import RateLimitMiddleware, _windows


@pytest.fixture(autouse=True)
def clear_rate_windows():
    """Reset rate limiter state between tests."""
    _windows.clear()
    yield
    _windows.clear()


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/v1/topics")
    async def topics():
        return {"topics": []}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"token": "fake"}

    @app.post("/api/v1/vision/analyse")
    async def analyse():
        return {"job_id": "123"}

    return app


@pytest.mark.unit
def test_security_headers_present():
    """8D.5 — Security headers on every response."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/api/v1/topics")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-XSS-Protection"] == "1; mode=block"
    assert resp.headers["Referrer-Policy"] == "strict-origin"


@pytest.mark.unit
def test_cache_control_on_auth_route():
    """8D.5 — Cache-Control: no-store on auth endpoints."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/login")
    assert resp.headers.get("Cache-Control") == "no-store"


@pytest.mark.unit
def test_login_rate_limit_triggers_429():
    """8D.1 — POST /auth/login rate limit (10/min per IP)."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    for _ in range(10):
        resp = client.post("/api/v1/auth/login")
        assert resp.status_code != 429, "Should not 429 within limit"

    # 11th request should be rate limited
    resp = client.post("/api/v1/auth/login")
    assert resp.status_code == 429
    body = resp.json()
    assert body["detail"] == "Rate limit exceeded"
    assert "retry_after" in body


@pytest.mark.unit
def test_vision_analyse_rate_limit_triggers_429():
    """8D.3 — POST /vision/analyse rate limit (30/min per JWT sub)."""
    # Build a fake JWT-like header with sub claim
    import base64, json
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "analyst-1"}).encode()
    ).decode().rstrip("=")
    fake_jwt = f"header.{payload}.sig"
    headers = {"Authorization": f"Bearer {fake_jwt}"}

    client = TestClient(_make_app(), raise_server_exceptions=False)

    for _ in range(30):
        resp = client.post("/api/v1/vision/analyse", headers=headers)
        assert resp.status_code != 429

    resp = client.post("/api/v1/vision/analyse", headers=headers)
    assert resp.status_code == 429


@pytest.mark.unit
def test_429_response_has_retry_after_header():
    """8D.4 — 429 response includes Retry-After header."""
    client = TestClient(_make_app(), raise_server_exceptions=False)
    for _ in range(11):
        client.post("/api/v1/auth/login")

    resp = client.post("/api/v1/auth/login")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
