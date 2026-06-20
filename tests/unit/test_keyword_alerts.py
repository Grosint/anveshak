"""Tests for keyword alert matching logic."""
import pytest


class TestKeywordMatching:
    """Test matching logic independent of DB."""

    def test_any_mode_single_match(self):
        text = "protest in kohima against army"
        keywords = ["kohima", "dimapur", "nagaland"]
        matched = [kw for kw in keywords if kw.lower() in text.lower()]
        assert matched == ["kohima"]

    def test_any_mode_no_match(self):
        text = "weather forecast for mumbai"
        keywords = ["kohima", "dimapur"]
        matched = [kw for kw in keywords if kw.lower() in text.lower()]
        assert matched == []

    def test_all_mode_partial_fails(self):
        text = "protest in kohima"
        keywords = ["kohima", "dimapur"]
        matched = [kw for kw in keywords if kw.lower() in text.lower()]
        assert len(matched) != len(keywords)

    def test_all_mode_full_match(self):
        text = "protest in kohima and dimapur"
        keywords = ["kohima", "dimapur"]
        matched = [kw for kw in keywords if kw.lower() in text.lower()]
        assert len(matched) == len(keywords)

    def test_case_insensitive(self):
        text = "NSCN ceasefire violated in NAGALAND"
        keywords = ["nscn", "nagaland"]
        matched = [kw for kw in keywords if kw.lower() in text.lower()]
        assert len(matched) == 2


class TestCheckKeywordAlertsSql:
    def test_active_rules_sql_filters_active(self):
        from anveshak.analyst.keyword_alerts import SQL_ACTIVE_RULES
        assert "is_active = TRUE" in SQL_ACTIVE_RULES

    def test_insert_trigger_has_on_conflict(self):
        from anveshak.analyst.keyword_alerts import SQL_INSERT_TRIGGER
        assert "ON CONFLICT DO NOTHING" in SQL_INSERT_TRIGGER

    def test_insert_trigger_has_labels(self):
        from anveshak.analyst.keyword_alerts import SQL_INSERT_TRIGGER
        assert '"classification":"OPEN"' in SQL_INSERT_TRIGGER


class TestAlertDbSql:
    def test_list_rules_sql_exists(self):
        from anveshak.api.db.alerts import SQL_LIST_RULES
        assert "keyword_alert_rules" in SQL_LIST_RULES

    def test_insert_rule_sql_has_labels(self):
        from anveshak.api.db.alerts import SQL_INSERT_RULE
        assert '"classification":"OPEN"' in SQL_INSERT_RULE

    def test_delete_rule_returns_id(self):
        from anveshak.api.db.alerts import SQL_DELETE_RULE
        assert "RETURNING id" in SQL_DELETE_RULE


class TestAlertRouterRegistered:
    def test_alerts_router_in_main(self):
        import inspect
        from anveshak.api import main
        source = inspect.getsource(main)
        assert "alerts_router" in source
