"""Topic model — a user-defined monitoring subject."""

from enum import Enum
from typing import Optional

from pydantic import Field

from .base import AuditedModel


class TopicStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Topic(AuditedModel):
    """A user-defined subject/topic for OSINT monitoring.

    The analyst creates a topic with keywords and the system monitors it.
    Everything in Anveshak is scoped to a topic.
    """

    name: str
    keywords: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["en"])
    credibility_min: float = 30.0  # minimum source credibility to include
    signal_threshold: int = 3  # independent sources needed to fire Signal
    status: TopicStatus = TopicStatus.ACTIVE
    clip_categories: list[str] = Field(default_factory=list)  # for CLIP zero-shot
    scheduled_report_cron: Optional[str] = None  # e.g. "0 6 * * 1" = Monday 6am
    scheduled_report_type: Optional[str] = None  # intelligence_brief | weekly_digest
