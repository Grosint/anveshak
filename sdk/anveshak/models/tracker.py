"""Tracker model — persistent analyst-owned case files."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from .base import AuditedModel


class Tracker(AuditedModel):
    """A permanent analyst-owned case file that survives Leiden re-clustering.

    Trackers are seeded from narrative clusters or created from scratch.
    They accumulate content via auto-matching (review queue) and manual addition.
    """

    case_number: str
    org_id: Optional[str] = None
    topic_id: str
    origin_cluster_id: Optional[str] = None
    title: str
    external_case_ref: Optional[str] = None
    centroid: Optional[list[float]] = None
    centroid_threshold: float = 0.70
    status: Literal["watching", "active", "concluded"] = "watching"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    assigned_to: Optional[str] = None
    created_by: str
    concluded_by: Optional[str] = None
    concluded_at: Optional[datetime] = None
    closing_summary: Optional[str] = None
