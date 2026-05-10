"""Role-based access control for Anveshak API.

Provides require_role() — a FastAPI dependency factory that enforces
role-based authorization on route handlers.

Usage:
    @router.post("/admin-action")
    async def admin_action(user=Depends(require_role("admin"))):
        ...

    @router.get("/read")
    async def read_data(user=Depends(require_role("viewer", "analyst", "admin"))):
        ...
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from .jwt import get_current_user


def require_role(*allowed_roles: str) -> Callable:
    """Return a FastAPI dependency that enforces role membership.

    Args:
        *allowed_roles: One or more role strings. User must have one of these.

    Returns:
        Async dependency that returns the user dict if authorized, raises 403 otherwise.
    """

    async def _check_role(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}",
            )
        return user

    return _check_role
