"""Security headers + structured request logging middleware (8D.5, 8D.6).

Security headers applied to every response:
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  X-XSS-Protection: 1; mode=block
  Referrer-Policy: strict-origin
  Strict-Transport-Security: max-age=31536000; includeSubDomains (when HSTS_ENABLED)
  Content-Security-Policy: default-src 'self'
  Cache-Control: no-store (auth routes only)

Request logging: method, path, status_code, duration_ms, analyst_id (from JWT).
No request bodies, no raw scraped content — CLAUDE.md security rule.
"""
from __future__ import annotations

import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..settings import settings as _settings

log = structlog.get_logger(__name__)

# Routes where Cache-Control: no-store is mandatory (auth responses must not be cached)
_AUTH_PREFIXES = ("/api/v1/auth",)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """8D.5 — Add security headers to every response.
    8D.6 — Structured request logging (no bodies, no PII).
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        t0 = time.monotonic()

        response: Response = await call_next(request)

        duration_ms = round((time.monotonic() - t0) * 1000, 1)

        # 8D.5 — Security headers (OWASP recommended set)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # HSTS — only when TLS is terminated upstream (avoid breaking HTTP-only dev)
        if _settings.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Cache-Control: no-store on auth paths — auth tokens must never be cached
        if any(request.url.path.startswith(p) for p in _AUTH_PREFIXES):
            response.headers["Cache-Control"] = "no-store"

        # 8D.6 — Structured request log: no bodies, no raw content
        analyst_id = _extract_analyst_id(request)
        log.info(
            "api.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            analyst_id=analyst_id,
        )

        return response


def _extract_analyst_id(request: Request) -> str | None:
    """Extract analyst sub from JWT without re-validating (best-effort logging only)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        import json
        import base64
        token = auth.removeprefix("Bearer ")
        payload_b64 = token.split(".")[1]
        # Pad to valid base64 length
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return str(payload.get("sub", ""))
    except Exception:
        return None
