"""JWT authentication for Anveshak API.

Includes:
  - Token creation with role + jti (JWT ID)
  - Token verification
  - Token revocation (Redis-backed blocklist)
  - JWT secret validation (startup guard)
  - Password hashing (bcrypt)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..settings import settings


class _BcryptContext:
    """Direct bcrypt wrapper — avoids passlib 1.7 / bcrypt>=4 incompatibility."""

    def verify(self, secret: str, hashed: str) -> bool:
        return _bcrypt.checkpw(secret.encode(), hashed.encode())

    def hash(self, secret: str) -> str:
        return _bcrypt.hashpw(secret.encode(), _bcrypt.gensalt(rounds=12)).decode()


pwd_context = _BcryptContext()
bearer_scheme = HTTPBearer()


def create_access_token(
    subject: str,
    username: str = "",
    role: str = "analyst",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT with sub, username, role, jti, exp, iat."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": subject,
        "username": username,
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict:
    """Decode and verify a JWT. Raises 401 on invalid/expired."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency — extract and verify current user from Bearer token."""
    return verify_token(credentials.credentials)


# ---------------------------------------------------------------------------
# Token revocation (Redis-backed)
# ---------------------------------------------------------------------------

async def revoke_token(redis, jti: str, ttl_seconds: int) -> None:
    """Add a jti to the Redis blocklist with TTL matching token expiry."""
    await redis.setex(f"blocklist:{jti}", ttl_seconds, "1")


async def is_token_revoked(redis, jti: str) -> bool:
    """Check if a jti is in the Redis blocklist."""
    return bool(await redis.exists(f"blocklist:{jti}"))


# ---------------------------------------------------------------------------
# Startup guard
# ---------------------------------------------------------------------------

def validate_jwt_secret(secret: str) -> None:
    """Raise ValueError if the JWT secret is the insecure default.

    Called during API lifespan startup to prevent deployment with
    forgeable tokens.
    """
    if secret == "change-me-in-production":
        raise ValueError(
            "JWT secret is 'change-me-in-production' — "
            "set JWT_SECRET_KEY to a secure value before deployment"
        )
