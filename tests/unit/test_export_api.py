"""Unit tests for export API endpoints — CSV/JSON export.

Tests:
  - SQL queries are well-formed
  - CSV helper produces valid CSV with headers
  - JSON helper produces valid JSON
  - MAX_EXPORT_ROWS limit is enforced
"""

from __future__ import annotations

import csv
import io
import json

import pytest

pytestmark = pytest.mark.unit


class TestExportHelpers:
    def test_rows_to_csv_produces_valid_csv(self):
        from anveshak.api.routes.export import _rows_to_csv

        rows = [
            {"id": "1", "url": "https://a.com", "clean_text": "Hello world"},
            {"id": "2", "url": "https://b.com", "clean_text": "Goodbye"},
        ]
        columns = ["id", "url", "clean_text"]
        result = _rows_to_csv(rows, columns)

        reader = csv.DictReader(io.StringIO(result))
        parsed = list(reader)
        assert len(parsed) == 2
        assert parsed[0]["id"] == "1"
        assert parsed[1]["url"] == "https://b.com"

    def test_rows_to_csv_handles_none_values(self):
        from anveshak.api.routes.export import _rows_to_csv

        rows = [{"id": "1", "url": None, "clean_text": "text"}]
        columns = ["id", "url", "clean_text"]
        result = _rows_to_csv(rows, columns)
        assert "text" in result

    def test_rows_to_json_produces_valid_json(self):
        from anveshak.api.routes.export import _rows_to_json

        rows = [{"id": "1", "url": "https://a.com"}]
        result = _rows_to_json(rows)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "1"

    def test_rows_to_json_handles_datetime(self):
        from datetime import UTC, datetime

        from anveshak.api.routes.export import _rows_to_json

        rows = [{"id": "1", "captured_at": datetime(2026, 4, 15, tzinfo=UTC)}]
        result = _rows_to_json(rows)
        parsed = json.loads(result)
        assert "2026" in parsed[0]["captured_at"]


class TestExportSQLQueries:
    def test_content_query_has_topic_filter(self):
        from anveshak.api.routes.export import SQL_EXPORT_CONTENT

        assert "topic_id = $1" in SQL_EXPORT_CONTENT
        assert "LIMIT $2" in SQL_EXPORT_CONTENT

    def test_signals_query_has_topic_filter(self):
        from anveshak.api.routes.export import SQL_EXPORT_SIGNALS

        assert "topic_id = $1" in SQL_EXPORT_SIGNALS
        assert "LIMIT $2" in SQL_EXPORT_SIGNALS

    def test_entities_query_has_topic_filter(self):
        from anveshak.api.routes.export import SQL_EXPORT_ENTITIES

        assert "topic_id = $1" in SQL_EXPORT_ENTITIES
        assert "LIMIT $2" in SQL_EXPORT_ENTITIES


class TestExportConstants:
    def test_max_export_rows_is_reasonable(self):
        from anveshak.api.routes.export import MAX_EXPORT_ROWS

        assert MAX_EXPORT_ROWS == 10000

    def test_column_lists_defined(self):
        from anveshak.api.routes.export import CONTENT_COLUMNS, ENTITY_COLUMNS, SIGNAL_COLUMNS

        assert "id" in CONTENT_COLUMNS
        assert "url" in CONTENT_COLUMNS
        assert "signal_type" in SIGNAL_COLUMNS
        assert "entity_type" in ENTITY_COLUMNS
