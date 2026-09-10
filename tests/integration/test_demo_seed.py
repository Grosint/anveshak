"""The demonstration seed, checked at the API seam - issue #40.

Two claims are load-bearing for a demonstration:

  - The Sentiment Timeline renders. It plots published_at, so seeded content
    without a Publication Time lands in the excluded footnote and the chart is
    empty.
  - Every Signal on screen was fired by the Signal engine. The seed therefore
    inserts none, and one appears only after detection has run over the seeded
    corpus.

Teardown is snapshot-based rather than scoped by org. check_signals runs across
every active Topic, so rows this test causes are not confined to the seeded
org, and deleting by org_id would both miss those and delete rows the test
found rather than made.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from anveshak.analyst.clustering import run_clustering
from anveshak.analyst.signal_engine import check_signals

from tests.conftest import POSTGRES_URL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED = REPO_ROOT / "scripts" / "seed_demo.sql"

SEED_ORG = "org-anshul"
TOPIC_UAV = "b0000000-0000-0000-0000-000000000002"

# The seed's own fixed IDs. Deleting these rather than everything owned by the
# org keeps the blast radius to rows this seed is the author of.
# Accounts moved out of the SQL seed in #41: scripts/seed_demo_org.py owns
# them now, and their ids are derived from the usernames in the environment.
# Nothing here creates a user, so nothing here deletes one.
SEED_TOPIC_IDS = (
    "b0000000-0000-0000-0000-000000000001",
    TOPIC_UAV,
    "b0000000-0000-0000-0000-000000000003",
)
SEED_SOURCE_IDS = tuple(f"c0000000-0000-0000-0000-00000000000{n}" for n in range(1, 6))
SEED_CONTENT_IDS = tuple(f"e0000000-0000-0000-0000-00000000000{n}" for n in range(1, 6))
SEED_AUDIT_IDS = ("d0000000-0000-0000-0000-000000000001",)
SEED_JOB_IDS = ("f0000000-0000-0000-0000-000000000001",)
SEED_REPORT_IDS = ("22000000-0000-0000-0000-000000000001",)


def _l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def _base_vector(seed: int, dim: int = 384) -> list[float]:
    rng = random.Random(seed)
    return _l2_normalise([rng.gauss(0, 1) for _ in range(dim)])


def _near(base: list[float], rng: random.Random, noise: float = 0.03) -> list[float]:
    """A realistic same-narrative neighbour: 0.03 is the calibrated setting."""
    return _l2_normalise([x + rng.uniform(-noise, noise) for x in base])


async def _ids(conn: Any, table: str) -> set[str]:
    return {r["id"] for r in await conn.fetch(f"SELECT id FROM {table}")}


@pytest.fixture
async def demo_seed(db_pool: asyncpg.Pool):
    """Load scripts/seed_demo.sql, then remove exactly what appeared."""
    # Defence in depth behind the session guard in conftest: this fixture
    # deletes rows the primary demo database also owns.
    assert "_test" in POSTGRES_URL, (
        f"refusing to seed and delete against a non-test database: {POSTGRES_URL}"
    )

    sql = SEED.read_text(encoding="utf-8")
    async with db_pool.acquire() as conn:
        clusters_before = await _ids(conn, "narrative_clusters")
        signals_before = await _ids(conn, "signals")
        await conn.execute(sql)

    yield db_pool

    async with db_pool.acquire() as conn:
        # Detection output first: it is the only part whose IDs are not fixed.
        new_signals = await _ids(conn, "signals") - signals_before
        if new_signals:
            await conn.execute("DELETE FROM signals WHERE id = ANY($1::text[])", list(new_signals))
        new_clusters = await _ids(conn, "narrative_clusters") - clusters_before
        if new_clusters:
            await conn.execute(
                "UPDATE content_items SET narrative_cluster_id = NULL "
                "WHERE narrative_cluster_id = ANY($1::text[])",
                list(new_clusters),
            )
            await conn.execute(
                "DELETE FROM narrative_clusters WHERE id = ANY($1::text[])", list(new_clusters)
            )

        # Then the seed's own rows, child-first.
        for table, ids in (
            ("analysis_jobs", SEED_JOB_IDS),
            ("reports", SEED_REPORT_IDS),
            ("content_items", SEED_CONTENT_IDS),
            ("credibility_audit_log", SEED_AUDIT_IDS),
        ):
            await conn.execute(f"DELETE FROM {table} WHERE id = ANY($1::text[])", list(ids))
        await conn.execute(
            "DELETE FROM topic_content_items WHERE topic_id = ANY($1::text[])", list(SEED_TOPIC_IDS)
        )
        await conn.execute(
            "DELETE FROM org_sources WHERE org_id = $1 AND source_id = ANY($2::text[])",
            SEED_ORG,
            list(SEED_SOURCE_IDS),
        )
        await conn.execute("DELETE FROM sources WHERE id = ANY($1::text[])", list(SEED_SOURCE_IDS))
        await conn.execute("DELETE FROM topics WHERE id = ANY($1::text[])", list(SEED_TOPIC_IDS))
        await conn.execute("DELETE FROM organizations WHERE id = $1", SEED_ORG)


async def _seeded_content(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, topic_id, source_id, captured_at, published_at "
            "FROM content_items WHERE id = ANY($1::text[]) ORDER BY captured_at",
            list(SEED_CONTENT_IDS),
        )
    return [dict(r) for r in rows]


class TestPublicationTime:
    async def test_every_seeded_item_has_a_publication_time(self, demo_seed: asyncpg.Pool) -> None:
        items = await _seeded_content(demo_seed)
        assert items, "seed produced no content items"
        missing = [i["id"] for i in items if i["published_at"] is None]
        assert not missing, f"{len(missing)} seeded items have no Publication Time: {missing}"

    async def test_publication_time_is_not_the_capture_time(self, demo_seed: asyncpg.Pool) -> None:
        # The two are different measurements. Seeding them equal would let a
        # bug that confuses them pass unnoticed.
        items = await _seeded_content(demo_seed)
        same = [i["id"] for i in items if i["published_at"] == i["captured_at"]]
        assert not same, f"Publication Time equals Capture Time on {same}"

    async def test_publication_time_precedes_capture(self, demo_seed: asyncpg.Pool) -> None:
        items = await _seeded_content(demo_seed)
        late = [
            i["id"]
            for i in items
            if i["published_at"] is not None and i["published_at"] > i["captured_at"]
        ]
        assert not late, f"items captured before they were published: {late}"


class TestSentimentTimeline:
    async def test_timeline_renders_with_nothing_excluded(self, demo_seed: asyncpg.Pool) -> None:
        from anveshak.api.db.timeline import get_timeline

        async with demo_seed.acquire() as conn:
            result = await get_timeline(conn, TOPIC_UAV, org_id=SEED_ORG, days=90)

        assert result["buckets"], "Sentiment Timeline is empty for a seeded topic"
        assert result["excluded_no_publication_time"] == 0, (
            "seeded items fell into the excluded footnote instead of the chart"
        )

    async def test_timeline_counts_every_seeded_item_of_the_topic(
        self, demo_seed: asyncpg.Pool
    ) -> None:
        from anveshak.api.db.timeline import get_timeline

        async with demo_seed.acquire() as conn:
            result = await get_timeline(conn, TOPIC_UAV, org_id=SEED_ORG, days=90)
        plotted = sum(int(b["total"]) for b in result["buckets"])

        items = await _seeded_content(demo_seed)
        expected = len([i for i in items if i["topic_id"] == TOPIC_UAV])
        assert plotted == expected, f"{expected} seeded items, {plotted} plotted"


class TestSignalsAreDetectedNotSeeded:
    async def test_no_signals_immediately_after_seeding(self, demo_seed: asyncpg.Pool) -> None:
        async with demo_seed.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM signals WHERE topic_id = ANY($1::text[])",
                list(SEED_TOPIC_IDS),
            )
        assert count == 0, f"{count} Signal(s) exist before detection ran - these are fabricated"

    async def test_no_narrative_clusters_immediately_after_seeding(
        self, demo_seed: asyncpg.Pool
    ) -> None:
        async with demo_seed.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM narrative_clusters WHERE topic_id = ANY($1::text[])",
                list(SEED_TOPIC_IDS),
            )
        assert count == 0, f"{count} Narrative Cluster(s) exist before clustering ran"

    async def test_seeded_corpus_corroborates_a_narrative(self, demo_seed: asyncpg.Pool) -> None:
        """The UAV topic carries the same story from independent sources.

        Without this the Signal engine has nothing to fire on, and the demo
        can only show detection by faking it.
        """
        items = await _seeded_content(demo_seed)
        uav = [i for i in items if i["topic_id"] == TOPIC_UAV]
        async with demo_seed.acquire() as conn:
            threshold = await conn.fetchval(
                "SELECT signal_threshold FROM topics WHERE id = $1", TOPIC_UAV
            )
        assert len({i["source_id"] for i in uav}) >= threshold, (
            f"UAV topic needs >= {threshold} independent sources to breach its own threshold"
        )

    async def test_signal_fires_once_the_engine_runs(self, demo_seed: asyncpg.Pool) -> None:
        """Detection over the seeded corpus produces the Signal the demo shows."""
        items = await _seeded_content(demo_seed)
        uav = [i for i in items if i["topic_id"] == TOPIC_UAV]

        # Stand in for analyse_content: the seeded rows are unembedded, and the
        # embedding model is not a dependency of this seam.
        base = _base_vector(seed=40)
        rng = random.Random(40)
        async with demo_seed.acquire() as conn:
            for item in uav:
                vector = "[" + ",".join(f"{x:.8f}" for x in _near(base, rng)) + "]"
                await conn.execute(
                    "UPDATE content_items SET embedding = $1::vector WHERE id = $2",
                    vector,
                    item["id"],
                )

        cluster_ids = await run_clustering(TOPIC_UAV, demo_seed)
        assert cluster_ids, "clustering produced no cluster from corroborating items"

        pushed: list[dict[str, Any]] = []

        async def broadcast(payload: dict[str, Any]) -> None:
            pushed.append(payload)

        await check_signals(demo_seed, broadcast)

        async with demo_seed.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM signals WHERE topic_id = $1", TOPIC_UAV
            )
        assert count >= 1, "Signal engine fired nothing on a corroborated seeded narrative"
