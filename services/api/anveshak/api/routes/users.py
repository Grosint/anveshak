"""User management endpoints — CRUD for analysts and admins."""

from __future__ import annotations

from typing import Literal, Optional

import asyncpg
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_role
from ..db import audit as audit_db
from ..db import users as users_db
from ..db.pool import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    username: str
    password: str
    role: Literal["viewer", "analyst", "admin"] = "analyst"
    org_id: Optional[str] = None  # super-admin sets this; org-admin inherits own org


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    role: Literal["viewer", "analyst", "admin"]


@router.get("")
async def list_users(
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("admin", "super-admin")),
):
    """List all users (admin/super-admin). Returns users without password hashes."""
    return await users_db.list_users(db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("admin", "super-admin")),
):
    """Create a new user (admin/super-admin)."""
    # Determine org_id: super-admin can specify any, org-admin uses own org
    org_id = req.org_id if req.org_id else _user.get("org_id")
    try:
        user_id = await users_db.create_user(
            db, req.username, req.password, req.role, org_id=org_id
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' already exists",
        )
    await audit_db.log_action(
        db,
        _user["sub"],
        "user.create",
        "user",
        user_id,
        {"username": req.username, "role": req.role},
        request.client.host if request.client else "",
    )
    return {"user_id": user_id}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("admin", "super-admin")),
):
    """Delete a user (admin/super-admin)."""
    deleted = await users_db.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    await audit_db.log_action(
        db,
        _user["sub"],
        "user.delete",
        "user",
        user_id,
        ip_address=request.client.host if request.client else "",
    )
    return {"deleted": True}


@router.patch("/{user_id}/role")
async def update_role(
    user_id: str,
    req: UpdateRoleRequest,
    request: Request,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("admin", "super-admin")),
):
    """Update a user's role (admin/super-admin)."""
    await users_db.update_user_role(db, user_id, req.role)
    await audit_db.log_action(
        db,
        _user["sub"],
        "user.role_change",
        "user",
        user_id,
        {"new_role": req.role},
        request.client.host if request.client else "",
    )
    return {"user_id": user_id, "role": req.role}
