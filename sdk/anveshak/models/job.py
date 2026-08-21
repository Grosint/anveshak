"""AnalysisJob model — async task queue state tracking."""

from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .base import AuditedModel


class JobType(str, Enum):
    SCRAPE = "scrape"
    NLP = "nlp"
    VISION = "vision"
    REPORT = "report"
    BACKFILL = "backfill"
    CLUSTER = "cluster"
    SIGNAL_CHECK = "signal_check"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AnalysisJob(AuditedModel):
    """Async task queue state record.

    All heavy processing (LLM inference, scraping, vision analysis)
    runs as ARQ background jobs tracked here.
    """

    job_type: JobType
    topic_id: Optional[str] = None
    status: JobStatus = JobStatus.QUEUED
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    arq_job_id: Optional[str] = None  # ARQ job identifier for polling
