"""Rate limiting middleware (8D.1–8D.4).

Uses a sliding window counter stored in a per-instance dict (in-memory).
Single-instance deployment — sovereign requirement means no horizontal scaling
without explicit configuration.

Limits (per 60-second window):
  POST /api/v1/auth/login  — 10 req/min per IP (brute-force protection)
  POST /api/v1/vision/analyse — 30 req/min per JWT sub (prevent queue flooding)
  All other authenticated endpoints — 120 req/min per JWT sub
  Unauthenticated reads — 60 req/min per IP

8D.4: Exceeded → HTTP 429 JSON {"detail": "Rate limit exceeded", "retry_after": N}
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from typing import Deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class _LRURateLimitStore:
    """Bounded LRU store for rate limit windows.

    Prevents unbounded memory growth when many unique (IP, path) pairs
    are seen over the lifetime of the API process.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._store: OrderedDict[str, Deque[float]] = OrderedDict()
        self._max = max_entries
        self.max_entries = max_entries  # public for test introspection

    def __getitem__(self, key: str) -> Deque[float]:
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        # Create new entry
        val: Deque[float] = deque()
        self._store[key] = val
        self._store.move_to_end(key)
        # Evict oldest if over cap
        while len(self._store) > self._max:
            self._store.popitem(last=False)
        return val

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def clear(self) -> None:
        self._store.clear()


# (identity_key) → deque of request timestamps within the window
_windows = _LRURateLimitStore(max_entries=10_000)

_WINDOW_S = 60  # sliding window size

# (path_prefix, method) → (limit, identity_fn)
# Identity function returns the rate-limit key for a request.

_LOGIN_PATH = "/api/v1/auth/login"
_VISION_ANALYSE_PATH = "/api/v1/vision/analyse"
_TIPLINE_PATH = "/api/v1/tipline/ingest"
_LOGIN_LIMIT = 10
_VISION_LIMIT = 30
_TIPLINE_LIMIT = 100
_AUTH_DEFAULT_LIMIT = 120
_ANON_LIMIT = 60


def _client_ip(request: Request) -> str:
    """Best-effort client IP (X-Forwarded-For → remote_addr)."""
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _jwt_sub(request: Request) -> str | None:
    """Extract JWT sub for per-analyst rate limiting — best-effort, no crypto."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        import base64
        import json

        token = auth.removeprefix("Bearer ")
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return str(payload.get("sub", ""))
    except Exception:
        return None


def _check_rate(key: str, limit: int) -> tuple[bool, int]:
    """Sliding window check. Returns (allowed, retry_after_seconds)."""
    now = time.monotonic()
    window = _windows[key]

    # Evict timestamps older than the window
    while window and window[0] < now - _WINDOW_S:
        window.popleft()

    if len(window) >= limit:
        oldest = window[0]
        retry_after = int(_WINDOW_S - (now - oldest)) + 1
        return False, retry_after

    window.append(now)
    return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """8D.1–8D.4 — Per-endpoint rate limiting."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        method = request.method

        # Skip rate limiting for internal paths (/health, /metrics)
        if path in ("/health", "/health/ready", "/metrics"):
            return await call_next(request)

        # 8D.1 — Login endpoint: per-IP
        if method == "POST" and path == _LOGIN_PATH:
            key = f"login:{_client_ip(request)}"
            allowed, retry_after = _check_rate(key, _LOGIN_LIMIT)
            if not allowed:
                return _rate_limit_response(retry_after)
            return await call_next(request)

        # Tipline ingest: per API key (X-Api-Key header)
        if method == "POST" and path == _TIPLINE_PATH:
            api_key = request.headers.get("x-api-key", _client_ip(request))
            key = f"tipline:{api_key}"
            allowed, retry_after = _check_rate(key, _TIPLINE_LIMIT)
            if not allowed:
                return _rate_limit_response(retry_after)
            return await call_next(request)

        # 8D.3 — Vision analyse: per JWT sub (prevent queue flooding)
        if method == "POST" and path == _VISION_ANALYSE_PATH:
            sub = _jwt_sub(request) or _client_ip(request)
            key = f"vision:{sub}"
            allowed, retry_after = _check_rate(key, _VISION_LIMIT)
            if not allowed:
                return _rate_limit_response(retry_after)
            return await call_next(request)

        # 8D.2 — Authenticated reads: per JWT sub
        sub = _jwt_sub(request)
        if sub:
            key = f"auth:{sub}"
            allowed, retry_after = _check_rate(key, _AUTH_DEFAULT_LIMIT)
            if not allowed:
                return _rate_limit_response(retry_after)
            return await call_next(request)

        # Anonymous requests: per IP
        key = f"anon:{_client_ip(request)}"
        allowed, retry_after = _check_rate(key, _ANON_LIMIT)
        if not allowed:
            return _rate_limit_response(retry_after)

        return await call_next(request)


def _rate_limit_response(retry_after: int) -> JSONResponse:
    """8D.4 — HTTP 429 with retry_after guidance."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )
