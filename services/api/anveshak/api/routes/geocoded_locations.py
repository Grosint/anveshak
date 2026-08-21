"""Geocoded locations endpoints — analyst override + listing."""

from __future__ import annotations

from typing import Optional

import structlog
from anveshak.db import DBConnection
from anveshak.models import Labels
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..auth.rbac import require_role
from ..db.pool import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/geocoded-locations", tags=["geocoded-locations"])


# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_GET_GEOCODED_LOCATION = """
    SELECT id, entity_text_normalized, entity_type,
           latitude, longitude, geocode_confidence, geocode_source,
           geocoded_at, labels, created_at, updated_at
    FROM geocoded_locations
    WHERE id = $1::uuid
"""

SQL_LIST_GEOCODED_LOCATIONS = """
    SELECT id, entity_text_normalized, entity_type,
           latitude, longitude, geocode_confidence, geocode_source,
           geocoded_at, created_at
    FROM geocoded_locations
    ORDER BY entity_text_normalized
    LIMIT $1 OFFSET $2
"""

SQL_LIST_GEOCODED_LOCATIONS_BY_TYPE = """
    SELECT id, entity_text_normalized, entity_type,
           latitude, longitude, geocode_confidence, geocode_source,
           geocoded_at, created_at
    FROM geocoded_locations
    WHERE entity_type = $1
    ORDER BY entity_text_normalized
    LIMIT $2 OFFSET $3
"""

SQL_UPDATE_GEOCODED_LOCATION = """
    UPDATE geocoded_locations
    SET latitude = $2, longitude = $3,
        geocode_source = 'analyst_override',
        updated_at = NOW()
    WHERE id = $1::uuid
"""


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class UpdateGeocodedLocationRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    latitude: float
    longitude: float
    # default_factory, not {}: pydantic does not validate defaults, so `= {}`
    # left .labels a plain dict whenever the caller omitted it, and anything
    # reading .labels.classification got an AttributeError.
    labels: Labels = Field(default_factory=Labels)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_geocoded_locations(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """List geocoded locations, optionally filtered by entity type."""
    if entity_type:
        rows = await db.fetch(SQL_LIST_GEOCODED_LOCATIONS_BY_TYPE, entity_type, limit, offset)
    else:
        rows = await db.fetch(SQL_LIST_GEOCODED_LOCATIONS, limit, offset)
    return [dict(r) for r in rows]


@router.get("/{location_id}")
async def get_geocoded_location(
    location_id: str,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Get a single geocoded location by ID."""
    row = await db.fetchrow(SQL_GET_GEOCODED_LOCATION, location_id)
    if not row:
        raise HTTPException(status_code=404, detail="Geocoded location not found")
    return dict(row)


@router.patch("/{location_id}")
async def update_geocoded_location(
    location_id: str,
    req: UpdateGeocodedLocationRequest,
    db: DBConnection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
):
    """Analyst override — correct coordinates for a geocoded location.

    Sets geocode_source to 'analyst_override' for provenance tracking.
    """
    # Verify location exists
    existing = await db.fetchrow(SQL_GET_GEOCODED_LOCATION, location_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Geocoded location not found")

    result = await db.execute(
        SQL_UPDATE_GEOCODED_LOCATION,
        location_id,
        req.latitude,
        req.longitude,
    )

    if result != "UPDATE 1":
        raise HTTPException(status_code=500, detail="Update failed")

    log.info(
        "geocoded_location.analyst_override",
        location_id=location_id,
        entity=existing["entity_text_normalized"],
        old_lat=existing["latitude"],
        old_lon=existing["longitude"],
        new_lat=req.latitude,
        new_lon=req.longitude,
        analyst=user.get("sub", "unknown"),
    )

    return {
        "id": location_id,
        "entity_text_normalized": existing["entity_text_normalized"],
        "entity_type": existing["entity_type"],
        "latitude": req.latitude,
        "longitude": req.longitude,
        "geocode_source": "analyst_override",
    }
