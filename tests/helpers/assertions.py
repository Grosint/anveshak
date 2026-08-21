"""Shared assertion helpers for structured test validation.

Usage:
    from tests.helpers.assertions import assert_has_fields, assert_valid_uuid

These replace weak assertions like `assert result is not None` with
structural checks that catch real bugs.
"""

from __future__ import annotations

import re
import uuid as _uuid


def assert_has_fields(obj: dict, fields: list[str], msg: str = "") -> None:
    """Assert that a dict contains all required fields with non-None values."""
    missing = [f for f in fields if f not in obj]
    if missing:
        raise AssertionError(
            f"Missing fields: {missing} in {list(obj.keys())}" + (f" — {msg}" if msg else "")
        )
    none_fields = [f for f in fields if obj[f] is None]
    if none_fields:
        raise AssertionError(f"Fields are None: {none_fields}" + (f" — {msg}" if msg else ""))


def assert_valid_uuid(value: str, msg: str = "") -> None:
    """Assert that a string is a valid UUID4."""
    try:
        _uuid.UUID(value, version=4)
    except (ValueError, AttributeError):
        raise AssertionError(f"Not a valid UUID4: {value!r}" + (f" — {msg}" if msg else ""))


def assert_valid_content_hash(value: str, msg: str = "") -> None:
    """Assert that a string is a valid SHA-256 hex digest (64 chars)."""
    if not isinstance(value, str) or not re.match(r"^[0-9a-f]{64}$", value):
        raise AssertionError(f"Not a valid SHA-256 hash: {value!r}" + (f" — {msg}" if msg else ""))


def assert_valid_labels(labels: dict, msg: str = "") -> None:
    """Assert that labels dict has the required Anveshak structure."""
    required = {"classification", "domain", "owner_org"}
    if not isinstance(labels, dict):
        raise AssertionError(
            f"Labels must be dict, got {type(labels).__name__}" + (f" — {msg}" if msg else "")
        )
    missing = required - set(labels.keys())
    if missing:
        raise AssertionError(
            f"Labels missing required keys: {missing}" + (f" — {msg}" if msg else "")
        )


def assert_score_in_range(
    score: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    msg: str = "",
) -> None:
    """Assert that a score is a float within the given range."""
    if not isinstance(score, (int, float)):
        raise AssertionError(
            f"Score must be numeric, got {type(score).__name__}: {score!r}"
            + (f" — {msg}" if msg else "")
        )
    if not (min_val <= score <= max_val):
        raise AssertionError(
            f"Score {score} outside range [{min_val}, {max_val}]" + (f" — {msg}" if msg else "")
        )


def assert_probability(score: float, msg: str = "") -> None:
    """Assert that a score is a float in [0.0, 1.0] — for deepfake scores etc."""
    assert_score_in_range(score, 0.0, 1.0, msg or "expected probability 0.0–1.0")
