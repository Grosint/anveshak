"""Authentication endpoints — login, logout, current user."""
from __future__ import annotations

from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
import asyncpg

from ..db.pool import get_db
from ..db import auth as auth_db
from ..auth.jwt import (
    create_access_token,
    pwd_context,
    get_current_user,
    revoke_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    username: str
    password: str


@router.post("/login")
async def login(
    req: LoginRequest,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await auth_db.get_user_by_username(db, req.username)
    if not row or not pwd_context.verify(req.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(
        subject=str(row["id"]),
        username=req.username,
        role=row["role"],
    )
    return {"access_token": token, "token_type": "bearer"}


def _get_redis(request: Request) -> object | None:
    """Inject Redis from app state (wired in main.py lifespan)."""
    return getattr(request.app.state, "arq_pool", None)


@router.post("/logout")
async def logout(
    user: dict = Depends(get_current_user),
    redis=Depends(_get_redis),
):
    """Revoke the current token by adding its jti to the Redis blocklist."""
    jti = user.get("jti", "")
    if jti and redis is not None:
        exp = user.get("exp", 0)
        now = datetime.now(UTC).timestamp()
        ttl = max(int(exp - now), 1)
        await revoke_token(redis, jti, ttl)
    return {"status": "logged_out"}


@router.get("/me")
async def me(
    user: dict = Depends(get_current_user),
):
    """Return current user info extracted from JWT."""
    return {
        "user_id": user.get("sub"),
        "username": user.get("username"),
        "role": user.get("role"),
    }
