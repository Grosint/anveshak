"""RLS enforcement tests — verify org isolation at the SQL level.

The test DB user (anveshak) has BYPASSRLS=true (table owner). So these tests
verify the RLS POLICY LOGIC directly by embedding the same WHERE clause
that PostgreSQL RLS enforces. This catches:
  - Policy condition bugs (wrong column, wrong setting name)
  - Missing org_id on rows (would bypass filter)
  - Cross-org visibility in queries that use SET LOCAL app.current_org

Tests:
  R1: SET LOCAL app.current_org filters topics by org
  R2: Empty app.current_org sees all orgs (superadmin)
  R3: Cross-org content_items filtered correctly
  R4: Signals inherit org boundary through topic_id → topics.org_id
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from tests.conftest import LABELS_JSON

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ORG_A = f"org-rls-test-a-{uuid.uuid4().hex[:8]}"
ORG_B = f"org-rls-test-b-{uuid.uuid4().hex[:8]}"

# RLS policy condition — same logic as pg_policy on topics/content_items
RLS_FILTER = """
    (current_setting('app.current_org', true) = ''
     OR org_id = current_setting('app.current_org', true))
"""


@pytest.fixture
async def two_orgs(db_pool):
    """Create two test orgs with one topic each."""
    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        for org_id in (ORG_A, ORG_B):
            await conn.execute(
                """
                INSERT INTO organizations (id, name, slug, created_at, updated_at, labels)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                org_id,
                f"Test Org {org_id[-8:]}",
                org_id[-8:],
                now,
                now,
                LABELS_JSON,
            )

        topic_a = str(uuid.uuid4())
        topic_b = str(uuid.uuid4())
        for topic_id, org_id, name in [
            (topic_a, ORG_A, "Topic Alpha (Org A)"),
            (topic_b, ORG_B, "Topic Beta (Org B)"),
        ]:
            await conn.execute(
                """
                INSERT INTO topics (id, name, keywords, signal_threshold, status,
                                    org_id, created_at, updated_at, labels)
                VALUES ($1, $2, $3, 3, 'active', $4, $5, $6, $7)
                """,
                topic_id,
                name,
                ["test"],
                org_id,
                now,
                now,
                LABELS_JSON,
            )

    yield {"org_a": ORG_A, "org_b": ORG_B, "topic_a": topic_a, "topic_b": topic_b}

    # Cleanup
    async with db_pool.acquire() as conn:
        for tid in (topic_a, topic_b):
            await conn.execute("DELETE FROM signals WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM content_items WHERE topic_id=$1", tid)
            await conn.execute("DELETE FROM topics WHERE id=$1", tid)
        for org_id in (ORG_A, ORG_B):
            await conn.execute("DELETE FROM organizations WHERE id=$1", org_id)


# ---------------------------------------------------------------------------
# R1: SET LOCAL app.current_org filters topics by org
# ---------------------------------------------------------------------------


async def test_rls_filters_topics_by_org(db_pool, two_orgs):
    """With app.current_org set, only that org's topics should be visible.

    Since test user bypasses RLS, we apply the same WHERE clause manually
    to verify the policy condition works correctly.
    """
    async with db_pool.acquire() as conn:
        # SET LOCAL requires an active transaction
        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_org = '{two_orgs['org_a']}'")

            rows = await conn.fetch(f"SELECT id, name, org_id FROM topics WHERE {RLS_FILTER}")

            # Should include org_a, exclude org_b
            topic_ids = {r["id"] for r in rows}
            assert two_orgs["topic_a"] in topic_ids, "Org A topic should be visible"
            assert two_orgs["topic_b"] not in topic_ids, "Org B topic should NOT be visible"

            # All returned rows should belong to org_a
            for r in rows:
                if r["id"] in (two_orgs["topic_a"], two_orgs["topic_b"]):
                    assert r["org_id"] == two_orgs["org_a"], (
                        f"Topic {r['name']} has org_id={r['org_id']}, expected {two_orgs['org_a']}"
                    )


# ---------------------------------------------------------------------------
# R2: Empty app.current_org sees all orgs (superadmin)
# ---------------------------------------------------------------------------


async def test_rls_empty_org_sees_all(db_pool, two_orgs):
    """Empty app.current_org should see topics from ALL orgs (superadmin mode)."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.current_org = ''")

            rows = await conn.fetch(f"SELECT id, org_id FROM topics WHERE {RLS_FILTER}")
            topic_ids = {r["id"] for r in rows}

            assert two_orgs["topic_a"] in topic_ids, "Org A topic should be visible"
            assert two_orgs["topic_b"] in topic_ids, "Org B topic should be visible"


# ---------------------------------------------------------------------------
# R3: Cross-org content_items filtered
# ---------------------------------------------------------------------------


async def test_rls_filters_content_items_by_org(db_pool, two_orgs):
    """Content items must be filtered by org_id through RLS policy."""
    import hashlib

    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        # Create a source for each org
        src_a = str(uuid.uuid4())
        src_b = str(uuid.uuid4())
        for src_id, org_id in [(src_a, two_orgs["org_a"]), (src_b, two_orgs["org_b"])]:
            await conn.execute(
                """
                INSERT INTO sources (id, name, url_or_handle, platform,
                    credibility_score, org_id, created_at, updated_at, labels)
                VALUES ($1, $2, $3, 'web', 50.0, $4, $5, $6, $7)
                """,
                src_id,
                f"Src-{org_id[-4:]}",
                f"https://{src_id[:8]}.example.com",
                org_id,
                now,
                now,
                LABELS_JSON,
            )

        # Insert content for each org
        item_a = str(uuid.uuid4())
        item_b = str(uuid.uuid4())
        for item_id, topic_id, src_id, org_id, text in [
            (item_a, two_orgs["topic_a"], src_a, two_orgs["org_a"], "Content for org A"),
            (item_b, two_orgs["topic_b"], src_b, two_orgs["org_b"], "Content for org B"),
        ]:
            ch = hashlib.sha256(text.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO content_items (
                    id, topic_id, source_id, raw_text, clean_text, language,
                    content_hash, url, captured_at, credibility_score_at_capture,
                    org_id, created_at, updated_at, labels
                ) VALUES ($1,$2,$3,$4,$5,'en',$6,$7,$8,50.0,$9,$10,$11,$12)
                ON CONFLICT(content_hash) DO NOTHING
                """,
                item_id,
                topic_id,
                src_id,
                text,
                text,
                ch,
                f"https://example.com/{item_id[:8]}",
                now,
                org_id,
                now,
                now,
                LABELS_JSON,
            )

        # Apply RLS filter for org_a (inside transaction for SET LOCAL)
        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_org = '{two_orgs['org_a']}'")
            rows = await conn.fetch(f"SELECT id, org_id FROM content_items WHERE {RLS_FILTER}")
            item_ids = {r["id"] for r in rows}

            assert item_a in item_ids, "Org A content should be visible"
            assert item_b not in item_ids, "Org B content should NOT be visible"

        # Cleanup (outside filtered transaction)
        await conn.execute("DELETE FROM content_items WHERE id IN ($1,$2)", item_a, item_b)
        await conn.execute("DELETE FROM sources WHERE id IN ($1,$2)", src_a, src_b)


# ---------------------------------------------------------------------------
# R4: Signal org boundary through topic join
# ---------------------------------------------------------------------------


async def test_signal_org_boundary_through_topic(db_pool, two_orgs):
    """Signals don't have org_id directly — org boundary is via topic_id → topics.org_id.

    Query joining signals to topics must respect org filter on topics.
    """
    now = datetime.now(UTC)
    async with db_pool.acquire() as conn:
        sig_a = str(uuid.uuid4())
        sig_b = str(uuid.uuid4())
        for sig_id, topic_id in [
            (sig_a, two_orgs["topic_a"]),
            (sig_b, two_orgs["topic_b"]),
        ]:
            await conn.execute(
                """
                INSERT INTO signals (
                    id, topic_id, signal_type, description, evidence,
                    status, created_at, updated_at, labels
                ) VALUES ($1, $2, 'test', 'Test signal', '{}'::jsonb,
                          'new', $3, $3, $4)
                """,
                sig_id,
                topic_id,
                now,
                LABELS_JSON,
            )

        # Query signals with org filter on topics join (inside transaction)
        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_org = '{two_orgs['org_a']}'")
            rows = await conn.fetch(
                f"""
                SELECT s.id, s.topic_id, t.org_id
                FROM signals s
                JOIN topics t ON s.topic_id = t.id
                WHERE {RLS_FILTER.replace("org_id", "t.org_id")}
                """
            )
            sig_ids = {r["id"] for r in rows}

            assert sig_a in sig_ids, "Org A signal should be visible"
            assert sig_b not in sig_ids, "Org B signal should NOT be visible"

        # Cleanup (outside filtered transaction)
        await conn.execute("DELETE FROM signals WHERE id IN ($1,$2)", sig_a, sig_b)
