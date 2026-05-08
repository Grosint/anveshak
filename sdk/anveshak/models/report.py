"""Report model — immutable LLM-generated intelligence report."""
from pydantic import ConfigDict, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime
from .base import Labels, AuditedModel


class ReportType(str, Enum):
    INTELLIGENCE_BRIEF = "intelligence_brief"
    RESEARCH_SUMMARY = "research_summary"
    WEEKLY_DIGEST = "weekly_digest"


class ReportSourceWarning(AuditedModel):
    """Retroactive warning when a source cited in a report is later downgraded.

    Report itself is NEVER modified — warning is appended separately.
    Required by CLAUDE.md rule 4 (report immutability).
    """
    report_id: str
    source_id: str
    source_name: str
    warning_type: str = "credibility_downgraded"
    old_score: float
    new_score: float


class Report(AuditedModel):
    """An immutable LLM-generated OSINT intelligence report.

    CRITICAL: generated_at is set ONCE and NEVER updated.
    source_snapshot captures credibility scores at generation time.
    This is Anveshak's court-admissible output — immutability is non-negotiable.
    """
    topic_id: str
    report_type: ReportType
    time_window_start: datetime
    time_window_end: datetime
    credibility_min_filter: float = 30.0

    content_md: Optional[str] = None      # LLM-generated markdown
    content_html: Optional[str] = None    # rendered HTML
    pdf_path: Optional[str] = None        # storage path for PDF

    geojson: Optional[dict[str, Any]] = None       # GeoJSON FeatureCollection
    confidence_score: Optional[float] = None        # 0.0–1.0

    # Immutability fields
    generated_at: Optional[datetime] = None         # SET ONCE. NEVER UPDATED.
    source_snapshot: dict[str, Any] = Field(        # credibility scores at generation time
        default_factory=dict
    )
    content_item_count: int = 0


class ReportJob(AuditedModel):
    """Tracks async report generation job state."""
    topic_id: str
    report_type: ReportType
    report_id: Optional[str] = None       # set when report row created
    status: str = "queued"                # queued|running|complete|failed
    error: Optional[str] = None
