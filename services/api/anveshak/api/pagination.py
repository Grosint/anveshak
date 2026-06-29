"""Shared pagination utilities for list endpoints.

Provides a standard paginated response wrapper and helpers for adding
COUNT(*) OVER() + LIMIT/OFFSET to existing SQL queries.
"""
from __future__ import annotations

from typing import Any


def paginate_rows(
    rows: list[dict[str, Any]],
    total: int,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    """Wrap a list of row dicts into a paginated response envelope.

    Used at the route level — DB functions continue returning plain lists.
    """
    return {
        "items": rows,
        "total": total,
        "offset": offset,
        "limit": limit,
    }
