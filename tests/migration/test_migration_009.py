"""Migration 009 tests — Engine C schema.

Verifies scam_templates, topic_templates, identifier_clusters,
identifier_cluster_items tables, indexes, CHECK constraints,
seed templates, and topics.identifier_signal_threshold column.

Requires: make up (PostgreSQL running with migrations applied)
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.migration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Table existence
# ---------------------------------------------------------------------------

ENGINE_C_TABLES = [
    "scam_templates",
    "topic_templates",
    "identifier_clusters",
    "identifier_cluster_items",
]


@pytest.mark.parametrize("table_name", ENGINE_C_TABLES)
async def test_engine_c_table_exists(db_pool, table_name):
    """All Engine C tables must exist after migration 009."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)",
            table_name,
        )
    assert exists, f"Table '{table_name}' does not exist — migration 009 missing"


# ---------------------------------------------------------------------------
# scam_templates — columns
# ---------------------------------------------------------------------------


async def test_scam_templates_has_expected_columns(db_pool):
    """scam_templates must have all required columns."""
    expected = {
        "id",
        "org_id",
        "name",
        "display",
        "category",
        "keywords",
        "min_keyword_hits",
        "expected_identifiers",
        "severity",
        "reference_embedding",
        "legal_sections",
        "is_builtin",
        "is_active",
        "created_at",
        "updated_at",
        "labels",
    }
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'scam_templates'"
        )
    actual = {r["column_name"] for r in rows}
    missing = expected - actual
    assert not missing, f"scam_templates missing columns: {missing}"


# ---------------------------------------------------------------------------
# scam_templates — CHECK constraints
# ---------------------------------------------------------------------------


async def test_scam_templates_category_check(db_pool):
    """scam_templates.category must have CHECK constraint for valid values."""
    async with db_pool.acquire() as conn:
        constraints = await conn.fetch(
            "SELECT conname, pg_get_constraintdef(oid) AS def "
            "FROM pg_constraint "
            "WHERE conrelid = 'scam_templates'::regclass "
            "AND contype = 'c'"
        )
    defs = [r["def"] for r in constraints]
    category_check = any("category" in d for d in defs)
    assert category_check, (
        f"scam_templates must have CHECK constraint on category. Found constraints: {defs}"
    )


async def test_scam_templates_severity_check(db_pool):
    """scam_templates.severity must have CHECK constraint for valid values."""
    async with db_pool.acquire() as conn:
        constraints = await conn.fetch(
            "SELECT conname, pg_get_constraintdef(oid) AS def "
            "FROM pg_constraint "
            "WHERE conrelid = 'scam_templates'::regclass "
            "AND contype = 'c'"
        )
    defs = [r["def"] for r in constraints]
    severity_check = any("severity" in d for d in defs)
    assert severity_check, (
        f"scam_templates must have CHECK constraint on severity. Found constraints: {defs}"
    )


# ---------------------------------------------------------------------------
# scam_templates — labels non-optional (AGENTS.md rule 2)
# ---------------------------------------------------------------------------


async def test_scam_templates_labels_not_nullable(db_pool):
    """scam_templates.labels must be NOT NULL (AGENTS.md rule 2)."""
    async with db_pool.acquire() as conn:
        is_nullable = await conn.fetchval(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'scam_templates' AND column_name = 'labels'"
        )
    assert is_nullable == "NO", "scam_templates.labels must be NOT NULL"


# ---------------------------------------------------------------------------
# scam_templates — reference_embedding uses vector(384)
# ---------------------------------------------------------------------------


async def test_scam_templates_reference_embedding_type(db_pool):
    """scam_templates.reference_embedding must be vector(384) for MiniLM-L6-v2."""
    async with db_pool.acquire() as conn:
        udt = await conn.fetchval(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = 'scam_templates' "
            "AND column_name = 'reference_embedding'"
        )
    assert udt == "vector", f"reference_embedding must be vector type, got '{udt}'"


# ---------------------------------------------------------------------------
# topic_templates — composite PK
# ---------------------------------------------------------------------------


async def test_topic_templates_pk(db_pool):
    """topic_templates PK must be (topic_id, template_id)."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "  AND a.attnum = ANY(i.indkey) "
            "JOIN pg_class c ON c.oid = i.indrelid "
            "WHERE c.relname = 'topic_templates' AND i.indisprimary"
        )
    pk_cols = {r["attname"] for r in rows}
    assert pk_cols == {"topic_id", "template_id"}, (
        f"topic_templates PK must be (topic_id, template_id), got {pk_cols}"
    )


# ---------------------------------------------------------------------------
# identifier_clusters — columns
# ---------------------------------------------------------------------------


async def test_identifier_clusters_has_expected_columns(db_pool):
    """identifier_clusters must have all required columns."""
    expected = {
        "id",
        "topic_id",
        "identifier_type",
        "identifier_value",
        "source_count",
        "content_item_count",
        "first_seen_at",
        "last_seen_at",
        "created_at",
        "updated_at",
        "labels",
    }
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'identifier_clusters'"
        )
    actual = {r["column_name"] for r in rows}
    missing = expected - actual
    assert not missing, f"identifier_clusters missing columns: {missing}"


async def test_identifier_clusters_labels_not_nullable(db_pool):
    """identifier_clusters.labels must be NOT NULL (AGENTS.md rule 2)."""
    async with db_pool.acquire() as conn:
        is_nullable = await conn.fetchval(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'identifier_clusters' AND column_name = 'labels'"
        )
    assert is_nullable == "NO", "identifier_clusters.labels must be NOT NULL"


# ---------------------------------------------------------------------------
# identifier_clusters — UNIQUE index on (topic_id, identifier_type, identifier_value)
# ---------------------------------------------------------------------------


async def test_identifier_clusters_unique_index(db_pool):
    """identifier_clusters must have UNIQUE index on (topic_id, type, value)."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'identifier_clusters' "
            "AND indexname = 'idx_ic_topic_type_value'"
        )
    assert len(rows) == 1, "idx_ic_topic_type_value must exist"
    assert "UNIQUE" in rows[0]["indexdef"], "idx_ic_topic_type_value must be UNIQUE"


# ---------------------------------------------------------------------------
# identifier_clusters — source_count DESC index
# ---------------------------------------------------------------------------


async def test_identifier_clusters_source_count_index(db_pool):
    """identifier_clusters must have index on (topic_id, source_count DESC)."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'identifier_clusters' "
            "AND indexname = 'idx_ic_source_count'"
        )
    assert len(rows) == 1, "idx_ic_source_count must exist"
    assert "source_count" in rows[0]["indexdef"], "idx_ic_source_count must index source_count"


# ---------------------------------------------------------------------------
# identifier_cluster_items — composite PK
# ---------------------------------------------------------------------------


async def test_identifier_cluster_items_pk(db_pool):
    """identifier_cluster_items PK must be (identifier_cluster_id, content_item_id)."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "  AND a.attnum = ANY(i.indkey) "
            "JOIN pg_class c ON c.oid = i.indrelid "
            "WHERE c.relname = 'identifier_cluster_items' AND i.indisprimary"
        )
    pk_cols = {r["attname"] for r in rows}
    assert pk_cols == {"identifier_cluster_id", "content_item_id"}, (
        f"identifier_cluster_items PK must be "
        f"(identifier_cluster_id, content_item_id), got {pk_cols}"
    )


# ---------------------------------------------------------------------------
# extracted_entities — partial index for identifier types
# ---------------------------------------------------------------------------


async def test_extracted_entities_identifier_types_index(db_pool):
    """extracted_entities must have partial index for Engine C identifier types."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'extracted_entities' "
            "AND indexname = 'idx_entities_identifier_types'"
        )
    assert len(rows) == 1, "idx_entities_identifier_types must exist"
    indexdef = rows[0]["indexdef"]
    assert "PHONE_IN" in indexdef, "partial index must include PHONE_IN"
    assert "UPI" in indexdef, "partial index must include UPI"
    assert "CRYPTO_BTC" in indexdef, "partial index must include CRYPTO_BTC"


# ---------------------------------------------------------------------------
# topics — identifier_signal_threshold column
# ---------------------------------------------------------------------------


async def test_topics_has_identifier_signal_threshold(db_pool):
    """topics must have identifier_signal_threshold column after migration 009."""
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'topics' "
            "AND column_name = 'identifier_signal_threshold')"
        )
    assert exists, "topics.identifier_signal_threshold column must exist"


async def test_topics_identifier_signal_threshold_default(db_pool):
    """topics.identifier_signal_threshold must default to 2."""
    async with db_pool.acquire() as conn:
        default = await conn.fetchval(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'topics' "
            "AND column_name = 'identifier_signal_threshold'"
        )
    assert default is not None, "identifier_signal_threshold must have a default"
    assert "2" in str(default), f"identifier_signal_threshold default must be 2, got '{default}'"


# ---------------------------------------------------------------------------
# Seed data — 11 built-in templates
# ---------------------------------------------------------------------------


async def test_builtin_templates_seeded(db_pool):
    """11 built-in templates must be seeded with is_builtin=true."""
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM scam_templates WHERE is_builtin = true")
    assert count == 11, f"Expected 11 built-in templates, got {count}"


async def test_builtin_templates_have_null_org_id(db_pool):
    """Built-in templates must have org_id=NULL (global, not org-scoped)."""
    async with db_pool.acquire() as conn:
        non_null = await conn.fetchval(
            "SELECT COUNT(*) FROM scam_templates WHERE is_builtin = true AND org_id IS NOT NULL"
        )
    assert non_null == 0, "Built-in templates must have org_id=NULL"


EXPECTED_BUILTIN_NAMES = [
    "investment_fraud",
    "mule_recruitment",
    "maas",
    "digital_arrest",
    "job_fraud",
    "pump_and_dump",
    "fake_research_report",
    "drug_sale",
    "drug_delivery_recruitment",
    "fake_sim_sale",
    "crypto_cashout",
]


async def test_builtin_template_names(db_pool):
    """All 11 expected built-in template names must exist."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name FROM scam_templates WHERE is_builtin = true")
    actual = {r["name"] for r in rows}
    expected = set(EXPECTED_BUILTIN_NAMES)
    missing = expected - actual
    assert not missing, f"Missing built-in templates: {missing}"


async def test_builtin_templates_have_keywords(db_pool):
    """Every built-in template must have at least 3 keywords."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, array_length(keywords, 1) AS kw_count "
            "FROM scam_templates WHERE is_builtin = true"
        )
    for r in rows:
        assert r["kw_count"] is not None and r["kw_count"] >= 3, (
            f"Template '{r['name']}' must have >= 3 keywords, got {r['kw_count']}"
        )


async def test_builtin_templates_have_valid_severity(db_pool):
    """Every built-in template must have severity matching the plan."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, severity FROM scam_templates WHERE is_builtin = true")
    severity_map = {r["name"]: r["severity"] for r in rows}
    # Verify critical templates
    for name in ["investment_fraud", "mule_recruitment", "maas", "pump_and_dump"]:
        if name in severity_map:
            assert severity_map[name] == "CRITICAL", (
                f"Template '{name}' must be CRITICAL, got '{severity_map[name]}'"
            )


async def test_builtin_templates_have_valid_category(db_pool):
    """Every built-in template must have a valid category."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, category FROM scam_templates WHERE is_builtin = true")
    valid = {"fraud", "info_op", "narco", "custom"}
    for r in rows:
        assert r["category"] in valid, (
            f"Template '{r['name']}' has invalid category '{r['category']}'"
        )


# ---------------------------------------------------------------------------
# FK cascade — topic_templates, identifier_clusters, identifier_cluster_items
# ---------------------------------------------------------------------------


async def test_identifier_clusters_cascade_on_delete(db_pool):
    """identifier_clusters.topic_id FK must have ON DELETE CASCADE."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT conname, confdeltype::text FROM pg_constraint "
            "WHERE conrelid = 'identifier_clusters'::regclass "
            "AND contype = 'f'"
        )
    assert len(rows) >= 1, "identifier_clusters must have at least one FK"
    topic_fk = [r for r in rows if "topic" in r["conname"]]
    assert len(topic_fk) == 1, "identifier_clusters must have topic_id FK"
    assert topic_fk[0]["confdeltype"] == "c", (
        "identifier_clusters.topic_id FK must be ON DELETE CASCADE"
    )


async def test_topic_templates_cascade_on_delete(db_pool):
    """topic_templates FKs must have ON DELETE CASCADE."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT conname, confdeltype::text FROM pg_constraint "
            "WHERE conrelid = 'topic_templates'::regclass "
            "AND contype = 'f'"
        )
    for r in rows:
        assert r["confdeltype"] == "c", (
            f"FK '{r['conname']}' on topic_templates must be ON DELETE CASCADE"
        )


async def test_identifier_cluster_items_cascade_on_delete(db_pool):
    """identifier_cluster_items FKs must have ON DELETE CASCADE."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT conname, confdeltype::text FROM pg_constraint "
            "WHERE conrelid = 'identifier_cluster_items'::regclass "
            "AND contype = 'f'"
        )
    for r in rows:
        assert r["confdeltype"] == "c", (
            f"FK '{r['conname']}' on identifier_cluster_items must be ON DELETE CASCADE"
        )
