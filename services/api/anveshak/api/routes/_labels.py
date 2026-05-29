"""Dynamic labels helper — replaces hardcoded _LABELS_JSON constants."""
from __future__ import annotations

import json


def make_labels(domain: str = "osint", **extra: str) -> str:
    """Build a labels JSON string with classification and domain.

    Usage:
        make_labels()  # '{"classification":"OPEN","domain":"osint"}'
        make_labels(domain="report", topic_id="t-1")
    """
    labels = {"classification": "OPEN", "domain": domain, **extra}
    return json.dumps(labels)
