"""Detection output carries the reference time, not the wall clock — issue #46.

pytest.mark.integration — requires running Docker Compose services:
  make up

The unit tests pin the parameter. These pin the row: content captured on the
days a historic narrative ran is clustered and signalled at a reference time
from that period, and the rows land dated then rather than today.

Run with:
  uv run --package anveshak-tests pytest \
      tests/integration/test_virtual_clock_pipeline.py -v -m integration
"""

from __future__ import annotations

import hashlib
import math
import random
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from anveshak.analyst.clustering import run_clustering
from anveshak.analyst.signal_engine import check_signals
from anveshak.clock import ClockOverrideRefusedError

# The Cockroach Janta Party arc in #39. Long enough ago that the 30 day
# clustering window excludes all of it when measured from the wall clock.
REPLAY_TIME = datetime(2026, 5, 20, 9, 30, tzinfo=UTC)

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


@pytest.fixture(autouse=True)
def clock_on(monkeypatch):
    """A Replay run permits the override. A deployment does not: the flag has
    to be on and the environment has to be on the allowlist."""
    monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")


@pytest.fixture
async def historic_topic(make_topic):
    return await make_topic(
        name="Virtual Clock Test Topic",
        keywords=["march", "protest"],
        signal_threshold=2,
    )


@pytest.fixture
async def historic_sources(make_source):
    ids = {}
    for platform, handle in {
        "web": f"https://outlet-{uuid.uuid4().hex[:8]}.example",
        "telegram": f"t.me/channel_{uuid.uuid4().hex[:8]}",
        "reddit": f"r/sub_{uuid.uuid4().hex[:8]}",
    }.items():
        ids[platform] = await make_source(
            name=f"Historic source {platform} {uuid.uuid4().hex[:6]}",
            url_or_handle=handle,
            platform=platform,
            credibility_score=70.0,
        )
    return ids


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return vec if norm == 0 else [x / norm for x in vec]


def _base_vector(seed: int, dim: int = 384) -> list[float]:
    rng = random.Random(seed)
    return _l2_normalize([rng.gauss(0, 1) for _ in range(dim)])


def _near(base: list[float], rng: random.Random, noise: float = 0.03) -> list[float]:
    return _l2_normalize([x + rng.uniform(-noise, noise) for x in base])


async def _insert_item(
    pool: asyncpg.Pool,
    topic_id: str,
    source_id: str,
    text: str,
    embedding: list[float],
    captured_at: datetime,
) -> str:
    item_id = str(uuid.uuid4())
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO content_items (
                id, topic_id, source_id, raw_text, clean_text, language,
                content_hash, url, captured_at, credibility_score_at_capture,
                embedding, created_at, updated_at, labels, org_id
            ) VALUES ($1,$2,$3,$4,$5,'en',$6,$7,$8,70.0,$9::vector,$8,$8,$10,$11)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            item_id,
            topic_id,
            source_id,
            text,
            text,
            hashlib.sha256(text.lower().encode()).hexdigest(),
            f"https://example.com/{uuid.uuid4()}",
            captured_at,
            embedding_str,
            LABELS_JSON,
            "org-integration-test",
        )
    return item_id


async def _seed_narrative(pool, topic_id, sources, *, captured_at, seed) -> None:
    base = _base_vector(seed)
    rng = random.Random(seed)
    for platform, source_id in sources.items():
        for i in range(2):
            await _insert_item(
                pool,
                topic_id,
                source_id,
                f"Call to assemble reported by {platform} {i} {uuid.uuid4()}",
                _near(base, rng),
                captured_at,
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clusters_form_from_historic_content_and_carry_its_date(
    db_pool, historic_topic, historic_sources
):
    """The window is measured back from the reference time, so content from
    months ago is inside it, and the cluster is dated then."""
    await _seed_narrative(
        db_pool,
        historic_topic,
        historic_sources,
        captured_at=REPLAY_TIME - timedelta(days=2),
        seed=4601,
    )

    cluster_ids = await run_clustering(historic_topic, db_pool, reference_time=REPLAY_TIME)

    assert cluster_ids, "historic content must cluster when the clock is the reference time"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT created_at, updated_at FROM narrative_clusters WHERE id = ANY($1::text[])",
            cluster_ids,
        )
    assert rows
    for row in rows:
        assert row["created_at"] == REPLAY_TIME
        assert row["updated_at"] == REPLAY_TIME


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_same_content_is_outside_the_window_at_the_wall_clock(
    db_pool, historic_topic, historic_sources
):
    """The other half of the same fact: without the reference time, the
    30 day window excludes every item and nothing forms."""
    await _seed_narrative(
        db_pool,
        historic_topic,
        historic_sources,
        captured_at=REPLAY_TIME - timedelta(days=2),
        seed=4602,
    )

    assert await run_clustering(historic_topic, db_pool) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_signal_carries_the_date_its_evidence_existed(
    db_pool, historic_topic, historic_sources
):
    """Story 1: navigating to a past date shows what the platform would have
    said then."""
    await _seed_narrative(
        db_pool,
        historic_topic,
        historic_sources,
        captured_at=REPLAY_TIME - timedelta(days=1),
        seed=4603,
    )
    await run_clustering(historic_topic, db_pool, reference_time=REPLAY_TIME)

    fired = await check_signals(db_pool, _noop_broadcast, reference_time=REPLAY_TIME)

    assert fired >= 1
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT created_at, updated_at FROM signals WHERE topic_id = $1",
            historic_topic,
        )
    assert rows
    for row in rows:
        assert row["created_at"] == REPLAY_TIME
        assert row["updated_at"] == REPLAY_TIME


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_override_is_refused_when_the_flag_is_off(db_pool, historic_topic, monkeypatch):
    """The guard is reached through the same path a Replay uses."""
    monkeypatch.setenv("VIRTUAL_CLOCK_ENABLED", "false")

    with pytest.raises(ClockOverrideRefusedError):
        await run_clustering(historic_topic, db_pool, reference_time=REPLAY_TIME)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_detection_still_dates_rows_now(db_pool, historic_topic, historic_sources):
    """Story 6: the default path is unchanged."""
    now = datetime.now(UTC)
    await _seed_narrative(
        db_pool,
        historic_topic,
        historic_sources,
        captured_at=now - timedelta(hours=2),
        seed=4604,
    )

    cluster_ids = await run_clustering(historic_topic, db_pool)

    assert cluster_ids
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT created_at FROM narrative_clusters WHERE id = ANY($1::text[])",
            cluster_ids,
        )
    for row in rows:
        assert now <= row["created_at"] <= datetime.now(UTC)


async def _noop_broadcast(payload: dict) -> None:
    """The WebSocket layer is not what these tests are about."""
    return None
