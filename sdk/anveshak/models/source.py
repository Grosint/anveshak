"""Source model — a registered OSINT source with credibility tracking."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, UTC
import uuid
from .base import Labels, AuditedModel


class Source(AuditedModel):
    """A registered OSINT source (news site, social account, RSS feed, etc.)"""
    name: str
    url_or_handle: str
    platform: str                          # web|telegram|twitter|reddit|bluesky|rss|upload
    credibility_score: float = 50.0       # 0–100, starts at 50 for new sources
    auto_score_enabled: bool = True        # allow system to auto-update credibility
    last_checked_at: Optional[datetime] = None
    is_active: bool = True


class CredibilityAuditLog(BaseModel):
    """Immutable audit trail for every credibility score change.

    Required by CLAUDE.md rule 8: every credibility change must be logged.
    """
    model_config = ConfigDict(strict=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    old_score: float
    new_score: float
    reason: str                            # human-readable reason for change
    changed_by: str                        # "user:{user_id}" or "system:{component}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    labels: Labels
