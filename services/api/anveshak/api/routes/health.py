"""Health check endpoints."""
from fastapi import APIRouter, Depends, Response
from datetime import datetime, UTC
import asyncpg
import redis.asyncio as aioredis
import httpx
from ..db.pool import get_db
from ..settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "anveshak-api",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def readiness(response: Response, db: asyncpg.Connection = Depends(get_db)):
    """8D.7 — Deep health check: DB + Redis + Ollama.

    Returns HTTP 200 when all checks pass, HTTP 503 when any check fails.
    """
    checks = {}

    # PostgreSQL
    try:
        await db.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            checks["ollama"] = {"status": "ok", "models": models}
    except Exception as e:
        checks["ollama"] = f"error: {e}"

    all_ok = all(
        v == "ok" or (isinstance(v, dict) and v.get("status") == "ok")
        for v in checks.values()
    )

    if not all_ok:
        response.status_code = 503

    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }
