"""Integration tests for Engine C pipeline — real PostgreSQL + Redis.

Tests:
  1. Extraction → DB: extract_identifiers inserts identifier entity rows
  2. Clustering → DB: identifier_cluster_loop builds clusters
  3. Identifier signals → DB: check_identifier_signals fires convergence signal
  4. Template signals → DB: check_template_signals fires template match signal
  5. Template linking API: link, list, unlink

Requires: make up (Docker Compose running with anveshak_test DB)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import LABELS_JSON, insert_content_item

# ---------------------------------------------------------------------------
# 1. Extraction → extracted_entities rows
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestIdentifierExtractionToDB:
    """Verify that identifier entities are written to extracted_entities table."""

    async def test_identifier_entities_inserted(self, db_pool, make_topic, make_source):
        topic_id = await make_topic(name="Cyber Fraud Test")
        source_id = await make_source(name="Fraud Source", platform="telegram")

        # Insert content with known phone + UPI
        text = "Contact +91 9876543210 or pay fraud@ybl for guaranteed returns"
        item_id = await insert_content_item(
            db_pool,
            topic_id,
            source_id,
            text,
        )

        # Manually run identifier extraction and insert (simulates analyse_content)
        from anveshak.analyst.identifiers import extract_identifiers

        matches = extract_identifiers(text, "telegram")

        now = datetime.now(timezone.utc)
        async with db_pool.acquire() as conn:
            for m in matches:
                await conn.execute(
                    """INSERT INTO extracted_entities
                       (id, content_item_id, entity_type, entity_text, confidence,
                        language, created_at, labels)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    str(uuid.uuid4()),
                    item_id,
                    m.identifier_type,
                    m.normalized_value,
                    m.confidence,
                    "en",
                    now,
                    LABELS_JSON,
                )

            # Verify
            rows = await conn.fetch(
                """SELECT entity_type, entity_text FROM extracted_entities
                   WHERE content_item_id = $1
                   AND entity_type IN ('PHONE_IN', 'UPI')""",
                item_id,
            )

        types = {r["entity_type"] for r in rows}
        assert "PHONE_IN" in types, "PHONE_IN not inserted"
        assert "UPI" in types, "UPI not inserted"


# ---------------------------------------------------------------------------
# 2. Clustering → identifier_clusters rows
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestIdentifierClusteringToDB:
    """Verify that identifier_cluster_loop creates clusters in DB."""

    async def test_cluster_created_for_shared_phone(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        topic_id = await make_topic(name="Cluster Test Topic")
        src1 = await make_source(name="Source A", platform="telegram")
        src2 = await make_source(name="Source B", platform="web")

        # Insert 2 content items from different sources with same phone
        phone = "9876543210"
        text1 = f"Call {phone} for investment tips"
        text2 = f"Contact {phone} for guaranteed returns"
        item1 = await insert_content_item(db_pool, topic_id, src1, text1)
        item2 = await insert_content_item(db_pool, topic_id, src2, text2)

        now = datetime.now(timezone.utc)
        async with db_pool.acquire() as conn:
            # Insert identifier entities for both items
            for item_id, source_id in [(item1, src1), (item2, src2)]:
                await conn.execute(
                    """INSERT INTO extracted_entities
                       (id, content_item_id, entity_type, entity_text, confidence,
                        language, created_at, labels)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    str(uuid.uuid4()),
                    item_id,
                    "PHONE_IN",
                    phone,
                    0.95,
                    "en",
                    now,
                    LABELS_JSON,
                )

        # Run clustering cycle
        from anveshak.analyst.scheduler import _run_identifier_cluster_cycle

        total = await _run_identifier_cluster_cycle(db_pool)

        assert total >= 1, "Expected at least 1 cluster to be created"

        # Verify cluster in DB
        async with db_pool.acquire() as conn:
            cluster = await conn.fetchrow(
                """SELECT * FROM identifier_clusters
                   WHERE topic_id = $1
                     AND identifier_type = 'PHONE_IN'
                     AND identifier_value = $2""",
                topic_id,
                phone,
            )
            assert cluster is not None, "Cluster not found in DB"
            assert cluster["source_count"] >= 2, "source_count should be >= 2"

            # Verify junction table
            items = await conn.fetch(
                """SELECT * FROM identifier_cluster_items
                   WHERE identifier_cluster_id = $1""",
                cluster["id"],
            )
            assert len(items) >= 2, "Expected 2 cluster items"


# ---------------------------------------------------------------------------
# 3. Identifier signals → signals rows
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestIdentifierSignalsToDB:
    """Verify that check_identifier_signals fires a signal for breaching clusters."""

    async def test_identifier_convergence_signal_fired(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        topic_id = await make_topic(
            name="Signal Test Topic",
            signal_threshold=2,
        )
        src1 = await make_source(name="Sig Source A", platform="telegram")
        src2 = await make_source(name="Sig Source B", platform="web")

        now = datetime.now(timezone.utc)
        cluster_id = str(uuid.uuid4())

        async with db_pool.acquire() as conn:
            # Directly insert a breaching identifier cluster
            await conn.execute(
                """INSERT INTO identifier_clusters
                   (id, topic_id, identifier_type, identifier_value,
                    source_count, content_item_count,
                    first_seen_at, last_seen_at, labels)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                cluster_id,
                topic_id,
                "PHONE_IN",
                "9876543210",
                3,
                5,
                now,
                now,
                LABELS_JSON,
            )

            # Also need to set identifier_signal_threshold on topic (default 2)
            await conn.execute(
                "UPDATE topics SET identifier_signal_threshold = 2 WHERE id = $1",
                topic_id,
            )

            # Insert cluster items for source evidence
            item1 = str(uuid.uuid4())
            item2 = str(uuid.uuid4())
            for item_id, source_id in [(item1, src1), (item2, src2)]:
                await conn.execute(
                    """INSERT INTO content_items
                       (id, topic_id, source_id, raw_text, clean_text,
                        content_hash, url, captured_at, language,
                        credibility_score_at_capture,
                        created_at, updated_at, labels, org_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                    item_id,
                    topic_id,
                    source_id,
                    "test",
                    "test",
                    str(uuid.uuid4()),
                    f"https://test/{item_id[:8]}",
                    now,
                    "en",
                    75.0,
                    now,
                    now,
                    LABELS_JSON,
                    "org-integration-test",
                )
                await conn.execute(
                    """INSERT INTO identifier_cluster_items
                       (identifier_cluster_id, content_item_id, source_id)
                       VALUES ($1, $2, $3)""",
                    cluster_id,
                    item_id,
                    source_id,
                )

        # Run signal check
        from anveshak.analyst.identifier_signals import check_identifier_signals

        async def noop_broadcast(payload):
            pass

        fired = await check_identifier_signals(db_pool, noop_broadcast)
        assert fired >= 1, "Expected at least 1 identifier_convergence signal"

        # Verify signal in DB
        async with db_pool.acquire() as conn:
            signal = await conn.fetchrow(
                """SELECT * FROM signals
                   WHERE topic_id = $1
                     AND signal_type = 'identifier_convergence'""",
                topic_id,
            )
            assert signal is not None, "Signal not found in DB"
            evidence = json.loads(signal["evidence"])
            assert evidence["identifier_type"] == "PHONE_IN"


# ---------------------------------------------------------------------------
# 4. Template signals → signals rows
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestTemplateSignalsToDB:
    """Verify that check_template_signals fires a signal for template matches."""

    async def test_template_match_signal_fired(
        self,
        db_pool,
        make_topic,
        make_source,
    ):
        topic_id = await make_topic(name="Template Signal Test")
        source_id = await make_source(name="Fraud Content Source", platform="web")

        # Insert content items with scam_template label (simulates analyse_content output)
        for i in range(2):  # HIGH severity needs 2+ matches
            labels = json.dumps(
                {
                    "classification": "OPEN",
                    "domain": "osint",
                    "owner_org": "anveshak",
                    "scam_template": "investment_fraud",
                    "template_confidence": 0.85,
                    "matched_keywords": ["invest", "guaranteed", "returns"],
                    "extracted_identifiers": {"PHONE_IN": ["9876543210"]},
                }
            )
            await insert_content_item(
                db_pool,
                topic_id,
                source_id,
                f"Invest now for guaranteed returns item-{i}",
                content_hash=str(uuid.uuid4()),  # unique hash per item
            )
            # Update labels on the inserted item
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """UPDATE content_items SET labels = $1::jsonb
                       WHERE topic_id = $2 AND clean_text LIKE $3""",
                    labels,
                    topic_id,
                    f"%item-{i}%",
                )

        # Run template signal check
        from anveshak.analyst.template_signals import check_template_signals

        async def noop_broadcast(payload):
            pass

        fired = await check_template_signals(db_pool, noop_broadcast)
        # investment_fraud is CRITICAL severity → threshold=1 → should fire
        assert fired >= 1, "Expected at least 1 scam_template_match signal"


# ---------------------------------------------------------------------------
# 5. Template linking API
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestTemplateLinkingDB:
    """Verify template link/unlink/list DB functions."""

    async def test_link_list_unlink(self, db_pool, make_topic):
        topic_id = await make_topic(name="Template Link Test")

        from anveshak.api.db.identifiers import (
            link_template,
            list_topic_templates,
            unlink_template,
        )

        # Get a template ID from the seeded data
        async with db_pool.acquire() as conn:
            template = await conn.fetchrow(
                "SELECT id FROM scam_templates WHERE name = 'investment_fraud'"
            )

        if not template:
            pytest.skip("No seeded templates — run migration 009 first")

        template_id = template["id"]

        async with db_pool.acquire() as conn:
            # Link
            await link_template(conn, topic_id=topic_id, template_id=template_id)

            # List
            templates = await list_topic_templates(conn, topic_id=topic_id)
            assert len(templates) >= 1
            assert any(t["name"] == "investment_fraud" for t in templates)

            # Unlink
            await unlink_template(conn, topic_id=topic_id, template_id=template_id)

            # List again — should be empty
            templates = await list_topic_templates(conn, topic_id=topic_id)
            assert not any(t["name"] == "investment_fraud" for t in templates)
