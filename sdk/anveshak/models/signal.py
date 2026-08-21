"""Signal model — threshold-based intelligence notification."""

from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .base import AuditedModel


class SignalType(str, Enum):
    THRESHOLD_CROSSED = "threshold_crossed"  # cluster reached independent_source_count >= threshold
    CREDIBILITY_DROP = "credibility_drop"  # source credibility auto-downgraded
    NEW_CLUSTER = "new_cluster"  # new narrative cluster formed
    SENTIMENT_SHIFT = (
        "sentiment_shift"  # avg sentiment dropped sharply in recent window vs baseline
    )


class SignalStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class Signal(AuditedModel):
    """A threshold-based intelligence notification surfaced to the analyst.

    Fires when: independent_source_count >= topic.signal_threshold
    Delivered via: WebSocket push to connected analyst sessions.
    """

    topic_id: str
    signal_type: SignalType
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)  # cluster_id, source_names, etc.
    status: SignalStatus = SignalStatus.NEW
    cluster_id: Optional[str] = None
