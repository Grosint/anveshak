"""Signal model — threshold-based intelligence notification."""

from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .base import AuditedModel


class SignalType(str, Enum):
    THRESHOLD_CROSSED = "threshold_crossed"  # cluster reached independent_source_count >= threshold
    CREDIBILITY_DROP = "credibility_drop"  # source credibility auto-downgraded
    NEW_CLUSTER = "new_cluster"  # new narrative cluster formed
    # Deprecated. Nothing fires this any more: #30 rebased the signal off the
    # English VADER lexicon onto the multilingual hostility measure. The
    # member stays because signals written before that rebase still carry the
    # value, and Signal.signal_type is strict, so removing it makes every
    # historical row unparseable.
    SENTIMENT_SHIFT = "sentiment_shift"
    # Mean multilingual hostility rose sharply in the recent window against
    # its baseline. Replaces SENTIMENT_SHIFT. See issue #30.
    HOSTILITY_SHIFT = "hostility_shift"
    # Item and account counts climbed while independent source count stayed
    # flat: amplification rather than reporting. See issue #32.
    MANUFACTURED_NARRATIVE = "manufactured_narrative"
    # Public content contained an explicit call to assemble. Reports what was
    # said; never that an event will occur. See issue #33.
    MOBILIZATION_CALL = "mobilization_call"


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
