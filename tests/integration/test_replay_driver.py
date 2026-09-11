"""Replay at the database seam - issue #47.

The unit tests pin the staging arithmetic. These pin the rows a Replay leaves
behind, which is where the claim lives: a Signal carries the date its evidence
existed rather than the day the Replay ran, a Candidate Topic appears only once
it has survived the persistence gate, and a reset followed by an identical
re-run produces the same counts.

Embedding is the one step held out. It belongs to the analyst worker's models,
and injecting deterministic vectors here makes clustering reproducible, which
is what the third assertion measures.

pytest.mark.integration - requires running Docker Compose:
  make up

Run with:
  uv run pytest tests/integration/test_replay_driver.py -v -m integration
"""

from __future__ import annotations

import json
import math
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from anveshak.clock import ClockSettings

from scripts.import_corpus import load_corpus
from scripts.replay_corpus import ReplayRefusedError, plan_stages, reset_org_state, run_replay

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# One week apart, so the corpus stages into two weekly stages, and far enough
# back that a wall-clock window would exclude all of it.
WEEK_ONE = datetime(2026, 5, 18, 9, 30, tzinfo=UTC)
WEEK_TWO = WEEK_ONE + timedelta(days=8)

REPLAY_ORG = "org-replay-test"
LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"org-replay-test"}'

# Ten items in the first week: the promotion gate needs promotion_min_item_count
# in one cluster, and three sources for the independent source gate.
WEEK_ONE_ITEMS = 10
WEEK_TWO_ITEMS = 4


@pytest.fixture(autouse=True)
def clock_on(monkeypatch):
    """A Replay host. Both layers of the guard have to say yes."""
    monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")


@pytest.fixture
def token() -> str:
    """Unique per run, so content hashes and Source handles cannot pre-exist."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def replay_org(db_pool):
    """A dedicated organisation, because a Replay resets everything one owns."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
            VALUES ($1, 'Replay Test Org', 'replay-test', NOW(), NOW(), $2)
            ON CONFLICT (id) DO NOTHING
            """,
            REPLAY_ORG,
            LABELS_JSON,
        )
    return REPLAY_ORG


@pytest.fixture
async def watch_space(db_pool, replay_org):
    """An active Watch Space: Candidate Topics are only detected inside one."""
    topic_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                is_watch_space, org_id, created_at, updated_at, labels)
            VALUES ($1, 'Replay Watch Space', $2, 2, 'active', TRUE, $3, NOW(), NOW(), $4)
            """,
            topic_id,
            ["protest", "march"],
            replay_org,
            LABELS_JSON,
        )
    yield topic_id

    async with db_pool.acquire() as conn:
        # Explicit settings: the autouse clock fixture's environment is already
        # unwound by the time a fixture finalizer runs, and the teardown must
        # not depend on the guard still passing.
        await reset_org_state(
            db_pool,
            replay_org,
            clock_settings=ClockSettings(virtual_clock_enabled=True, environment="test"),
        )
        await conn.execute("DELETE FROM topic_sources WHERE topic_id = $1", topic_id)
        await conn.execute(
            "DELETE FROM org_sources WHERE org_id = $1",
            replay_org,
        )
        await conn.execute(
            "DELETE FROM sources WHERE org_id = $1",
            replay_org,
        )
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)
        await conn.execute("DELETE FROM organizations WHERE id = $1", replay_org)


@pytest.fixture
def corpus(tmp_path, token) -> Path:
    """Two weeks of one narrative, across three outlets."""
    outlets = [
        (f"https://outlet-{letter}-{token}.example/feed", f"Outlet {letter.upper()}", letter)
        for letter in ("a", "b", "c")
    ]
    lines = []
    for index in range(WEEK_ONE_ITEMS + WEEK_TWO_ITEMS):
        first_week = index < WEEK_ONE_ITEMS
        published = (WEEK_ONE if first_week else WEEK_TWO) + timedelta(hours=index)
        handle, name, letter = outlets[index % len(outlets)]
        lines.append(
            {
                "url": f"https://outlet-{letter}-{token}.example/article-{index}",
                "text": (
                    f"Demonstrators assembled again outside the ministry today. "
                    f"Organisers called for a march on the capital. Item {index} {token}."
                ),
                "language": "en",
                "published_at": published.isoformat(),
                "published_at_signal": "jsonld_date_published",
                "source": {
                    "handle": handle,
                    "name": name,
                    "platform": "web",
                    # Above credibility_high_threshold, so cross-verification
                    # boosts these Sources and the reset's restore has
                    # something to reverse.
                    "credibility_score": 70.0,
                },
            }
        )
    path = tmp_path / "replay_corpus.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Embedding, held out
# ---------------------------------------------------------------------------


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return vector if norm == 0 else [x / norm for x in vector]


def _base_vector(dim: int = 384) -> list[float]:
    rng = random.Random(4747)
    return _l2_normalize([rng.gauss(0, 1) for _ in range(dim)])


def _make_embed(base: list[float]):
    """Embed one stage's items as one tight narrative, deterministically.

    Noise of 0.03 is the calibration for a realistic cluster, and a seeded RNG
    per item id keeps a re-run of the same corpus producing the same vectors,
    which is what makes the reproducibility assertion mean anything.
    """

    async def embed(pool, topic_id: str, captured_at: datetime) -> int:
        rows = await pool.fetch(
            "SELECT id FROM content_items "
            "WHERE topic_id = $1 AND captured_at = $2 AND embedding IS NULL "
            "ORDER BY id",
            topic_id,
            captured_at,
        )
        for row in rows:
            rng = random.Random(row["id"])
            vector = _l2_normalize([x + rng.uniform(-0.03, 0.03) for x in base])
            await pool.execute(
                "UPDATE content_items SET embedding = $2::vector WHERE id = $1",
                row["id"],
                "[" + ",".join(f"{x:.8f}" for x in vector) + "]",
            )
        return 0

    return embed


async def _counts(pool, org_id: str, topic_id: str) -> dict[str, int]:
    async with pool.acquire() as conn:
        return {
            "content": await conn.fetchval(
                "SELECT COUNT(*) FROM content_items WHERE org_id = $1", org_id
            ),
            "clusters": await conn.fetchval(
                "SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = $1", topic_id
            ),
            "signals": await conn.fetchval(
                "SELECT COUNT(*) FROM signals WHERE topic_id = $1", topic_id
            ),
            "candidates": await conn.fetchval(
                "SELECT COUNT(*) FROM candidate_topics WHERE org_id = $1", org_id
            ),
            "pending_candidates": await conn.fetchval(
                "SELECT COUNT(*) FROM candidate_topics WHERE org_id = $1 AND status = 'pending'",
                org_id,
            ),
        }


async def _replay(
    pool,
    corpus: Path,
    topic_id: str,
    org_id: str,
    *,
    now: datetime | None = None,
    allow_shared_host: bool = True,
):
    return await run_replay(
        load_corpus(corpus),
        topic_id=topic_id,
        org_id=org_id,
        pool=pool,
        # Nothing here depends on a worker running: the jobs a stage enqueues
        # are labelling and cross-verification, both enrichment.
        arq_pool=AsyncMock(),
        embed=_make_embed(_base_vector()),
        now=now or datetime.now(UTC),
        # The test database is shared with every other integration test, so it
        # always has another organisation's Topics on it. A dedicated Replay
        # host does not, which is what the refusal test below covers.
        allow_shared_host=allow_shared_host,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStagedReplay:
    async def test_every_stage_imports_only_its_own_week(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        summary = await _replay(db_pool, corpus, watch_space, replay_org)

        assert [result.imported for result in summary.stages] == [
            WEEK_ONE_ITEMS,
            WEEK_TWO_ITEMS,
        ]
        # Capture Time is the stage's moment, which is what gives the hostility
        # shift Signal a prior window to measure against.
        async with db_pool.acquire() as conn:
            captured = await conn.fetch(
                "SELECT DISTINCT captured_at FROM content_items "
                "WHERE org_id = $1 ORDER BY captured_at",
                replay_org,
            )
        assert [row["captured_at"] for row in captured] == [
            stage.stage.reference_time for stage in summary.stages
        ]

    async def test_publication_time_survives_the_staging(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        await _replay(db_pool, corpus, watch_space, replay_org)
        async with db_pool.acquire() as conn:
            earliest = await conn.fetchval(
                "SELECT MIN(published_at) FROM content_items WHERE org_id = $1",
                replay_org,
            )
        assert earliest == WEEK_ONE

    async def test_signals_carry_their_stage_date_not_the_wall_clock(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        summary = await _replay(db_pool, corpus, watch_space, replay_org)
        stage_times = {result.stage.reference_time for result in summary.stages}

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT signal_type, created_at FROM signals WHERE topic_id = $1",
                watch_space,
            )

        assert rows, "no Signal fired across the Replay"
        today = datetime.now(UTC).date()
        for row in rows:
            assert row["created_at"] in stage_times
            assert row["created_at"].date() != today

    async def test_clusters_are_stamped_at_the_stage_clock(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        summary = await _replay(db_pool, corpus, watch_space, replay_org)
        last_stage = summary.stages[-1].stage.reference_time

        async with db_pool.acquire() as conn:
            created = await conn.fetchval(
                "SELECT MIN(created_at) FROM narrative_clusters WHERE topic_id = $1",
                watch_space,
            )
        assert created is not None
        assert created <= last_stage

    async def test_a_candidate_topic_waits_for_the_persistence_gate(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        # Stage one records the cluster so its history accrues; only stage two
        # has seen it across two runs, which is what promotion is supposed to
        # mean. A bulk import gives one run and cannot express this.
        items = load_corpus(corpus)
        stages = plan_stages(items, now=datetime.now(UTC))
        assert len(stages) == 2

        summary = await _replay(db_pool, corpus, watch_space, replay_org)
        assert summary.stages[0].candidates == 0
        assert summary.stages[1].candidates >= 1

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, run_count FROM candidate_topics WHERE org_id = $1 "
                "ORDER BY run_count DESC LIMIT 1",
                replay_org,
            )
        assert row["status"] == "pending"
        assert row["run_count"] >= 2


class TestResetAndRerun:
    async def test_a_rerun_reproduces_the_first_run(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        now = datetime.now(UTC)
        await _replay(db_pool, corpus, watch_space, replay_org, now=now)
        first = await _counts(db_pool, replay_org, watch_space)

        await _replay(db_pool, corpus, watch_space, replay_org, now=now)
        second = await _counts(db_pool, replay_org, watch_space)

        assert second == first
        assert first["content"] == WEEK_ONE_ITEMS + WEEK_TWO_ITEMS

    async def test_reset_removes_the_previous_run(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        await _replay(db_pool, corpus, watch_space, replay_org)
        assert (await _counts(db_pool, replay_org, watch_space))["content"] > 0

        await reset_org_state(db_pool, replay_org)
        after = await _counts(db_pool, replay_org, watch_space)
        assert after == {
            "content": 0,
            "clusters": 0,
            "signals": 0,
            "candidates": 0,
            "pending_candidates": 0,
        }

    async def test_reset_leaves_the_watch_space_and_its_sources(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        # A Watch Space is configuration the Replay imports into, and a Source
        # is global to every organisation. Deleting either would make the
        # second run a different run.
        await _replay(db_pool, corpus, watch_space, replay_org)
        await reset_org_state(db_pool, replay_org)

        async with db_pool.acquire() as conn:
            assert await conn.fetchval("SELECT COUNT(*) FROM topics WHERE id = $1", watch_space)
            assert await conn.fetchval("SELECT COUNT(*) FROM sources WHERE org_id = $1", replay_org)


class TestCredibility:
    async def test_the_reset_restores_what_cross_verification_moved(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        # Cross-verification boosts a high-credibility Source confirmed by a
        # multi-platform cluster, and audit-logs it (rule 8). A re-run that
        # started from the boosted score would produce a different arc from the
        # same corpus, so the reset puts the score back and deletes the trail
        # it is reversing in the same transaction.
        await _replay(db_pool, corpus, watch_space, replay_org)

        async with db_pool.acquire() as conn:
            audited = await conn.fetch(
                "SELECT source_id, old_score FROM credibility_audit_log WHERE org_id = $1",
                replay_org,
            )
            boosted = await conn.fetchval(
                "SELECT MAX(credibility_score) FROM sources WHERE org_id = $1", replay_org
            )
        assert audited, "cross-verification wrote no credibility change to reverse"
        assert boosted > 70.0

        await reset_org_state(db_pool, replay_org)

        async with db_pool.acquire() as conn:
            remaining = await conn.fetchval(
                "SELECT COUNT(*) FROM credibility_audit_log WHERE org_id = $1", replay_org
            )
            scores = await conn.fetch(
                "SELECT credibility_score FROM sources WHERE org_id = $1", replay_org
            )
        assert remaining == 0
        assert [row["credibility_score"] for row in scores] == [70.0] * len(scores)


class TestRefusals:
    async def test_the_driver_refuses_where_the_flag_is_off(
        self, db_pool, corpus, watch_space, replay_org, monkeypatch
    ) -> None:
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "false")
        with pytest.raises(ReplayRefusedError):
            await _replay(db_pool, corpus, watch_space, replay_org)

        # Refused before the reset, so a Replay that cannot run destroys
        # nothing on the way to finding that out.
        assert (await _counts(db_pool, replay_org, watch_space))["content"] == 0

    async def test_reset_refuses_where_the_flag_is_off(
        self, db_pool, replay_org, monkeypatch
    ) -> None:
        # The teardown is importable, so it carries the guard itself rather
        # than trusting the one caller that has it today.
        monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "false")
        with pytest.raises(ReplayRefusedError):
            await reset_org_state(db_pool, replay_org)

    async def test_the_driver_refuses_a_shared_host_by_default(
        self, db_pool, corpus, watch_space, replay_org
    ) -> None:
        # Detection is deployment-wide, so another organisation's Topics would
        # collect Signals dated months ago that this organisation's reset does
        # not remove.
        with pytest.raises(ReplayRefusedError) as exc:
            await _replay(db_pool, corpus, watch_space, replay_org, allow_shared_host=False)
        assert "deployment-wide" in str(exc.value)

    async def test_the_driver_refuses_a_topic_the_organisation_does_not_own(
        self, db_pool, corpus, watch_space
    ) -> None:
        from scripts.import_corpus import TopicAccessError

        with pytest.raises(TopicAccessError):
            await _replay(db_pool, corpus, watch_space, "org-integration-test")
