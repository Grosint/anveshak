"""Candidate Topic detection through to an accepted Topic — #26, #27.

Extends the existing analyst pipeline seam rather than creating a new one:
seed content into a real database, run the pipeline functions in sequence,
assert database state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
import pytest
from anveshak.analyst.settings import settings

from tests.conftest import TEST_ORG_ID

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

LABELS_JSON = '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'


def _unit_vector(seed: int, base: np.ndarray | None = None, noise: float = 0.03):
    """L2-normalised embedding, since sentence-transformers outputs unit vectors."""
    rng = np.random.default_rng(seed)
    vector = rng.normal(size=384) if base is None else base + rng.normal(0, noise, 384)
    return vector / np.linalg.norm(vector)


def _vector_literal(vector) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vector) + "]"


@pytest.fixture
async def watch_space(db_pool, ensure_org):
    topic_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (id, name, keywords, languages, signal_threshold,
                                status, org_id, is_watch_space, created_at,
                                updated_at, labels)
            VALUES ($1, 'Integration Test Topic watchspace detect', '{tension}',
                    '{en}', 2, 'active', $2, TRUE, NOW(), NOW(), $3::jsonb)
            """,
            topic_id,
            TEST_ORG_ID,
            LABELS_JSON,
        )
    yield topic_id
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM candidate_topics WHERE watch_space_id = $1", topic_id)
        await conn.execute("DELETE FROM content_items WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM narrative_clusters WHERE topic_id = $1", topic_id)
        await conn.execute("DELETE FROM topics WHERE parent_topic_id = $1", topic_id)
        await conn.execute("DELETE FROM topics WHERE id = $1", topic_id)


async def _make_cluster(
    db_pool,
    watch_space,
    *,
    seed: int,
    item_count: int,
    source_ids: list[str],
    centroid=None,
):
    """A cluster with real content behind it, as clustering would leave it."""
    cluster_id = str(uuid.uuid4())
    base = centroid if centroid is not None else _unit_vector(seed)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO narrative_clusters (
                id, topic_id, label, item_count, independent_source_count,
                embedding_centroid, created_at, updated_at, labels
            )
            VALUES ($1, $2, $3, $4, $5, $6::vector, NOW(), NOW(), $7::jsonb)
            """,
            cluster_id,
            watch_space,
            f"Narrative {seed}",
            item_count,
            len(source_ids),
            _vector_literal(base),
            LABELS_JSON,
        )
        for i in range(item_count):
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, narrative_cluster_id, org_id,
                    raw_text, clean_text, content_hash, captured_at,
                    published_at, labels
                )
                VALUES ($1, $2, $3, $4, $5, $6, $6, $7, NOW(), NOW(), $8::jsonb)
                """,
                str(uuid.uuid4()),
                watch_space,
                source_ids[i % len(source_ids)],
                cluster_id,
                TEST_ORG_ID,
                f"item {seed}-{i}",
                f"{cluster_id}-{i}",
                f'{{"classification":"OPEN","domain":"osint","owner_org":"anveshak",'
                f'"author_handle":"@account{i % 4}"}}',
            )
    return cluster_id, base


class TestPromotionGating:
    async def test_a_qualifying_cluster_surfaces(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics

        sources = [await make_source(name=f"Test Source detect {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=101,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )

        # Persistence: the gate requires two runs, so one pass is not enough.
        await detect_candidate_topics(db_pool)
        async with db_pool.acquire() as conn:
            after_one = await conn.fetchval(
                "SELECT run_count FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
        assert after_one == 1

        await detect_candidate_topics(db_pool)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, run_count, independent_source_count, item_count, "
                "contributing_account_count, novelty_score "
                "FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )

        assert row["status"] == "pending"
        assert row["run_count"] == 2
        assert row["independent_source_count"] == 3
        assert row["contributing_account_count"] > 0

    async def test_a_small_cluster_never_surfaces(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics

        sources = [await make_source(name=f"Test Source small {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=202,
            item_count=settings.promotion_min_item_count - 1,
            source_ids=sources,
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
        # Below the size gate the cluster is not even a candidate to record.
        assert row is None

    async def test_a_single_sourced_cluster_stays_out_of_the_inbox(
        self, db_pool, watch_space, make_source
    ):
        """It is recorded so its persistence accrues, but it does not qualify."""
        from anveshak.analyst.detection import detect_candidate_topics, evaluate_gates

        source = await make_source(name="Test Source single")
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=303,
            item_count=settings.promotion_min_item_count + 2,
            source_ids=[source],
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT independent_source_count, run_count, novelty_score "
                "FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )

        gates = evaluate_gates(
            cluster_id=cluster_id,
            independent_source_count=row["independent_source_count"],
            item_count=settings.promotion_min_item_count + 2,
            novelty_score=row["novelty_score"],
            run_count=row["run_count"],
        )
        assert gates.passed is False
        assert "independent_sources" in gates.failed_gates

    async def test_a_rediscovery_scores_low_novelty(
        self, db_pool, watch_space, make_source, make_topic
    ):
        """A cluster resembling an existing Topic must not surface."""
        from anveshak.analyst.detection import detect_candidate_topics, evaluate_gates

        existing_topic = await make_topic(name="Integration Test Topic already tracked")
        shared = _unit_vector(404)

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO narrative_clusters (
                    id, topic_id, label, item_count, independent_source_count,
                    embedding_centroid, created_at, updated_at, labels
                )
                VALUES ($1, $2, 'Already tracked', 20, 4, $3::vector, NOW(), NOW(),
                        $4::jsonb)
                """,
                str(uuid.uuid4()),
                existing_topic,
                _vector_literal(shared),
                LABELS_JSON,
            )

        sources = [await make_source(name=f"Test Source redis {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=405,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
            centroid=shared,
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT novelty_score, run_count, independent_source_count "
                "FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )

        gates = evaluate_gates(
            cluster_id=cluster_id,
            independent_source_count=row["independent_source_count"],
            item_count=settings.promotion_min_item_count + 5,
            novelty_score=row["novelty_score"],
            run_count=row["run_count"],
        )
        assert gates.passed is False
        assert "novelty" in gates.failed_gates


class TestOnlyQualifyingClustersReachTheInbox:
    """The gates are only real if the inbox reads what they decided.

    Every cluster above the size gate is recorded so its persistence
    history accrues, but the inbox lists 'pending' only. Writing them all as
    'pending' defeated the novelty and persistence gates entirely.
    """

    async def test_a_cluster_below_the_gates_is_recorded_not_pending(
        self, db_pool, watch_space, make_source
    ):
        from anveshak.analyst.detection import detect_candidate_topics

        source = await make_source(name="Test Source recorded")
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=1113,
            item_count=settings.promotion_min_item_count + 2,
            source_ids=[source],  # one source: fails the independent-source gate
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, run_count FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )
        assert row["status"] == "recorded"
        # Recorded, so the persistence history is there if it later qualifies.
        assert row["run_count"] == 2

    async def test_a_recorded_cluster_is_not_in_the_inbox(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import list_candidates

        source = await make_source(name="Test Source recorded inbox")
        await _make_cluster(
            db_pool,
            watch_space,
            seed=1114,
            item_count=settings.promotion_min_item_count + 2,
            source_ids=[source],
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            listed = await list_candidates(conn, org_id=TEST_ORG_ID)

        assert listed == []

    async def test_a_recorded_cluster_is_promoted_when_it_qualifies(
        self, db_pool, watch_space, make_source
    ):
        """A slow-growing narrative arrives at the gates with its history."""
        from anveshak.analyst.detection import detect_candidate_topics

        source = await make_source(name="Test Source grows")
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=1115,
            item_count=settings.promotion_min_item_count + 2,
            source_ids=[source],
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        # More independent sources arrive.
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE narrative_clusters SET independent_source_count = $2 WHERE id = $1",
                cluster_id,
                settings.promotion_min_independent_sources,
            )

        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, run_count FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )
        assert row["status"] == "pending"
        assert row["run_count"] == 3

    async def test_an_accepted_cluster_is_never_demoted(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import set_candidate_status

        sources = [await make_source(name=f"Test Source accepted {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=1116,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            candidate_id = await conn.fetchval(
                "SELECT id FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
            await set_candidate_status(conn, candidate_id, org_id=TEST_ORG_ID, status="accepted")

        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            status = await conn.fetchval(
                "SELECT status FROM candidate_topics WHERE id = $1", candidate_id
            )
        assert status == "accepted"


class TestDecisionsPersist:
    async def test_a_dismissed_candidate_is_not_reproposed(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import set_candidate_status

        sources = [await make_source(name=f"Test Source dismiss {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=506,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            candidate_id = await conn.fetchval(
                "SELECT id FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
            await set_candidate_status(conn, candidate_id, org_id=TEST_ORG_ID, status="dismissed")

        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, run_count FROM candidate_topics WHERE id = $1",
                candidate_id,
            )
        assert row["status"] == "dismissed"
        # Untouched: detection skips a dismissed cluster entirely.
        assert row["run_count"] == 2


class TestAcceptancePopulatesTheTopic:
    async def test_accepting_creates_a_populated_topic(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db import candidates as candidates_db
        from anveshak.api.db.topics import insert_topic

        sources = [await make_source(name=f"Test Source accept {i}") for i in range(3)]
        item_count = settings.promotion_min_item_count + 5
        cluster_id, _ = await _make_cluster(
            db_pool, watch_space, seed=607, item_count=item_count, source_ids=sources
        )

        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        new_topic_id = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            candidate = await conn.fetchrow(
                "SELECT id, cluster_id, watch_space_id FROM candidate_topics WHERE cluster_id = $1",
                cluster_id,
            )
            await insert_topic(
                conn,
                new_topic_id,
                "Promoted narrative",
                ["tension"],
                ["en"],
                30.0,
                3,
                [],
                None,
                None,
                datetime.now(UTC),
                LABELS_JSON,
                org_id=TEST_ORG_ID,
                parent_topic_id=candidate["watch_space_id"],
            )
            content_ids = await candidates_db.cluster_content_ids(
                conn, cluster_id, org_id=TEST_ORG_ID
            )
            await candidates_db.link_content_to_topic(conn, new_topic_id, content_ids)
            await candidates_db.set_candidate_status(
                conn,
                candidate["id"],
                org_id=TEST_ORG_ID,
                status="accepted",
                promoted_topic_id=new_topic_id,
            )

            linked = await conn.fetchval(
                "SELECT COUNT(*) FROM topic_content_items WHERE topic_id = $1",
                new_topic_id,
            )
            lineage = await conn.fetchval(
                "SELECT parent_topic_id FROM topics WHERE id = $1", new_topic_id
            )
            decided = await conn.fetchrow(
                "SELECT status, promoted_topic_id FROM candidate_topics WHERE id = $1",
                candidate["id"],
            )

        assert linked == item_count
        assert lineage == watch_space
        assert decided["status"] == "accepted"
        assert decided["promoted_topic_id"] == new_topic_id

    async def test_accepting_twice_changes_nothing(self, db_pool, watch_space, make_source):
        """The status guard makes the decision idempotent."""
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import set_candidate_status

        sources = [await make_source(name=f"Test Source twice {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=708,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            candidate_id = await conn.fetchval(
                "SELECT id FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
            first = await set_candidate_status(
                conn, candidate_id, org_id=TEST_ORG_ID, status="accepted"
            )
            second = await set_candidate_status(
                conn, candidate_id, org_id=TEST_ORG_ID, status="accepted"
            )

        assert first is not None
        assert second is None


class TestOrgIsolation:
    async def test_a_candidate_is_invisible_across_an_org_boundary(
        self, db_pool, watch_space, make_source
    ):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import list_candidates

        sources = [await make_source(name=f"Test Source iso {i}") for i in range(3)]
        await _make_cluster(
            db_pool,
            watch_space,
            seed=809,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            mine = await list_candidates(conn, org_id=TEST_ORG_ID)
            theirs = await list_candidates(conn, org_id="org-someone-else")

        assert len(mine) >= 1
        assert theirs == []

    async def test_deciding_another_orgs_candidate_does_nothing(
        self, db_pool, watch_space, make_source
    ):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import set_candidate_status

        sources = [await make_source(name=f"Test Source iso2 {i}") for i in range(3)]
        cluster_id, _ = await _make_cluster(
            db_pool,
            watch_space,
            seed=910,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            candidate_id = await conn.fetchval(
                "SELECT id FROM candidate_topics WHERE cluster_id = $1", cluster_id
            )
            result = await set_candidate_status(
                conn, candidate_id, org_id="org-someone-else", status="dismissed"
            )
            still = await conn.fetchval(
                "SELECT status FROM candidate_topics WHERE id = $1", candidate_id
            )

        assert result is None
        assert still == "pending"


class TestOrderingIsByPropagation:
    async def test_the_inbox_orders_by_spread(self, db_pool, watch_space, make_source):
        from anveshak.analyst.detection import detect_candidate_topics
        from anveshak.api.db.candidates import list_candidates

        few = [await make_source(name=f"Test Source order few {i}") for i in range(3)]
        many = [await make_source(name=f"Test Source order many {i}") for i in range(5)]

        await _make_cluster(
            db_pool,
            watch_space,
            seed=1011,
            item_count=settings.promotion_min_item_count + 1,
            source_ids=few,
        )
        await _make_cluster(
            db_pool,
            watch_space,
            seed=1012,
            item_count=settings.promotion_min_item_count + 1,
            source_ids=many,
        )
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            listed = await list_candidates(conn, org_id=TEST_ORG_ID)

        counts = [c["independent_source_count"] for c in listed]
        assert counts == sorted(counts, reverse=True)


class TestAcceptingThroughTheRoute:
    """The accept route itself, over HTTP, against the real schema.

    The test above this one re-implements the route's steps in a different
    order, so it passed while every real accept returned 500: the route wrote
    candidate_topics.promoted_topic_id before the Topic that column references
    existed. A foreign key is checked by PostgreSQL, never by a mock, so the
    seam only shows when the route drives the database. See the wiring note in
    .agents/skills/learned/references/agent-wiring-check-after-green.md.
    """

    @pytest.fixture
    async def client(self, db_pool):
        import httpx
        from anveshak.api.auth.jwt import get_current_user
        from anveshak.api.db.pool import get_db
        from anveshak.api.main import app

        async def _override_get_db():
            async with db_pool.acquire() as conn:
                yield conn

        async def _override_user() -> dict:
            return {"sub": "integration-analyst", "role": "admin", "org_id": TEST_ORG_ID}

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_user
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://accept") as http:
            yield http
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    async def _pending_candidate(self, db_pool, watch_space, make_source, seed: int) -> str:
        from anveshak.analyst.detection import detect_candidate_topics

        sources = [await make_source(name=f"Test Source route {seed} {i}") for i in range(3)]
        await _make_cluster(
            db_pool,
            watch_space,
            seed=seed,
            item_count=settings.promotion_min_item_count + 5,
            source_ids=sources,
        )
        # Two passes: the persistence gate counts detection passes, not clusters.
        await detect_candidate_topics(db_pool)
        await detect_candidate_topics(db_pool)

        async with db_pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT id FROM candidate_topics WHERE watch_space_id = $1 AND status = 'pending'",
                watch_space,
            )

    async def test_accepting_over_http_creates_the_topic(
        self, client, db_pool, watch_space, make_source
    ):
        candidate_id = await self._pending_candidate(db_pool, watch_space, make_source, 1201)

        response = await client.post(
            f"/api/v1/candidate-topics/{candidate_id}/accept",
            json={"name": "Promoted over HTTP", "keywords": ["tension"]},
        )

        assert response.status_code == 201, response.text
        body = response.json()

        async with db_pool.acquire() as conn:
            decided = await conn.fetchrow(
                "SELECT status, promoted_topic_id FROM candidate_topics WHERE id = $1",
                candidate_id,
            )
            topic = await conn.fetchrow(
                "SELECT name, parent_topic_id FROM topics WHERE id = $1", body["topic_id"]
            )
            linked = await conn.fetchval(
                "SELECT COUNT(*) FROM topic_content_items WHERE topic_id = $1", body["topic_id"]
            )

        assert decided["status"] == "accepted"
        # The column the foreign key guards: the claim and the Topic agree.
        assert decided["promoted_topic_id"] == body["topic_id"]
        assert topic["name"] == "Promoted over HTTP"
        assert topic["parent_topic_id"] == watch_space
        assert linked == body["content_items_linked"] > 0

    async def test_accepting_twice_over_http_creates_one_topic(
        self, client, db_pool, watch_space, make_source
    ):
        candidate_id = await self._pending_candidate(db_pool, watch_space, make_source, 1202)

        first = await client.post(f"/api/v1/candidate-topics/{candidate_id}/accept", json={})
        second = await client.post(f"/api/v1/candidate-topics/{candidate_id}/accept", json={})

        assert first.status_code == 201, first.text
        assert second.status_code == 409, second.text

        async with db_pool.acquire() as conn:
            topics = await conn.fetchval(
                "SELECT COUNT(*) FROM topics WHERE parent_topic_id = $1", watch_space
            )
        assert topics == 1
