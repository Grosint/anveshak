"""Unit tests — new source API filter SQL (criteria 7.9, 7.10).

Tests the SQL constants and function signatures — no live DB required.
"""
import pytest

from anveshak.api.db.sources import (
    SQL_LIST_SOURCES_BELOW,
    SQL_TOPIC_SOURCES,
    list_sources_below,
    list_topic_sources,
)
import inspect


# ---------------------------------------------------------------------------
# SQL_LIST_SOURCES_BELOW (7.9)
# ---------------------------------------------------------------------------

def test_list_sources_below_sql_has_threshold_param():
    """SQL must use $1 for threshold parameter."""
    assert "$1" in SQL_LIST_SOURCES_BELOW


def test_list_sources_below_sql_filters_credibility():
    """SQL must filter on credibility_score < threshold."""
    normalised = " ".join(SQL_LIST_SOURCES_BELOW.split()).upper()
    assert "CREDIBILITY_SCORE" in normalised
    assert "< $1" in " ".join(SQL_LIST_SOURCES_BELOW.split())


def test_list_sources_below_sql_orders_ascending():
    """Worst sources should appear first (ASC)."""
    normalised = " ".join(SQL_LIST_SOURCES_BELOW.split()).upper()
    assert "ORDER BY CREDIBILITY_SCORE ASC" in normalised


# ---------------------------------------------------------------------------
# SQL_TOPIC_SOURCES (7.10)
# ---------------------------------------------------------------------------

def test_topic_sources_sql_has_topic_param():
    """SQL must use $1 for topic_id parameter."""
    assert "$1" in SQL_TOPIC_SOURCES


def test_topic_sources_sql_joins_content_items():
    """SQL must join sources through content_items to find contributing sources."""
    normalised = " ".join(SQL_TOPIC_SOURCES.split()).upper()
    assert "CONTENT_ITEMS" in normalised
    assert "JOIN" in normalised


def test_topic_sources_sql_includes_item_count():
    """SQL must include item_count so the frontend can sort by activity."""
    normalised = " ".join(SQL_TOPIC_SOURCES.split()).upper()
    assert "COUNT" in normalised
    assert "ITEM_COUNT" in normalised


def test_topic_sources_sql_orders_by_item_count():
    """Most active source should appear first."""
    normalised = " ".join(SQL_TOPIC_SOURCES.split()).upper()
    assert "ORDER BY ITEM_COUNT DESC" in normalised


# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

def test_list_sources_below_signature():
    sig = inspect.signature(list_sources_below)
    params = list(sig.parameters.keys())
    assert "conn" in params
    assert "threshold" in params


def test_list_topic_sources_signature():
    sig = inspect.signature(list_topic_sources)
    params = list(sig.parameters.keys())
    assert "conn" in params
    assert "topic_id" in params
