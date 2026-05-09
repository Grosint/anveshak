"""User management endpoints — CRUD for analysts and admins."""
from __future__ import annotations

from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..auth.jwt import get_current_user
from ..db.pool import get_db
from ..db import users as users_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    username: str
    password: str
    role: Literal["analyst", "admin"] = "analyst"


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    role: Literal["analyst", "admin"]


@router.get("")
async def list_users(
    db: asyncpg.Connection = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """List all users (admin only). Returns users without password hashes."""
    return await users_db.list_users(db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    db: asyncpg.Connection = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Create a new user (admin only)."""
    try:
        user_id = await users_db.create_user(db, req.username, req.password, req.role)
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' already exists",
        )
    return {"user_id": user_id}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Delete a user (admin only)."""
    deleted = await users_db.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}


@router.patch("/{user_id}/role")
async def update_role(
    user_id: str,
    req: UpdateRoleRequest,
    db: asyncpg.Connection = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Update a user's role (admin only)."""
    await users_db.update_user_role(db, user_id, req.role)
    return {"user_id": user_id, "role": req.role}
