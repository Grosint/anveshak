"""The score a Source is created at, at the route seam - issue #51, ADR 0004.

The rubric computes a number and the SDK tests cover that. These cover the
wiring: that the routes actually ask it, that a stated score still wins, and
that a Source the rubric placed carries a row saying why. Without them the
rubric can be correct and reach nothing, which is the failure the AGENTS
wiring check exists for.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from anveshak.source_rubric import load_rubric

pytestmark = pytest.mark.unit

HANDLE = "https://declared.example.in/feed"
UNDECLARED = "https://undeclared.example.in/feed"


@pytest.fixture
def rubric_declaring(tmp_path, monkeypatch):
    """A rubric declaring HANDLE as meeting one criterion worth +10."""
    path = tmp_path / "source_rubric.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "owner": "customer",
                "baseline": 50.0,
                "criteria": [
                    {
                        "id": "named_editorial_responsibility",
                        "label": "Named editorial responsibility",
                        "test": "The masthead names an editor.",
                        "points": 10,
                    }
                ],
                "outlets": [
                    {
                        "handle": HANDLE,
                        "name": "Declared Outlet",
                        "criteria_met": ["named_editorial_responsibility"],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("SOURCE_RUBRIC_PATH", str(path))
    load_rubric.cache_clear()
    yield
    load_rubric.cache_clear()


def _repo_root() -> Path:
    """The checkout root, by its marker file rather than by a parent count."""
    root = Path(__file__).resolve().parent
    while not (root / "uv.lock").exists():
        assert root != root.parent, "no uv.lock above this test"
        root = root.parent
    return root


def _transactional_conn() -> AsyncMock:
    """`async with db.transaction()` needs a context manager, not a coroutine."""
    conn = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    return conn


async def _create(handle: str, *, stated: float | None):
    from anveshak.api.routes.sources import CreateSourceRequest, create_source

    conn = _transactional_conn()
    request = MagicMock()
    request.client = None
    user = {"sub": "u-1", "user_id": "u-1", "role": "analyst", "org_id": "org-test"}

    with (
        patch("anveshak.api.routes.sources.sources_db") as sources_db,
        patch("anveshak.api.routes.sources.audit_db") as audit_db,
    ):
        sources_db.insert_source = AsyncMock()
        sources_db.log_creation_baseline = AsyncMock()
        sources_db.update_source_health = AsyncMock()
        sources_db.add_org_source = AsyncMock()
        sources_db.add_topic_source = AsyncMock()
        audit_db.log_action = AsyncMock()

        await create_source(
            req=CreateSourceRequest(
                name="Declared Outlet",
                url_or_handle=handle,
                platform="telegram",
                credibility_score=stated,
            ),
            request=request,
            db=conn,
            user=user,
        )
        return sources_db


class TestRegisteringASource:
    async def test_a_declared_outlet_is_created_at_its_structural_baseline(self, rubric_declaring):
        sources_db = await _create(HANDLE, stated=None)
        assert sources_db.insert_source.call_args.args[5] == 60.0

    async def test_a_declared_outlet_carries_a_row_saying_why(self, rubric_declaring):
        """User story 2. Otherwise the only record of why a Source starts at
        60 is a log line, and the audit log an analyst opens is empty."""
        sources_db = await _create(HANDLE, stated=None)
        sources_db.log_creation_baseline.assert_called_once()
        kwargs = sources_db.log_creation_baseline.call_args.kwargs
        assert kwargs["baseline"] == 60.0
        assert kwargs["neutral_score"] == 50.0
        assert "named_editorial_responsibility" in kwargs["reason"]
        assert kwargs["changed_by"].endswith("2"), "the row names the rubric version"

    async def test_an_undeclared_outlet_is_created_neutral_with_no_row(self, rubric_declaring):
        sources_db = await _create(UNDECLARED, stated=None)
        assert sources_db.insert_source.call_args.args[5] == 50.0
        sources_db.log_creation_baseline.assert_not_called()

    async def test_a_stated_score_wins_and_writes_no_baseline_row(self, rubric_declaring):
        """The row would claim the rubric placed a score it did not."""
        sources_db = await _create(HANDLE, stated=31.0)
        assert sources_db.insert_source.call_args.args[5] == 31.0
        sources_db.log_creation_baseline.assert_not_called()


class TestApprovingACatalogEntry:
    async def test_an_approved_entry_takes_the_same_baseline(self, rubric_declaring):
        from anveshak.api.routes.catalog import _insert_with_baseline

        conn = _transactional_conn()
        with patch("anveshak.api.routes.catalog.sources_db") as sources_db:
            sources_db.insert_source = AsyncMock()
            sources_db.log_creation_baseline = AsyncMock()

            await _insert_with_baseline(
                conn,
                source_id="src-1",
                name="Declared Outlet",
                handle=HANDLE,
                platform="web",
                now=None,
                org_id="org-test",
            )

        assert sources_db.insert_source.call_args.kwargs["credibility_score"] == 60.0
        assert sources_db.insert_source.call_args.kwargs["org_id"] == "org-test"
        sources_db.log_creation_baseline.assert_called_once()
        # Both columns are NOT NULL references to organizations, so a row
        # without it is one postgres refuses.
        assert sources_db.log_creation_baseline.call_args.kwargs["org_id"] == "org-test"

    async def test_both_approval_routes_pass_the_caller_org(self):
        """The helper cannot default it, and a route that forgets writes NULL
        into a NOT NULL foreign key. require_org_context rather than
        get_user_org, so a caller with no organisation is a 400 rather than
        a refused insert."""
        text = (_repo_root() / "services/api/anveshak/api/routes/catalog.py").read_text()
        assert text.count("_insert_with_baseline(") == 3, "definition plus two call sites"
        assert text.count("org_id=require_org_context(user)") == 2


class TestEveryCreationPathAsksTheRubric:
    def test_no_creation_path_hardcodes_the_neutral_score(self):
        """Three paths create Sources, and each used to carry its own 50.0."""
        root = _repo_root()
        for relative in (
            "services/api/anveshak/api/routes/sources.py",
            "services/api/anveshak/api/routes/catalog.py",
            "scripts/import_corpus.py",
        ):
            text = (root / relative).read_text()
            assert "creation_score(" in text, f"{relative} does not ask the rubric"
            assert not re.search(r"credibility_score\s*=\s*50(\.0)?\b", text), (
                f"{relative} still carries its own copy of the neutral score"
            )
