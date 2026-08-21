"""Unit tests — report_source_warnings dedup guard (criterion 7.6).

Verifies that the ON CONFLICT (report_id, source_id) DO NOTHING clause
in SQL_INSERT_SOURCE_WARNING prevents duplicate warning rows.
"""

from anveshak.reporter.db import SQL_INSERT_SOURCE_WARNING


def test_sql_insert_source_warning_has_on_conflict_clause():
    """SQL must contain ON CONFLICT clause to enforce dedup at DB level."""
    normalised = " ".join(SQL_INSERT_SOURCE_WARNING.split()).upper()
    assert "ON CONFLICT" in normalised, (
        "SQL_INSERT_SOURCE_WARNING must include ON CONFLICT clause — "
        "without it, check_source_warnings inserts duplicate rows every 6 hours"
    )
    assert "DO NOTHING" in normalised, (
        "ON CONFLICT must use DO NOTHING — duplicate (report_id, source_id) pairs "
        "should be silently ignored, not updated"
    )


def test_sql_insert_source_warning_targets_correct_columns():
    """ON CONFLICT must target (report_id, source_id) — the unique index columns."""
    normalised = " ".join(SQL_INSERT_SOURCE_WARNING.split()).upper()
    assert "REPORT_ID" in normalised
    assert "SOURCE_ID" in normalised
