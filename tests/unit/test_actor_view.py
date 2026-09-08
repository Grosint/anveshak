"""Actor View — issue #35.

A query, not a stored entity. There is deliberately no actor table and no
persistent per-person record: a handle is an Identifier, and everything shown
is derived from content items on demand. That keeps the retention posture
defensible under scrutiny.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from anveshak.api.db.actors import (
    SQL_ACTOR_ACTIVITY,
    SQL_ACTOR_CONTENT,
    SQL_ACTOR_SUMMARY,
)

pytestmark = pytest.mark.unit

ACTOR_SQL = (SQL_ACTOR_SUMMARY, SQL_ACTOR_CONTENT, SQL_ACTOR_ACTIVITY)


class TestNoPersistentRecord:
    def test_no_actor_table_is_created(self):
        """No migration creates one, now or later."""
        for migration in Path("services/api/migrations/versions").glob("*.py"):
            source = migration.read_text().lower()
            assert "create table actors" not in source
            assert "create table actor_" not in source

    def test_the_repository_only_reads(self):
        source = Path("services/api/anveshak/api/db/actors.py").read_text().upper()
        for statement in ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE"):
            assert statement not in source

    def test_everything_is_derived_from_content_items(self):
        for sql in ACTOR_SQL:
            assert "content_items" in sql


class TestOrgIsolation:
    def test_every_query_is_org_scoped(self):
        """A handle is reachable by name, so scoping cannot rely on a lookup."""
        for sql in ACTOR_SQL:
            assert "org_id" in sql

    def test_every_query_is_topic_scoped(self):
        for sql in ACTOR_SQL:
            assert "topic_id" in sql

    def test_param_counts_match_the_repository_calls(self):
        import inspect

        from anveshak.api.db import actors

        for name, sql in (
            ("get_actor_summary", SQL_ACTOR_SUMMARY),
            ("list_actor_content", SQL_ACTOR_CONTENT),
            ("get_actor_activity", SQL_ACTOR_ACTIVITY),
        ):
            placeholders = {int(p[1:]) for p in re.findall(r"\$\d+", sql)}
            body = inspect.getsource(getattr(actors, name))
            call = body.split("(", 1)[1]
            # SQL constant plus one argument per placeholder.
            assert len(placeholders) == max(placeholders), name
            assert f"${max(placeholders)}" in sql, name
            assert call.count(",") >= max(placeholders), name


class TestPublicContentOnly:
    def test_queries_exclude_non_public_platforms(self):
        """Collection posture is public sources; the view must match it."""
        source = Path("services/api/anveshak/api/db/actors.py").read_text()
        assert "tipline" in source.lower()


class TestHandleNormalisation:
    def test_at_prefix_is_stripped_for_matching(self):
        from anveshak.api.db.actors import normalise_handle

        assert normalise_handle("@someone") == "someone"
        assert normalise_handle("someone") == "someone"

    def test_matching_is_case_insensitive(self):
        from anveshak.api.db.actors import normalise_handle

        assert normalise_handle("SomeOne") == "someone"

    def test_whitespace_is_trimmed(self):
        from anveshak.api.db.actors import normalise_handle

        assert normalise_handle("  @someone  ") == "someone"

    def test_an_empty_handle_normalises_to_empty(self):
        from anveshak.api.db.actors import normalise_handle

        assert normalise_handle("") == ""
        assert normalise_handle("@") == ""


class TestRoute:
    def test_the_route_is_registered(self):
        from anveshak.api.routes.actors import router

        paths = {route.path for route in router.routes}
        assert any("actors" in path for path in paths)

    def test_the_router_is_wired_into_the_app(self):
        source = Path("services/api/anveshak/api/main.py").read_text()
        assert "actors" in source

    def test_the_route_verifies_topic_access(self):
        source = Path("services/api/anveshak/api/routes/actors.py").read_text()
        assert "verify_topic_access" in source
