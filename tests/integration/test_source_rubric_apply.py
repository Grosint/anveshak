"""Applying the structural baseline to real Sources - issue #51, ADR 0004.

The seam is the audit log. A credibility score that moved without a row in
credibility_audit_log is the silent change architectural rule 8 exists to
prevent, and a unit test on the decision function cannot see whether the two
statements actually both ran.

Requires Docker Compose with postgres running.
Run with: pytest tests/integration/test_source_rubric_apply.py -m integration
"""

from __future__ import annotations

import uuid

import pytest
import yaml
from anveshak.source_rubric import load_rubric

from scripts.apply_source_rubric import CHANGED_BY_PREFIX, apply_rubric

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def rubric_declaring(tmp_path, monkeypatch):
    """Point the loader at a rubric that declares the given handle."""

    def write(handle: str, criteria_met: list[str]) -> None:
        path = tmp_path / "source_rubric.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "owner": "customer",
                    "baseline": 50.0,
                    "criteria": [
                        {
                            "id": "named_editorial_responsibility",
                            "label": "Named editorial responsibility",
                            "test": "The masthead names an editor.",
                            "points": 10,
                        },
                        {
                            "id": "corrections_policy_published",
                            "label": "Corrections policy published",
                            "test": "A corrections policy is published.",
                            "points": 8,
                        },
                    ],
                    "outlets": [
                        {
                            "handle": handle,
                            "name": "Declared Outlet",
                            "criteria_met": criteria_met,
                        }
                    ],
                }
            )
        )
        monkeypatch.setenv("SOURCE_RUBRIC_PATH", str(path))
        load_rubric.cache_clear()

    yield write
    load_rubric.cache_clear()


async def _audit_rows(db_pool, source_id: str) -> list:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT old_score, new_score, reason, changed_by "
            "FROM credibility_audit_log WHERE source_id = $1 ORDER BY created_at",
            source_id,
        )


async def _score(db_pool, source_id: str) -> float:
    async with db_pool.acquire() as conn:
        return float(
            await conn.fetchval("SELECT credibility_score FROM sources WHERE id = $1", source_id)
        )


async def test_a_baseline_is_applied_and_audited(db_pool, make_source, rubric_declaring):
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    source_id = await make_source(name="Rubric Outlet", url_or_handle=handle)
    rubric_declaring(handle, ["named_editorial_responsibility", "corrections_policy_published"])

    outcomes = await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    assert [o.status for o in outcomes] == ["applied"]
    assert await _score(db_pool, source_id) == 68.0

    rows = await _audit_rows(db_pool, source_id)
    assert len(rows) == 1, "rule 8: a score change writes exactly one audit row"
    assert rows[0]["new_score"] == 68.0
    assert rows[0]["changed_by"].startswith(CHANGED_BY_PREFIX)
    # User story 2: the basis is on the row, not only in a config file.
    assert "named_editorial_responsibility" in rows[0]["reason"]
    assert "corrections_policy_published" in rows[0]["reason"]


async def test_a_dry_run_writes_nothing(db_pool, make_source, rubric_declaring):
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    source_id = await make_source(name="Rubric Outlet", url_or_handle=handle)
    before = await _score(db_pool, source_id)
    rubric_declaring(handle, ["named_editorial_responsibility"])

    outcomes = await apply_rubric(db_pool, apply_changes=False, rebaseline=False)

    assert [o.status for o in outcomes] == ["would_apply"]
    assert await _score(db_pool, source_id) == before
    assert await _audit_rows(db_pool, source_id) == []


async def test_a_second_run_does_not_reset_a_score_behaviour_moved(
    db_pool, make_source, rubric_declaring
):
    """The score is not the rubric's to keep. Once the baseline is set, the
    drop and boost passes own it, and a re-run must not undo them."""
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    source_id = await make_source(name="Rubric Outlet", url_or_handle=handle)
    rubric_declaring(handle, ["named_editorial_responsibility"])
    await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sources SET credibility_score = 41.0 WHERE id = $1", source_id
        )

    outcomes = await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    assert [o.status for o in outcomes] == ["skipped"]
    assert await _score(db_pool, source_id) == 41.0
    assert len(await _audit_rows(db_pool, source_id)) == 1


async def test_rebaselining_writes_its_own_audited_row(db_pool, make_source, rubric_declaring):
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    source_id = await make_source(name="Rubric Outlet", url_or_handle=handle)
    rubric_declaring(handle, ["named_editorial_responsibility"])
    await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    rubric_declaring(handle, ["named_editorial_responsibility", "corrections_policy_published"])
    outcomes = await apply_rubric(db_pool, apply_changes=True, rebaseline=True)

    assert [o.status for o in outcomes] == ["applied"]
    assert await _score(db_pool, source_id) == 68.0
    rows = await _audit_rows(db_pool, source_id)
    assert len(rows) == 2
    assert rows[1]["old_score"] == 60.0
    assert "Re-applied" in rows[1]["reason"]


async def test_a_declared_outlet_with_no_source_is_reported_not_skipped(
    db_pool, rubric_declaring
):
    """An outlet assessed but never registered is an operator mistake worth
    seeing, not a row to create."""
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    rubric_declaring(handle, ["named_editorial_responsibility"])

    outcomes = await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    assert [o.status for o in outcomes] == ["no_source"]


async def test_a_failing_audit_insert_rolls_the_score_back(
    db_pool, make_source, rubric_declaring, monkeypatch
):
    """The claim the transaction makes, tested in the direction that proves it.

    A score that moved while its audit row did not is the silent change
    architectural rule 8 exists to prevent, and only the failure path shows
    whether the two statements really share a transaction.
    """
    import scripts.apply_source_rubric as module

    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    source_id = await make_source(name="Rubric Outlet", url_or_handle=handle)
    before = await _score(db_pool, source_id)
    rubric_declaring(handle, ["named_editorial_responsibility"])

    # A NOT NULL column the insert cannot satisfy, so the second statement
    # of the pair fails after the first has run.
    monkeypatch.setattr(
        module,
        "SQL_INSERT_AUDIT_LOG",
        module.SQL_INSERT_AUDIT_LOG.replace("$5, $6", "NULL, $6"),
    )

    with pytest.raises(Exception):
        await apply_rubric(db_pool, apply_changes=True, rebaseline=False)

    assert await _score(db_pool, source_id) == before
    assert await _audit_rows(db_pool, source_id) == []


@pytest.fixture
async def other_org(db_pool):
    """A second organisation, since a Source is a global entity."""
    org_id = "org-rubric-other"
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ($1, 'Rubric Other Org', 'rubric-other', NOW(), NOW(),
                    '{"classification":"OPEN","domain":"osint"}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            org_id,
        )
    yield org_id
    # Reverse dependency order. The org outlives make_source's own cleanup,
    # so its rows have to go before the organisation they point at.
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM credibility_audit_log WHERE org_id = $1", org_id)
        await conn.execute("DELETE FROM org_sources WHERE org_id = $1", org_id)
        await conn.execute("DELETE FROM sources WHERE org_id = $1", org_id)
        await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)


async def test_a_run_can_be_scoped_to_one_organisation(
    db_pool, make_source, other_org, rubric_declaring
):
    """A Source is global, so one handle can exist under two organisations.

    An unscoped run rewrites both, and the audit row lands under the owning
    organisation, which is RLS-protected. An operator working for one
    organisation needs to be able to say which.
    """
    handle = f"https://rubric-{uuid.uuid4().hex[:8]}.example.in/feed"
    mine = await make_source(name="Mine", url_or_handle=handle)
    theirs = await make_source(name="Theirs", url_or_handle=handle, org_id=other_org)
    rubric_declaring(handle, ["named_editorial_responsibility"])

    outcomes = await apply_rubric(
        db_pool, apply_changes=True, rebaseline=False, org_id=other_org
    )

    assert [o.status for o in outcomes] == ["applied"]
    assert await _score(db_pool, theirs) == 60.0
    assert await _audit_rows(db_pool, mine) == []

    async with db_pool.acquire() as conn:
        org_of_row = await conn.fetchval(
            "SELECT org_id FROM credibility_audit_log WHERE source_id = $1", theirs
        )
    assert org_of_row == other_org
