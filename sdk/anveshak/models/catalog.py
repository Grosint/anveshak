"""Source discovery models — catalog, discovered sources, LLM suggestions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .base import AuditedModel, Labels


class CatalogEntry(AuditedModel):
    """A curated OSINT source in the pre-built knowledge base.

    Organized by domain tags (china, pakistan, cyber, etc.) with
    effectiveness analytics computed by a weekly ARQ job.
    """

    name: str
    url_or_handle: str
    platform: str  # web|telegram|reddit|bluesky|rss|twitter
    domain_tags: list[str] = Field(default_factory=list)
    reliability_tier: str = "C"  # S, A, B, C
    bias_indicator: str = "unknown"
    risk_level: str = "low"  # low, medium, high
    language: str = "en"
    category: str = "news"  # news, government, military, social, blog
    description: str = ""
    subscriber_count: Optional[int] = None
    activity_frequency: str = "unknown"  # daily, weekly, sporadic
    # Effectiveness analytics (computed by weekly job)
    signal_contribution_count: int = 0
    relevance_hit_rate: Optional[float] = None
    cluster_participation_rate: Optional[float] = None
    topics_approved_count: int = 0
    recommendation_rank: str = "curated"  # most_recommended, proven, curated, low_performer


class CatalogApproval(BaseModel):
    """Tracks which catalog entries were approved for which topics."""

    model_config = ConfigDict(strict=True)

    catalog_entry_id: str
    topic_id: str
    source_id: str
    approved_by: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    labels: Labels


class DiscoveredSource(AuditedModel):
    """A source discovered via snowball, forwarding, entity search, or LLM suggestion."""

    topic_id: str
    domain_or_handle: str
    platform: str = "web"
    discovery_method: str  # snowball, forwarding, entity_search, llm_suggestion
    citation_count: int = 1
    confidence_score: Optional[float] = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending, approved, dismissed
    source_id: Optional[str] = None  # set when approved → source created


class SourceSuggestion(BaseModel):
    """LLM-generated source type recommendation (Level 4).

    Validated via Pydantic before storage (AGENTS.md rule 9).
    Provides guidance, not specific URLs — analyst acts manually.
    """

    model_config = ConfigDict(strict=True)

    platform: str
    description: str
    search_terms: list[str]
    reasoning: str
    labels: Labels
