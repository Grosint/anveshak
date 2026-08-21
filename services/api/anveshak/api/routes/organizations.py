"""Organization management endpoints — CRUD for multi-tenancy."""

from __future__ import annotations

from typing import Optional

import asyncpg
from anveshak.db import DBConnection
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..auth.rbac import require_role
from ..db import organizations as org_db
from ..db.pool import get_db

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class CreateOrgRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    slug: str


class UpdateOrgRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_organizations(
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("super-admin")),
):
    """List all organizations (super-admin only)."""
    return await org_db.list_organizations(db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: CreateOrgRequest,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("super-admin")),
):
    """Create a new organization (super-admin only)."""
    try:
        org_id = await org_db.create_organization(db, req.name, req.slug)
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization '{req.name}' or slug '{req.slug}' already exists",
        )
    return {"org_id": org_id}


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("super-admin")),
):
    """Get a single organization (super-admin only)."""
    org = await org_db.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{org_id}")
async def update_organization(
    org_id: str,
    req: UpdateOrgRequest,
    db: DBConnection = Depends(get_db),
    _user: dict = Depends(require_role("super-admin")),
):
    """Update an organization (super-admin only)."""
    org = await org_db.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    await org_db.update_organization(db, org_id, name=req.name, is_active=req.is_active)
    return {"org_id": org_id, "updated": True}
