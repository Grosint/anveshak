"""Source Assessment model — immutable source intelligence card.

Follows Report immutability pattern (CLAUDE.md rule 4):
generated_at is set ONCE via WHERE generated_at IS NULL guard.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .base import AuditedModel, Labels


class SourceStats(BaseModel):
    """Deterministic statistics computed from SQL — no LLM involved."""

    model_config = ConfigDict(strict=True)

    total_posts: int
    first_post: Optional[datetime] = None
    last_post: Optional[datetime] = None
    avg_posts_per_day: float
    engagement: dict[str, int]  # {likes, comments, shares, views}
    language_breakdown: list[dict[str, Any]]  # [{language, count, pct}]
    volume_timeline: list[dict[str, Any]]  # [{date, count}]
    top_entities: list[dict[str, Any]]  # [{entity_text, entity_type, count}]
    identifier_overlap: list[dict[str, Any]]  # [{identifier_type, value, source_count}]
    cluster_participation: list[dict[str, Any]]  # [{cluster_id, label, item_count}]
    sentiment_distribution: dict[str, int]  # {negative, neutral, positive}
    credibility_trajectory: list[dict[str, Any]]  # [{date, old_score, new_score, reason}]
    labels: Labels


class SourceAssessment(AuditedModel):
    """An immutable source intelligence card scoped to a topic.

    CRITICAL: generated_at is set ONCE and NEVER updated.
    source_snapshot captures credibility scores at generation time.
    """

    topic_id: str
    source_id: str
    org_id: str
    time_window_start: datetime
    time_window_end: datetime

    # Phase 0: deterministic stats
    stats: Optional[SourceStats] = None

    # Phase 1: platform metadata (bio, followers, account age)
    platform_metadata: Optional[dict[str, Any]] = None

    # Phase 2: LLM brief
    brief_md: Optional[str] = None
    confidence_score: Optional[float] = None

    # Immutability fields
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    content_item_count: int = 0
    generated_at: Optional[datetime] = None  # SET ONCE. NEVER UPDATED.
    generation_error: Optional[str] = None
    arq_job_id: Optional[str] = None
