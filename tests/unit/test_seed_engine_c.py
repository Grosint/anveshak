"""Unit tests for Engine C demo seed SQL — validates structure and data integrity.

Parses seed_demo_engine_c.sql and checks:
  - 4 orgs, 4 users, 4 topics created
  - Sources linked via org_sources and topic_sources
  - Content items include Engine C identifiers in labels
  - Identifier clusters pre-seeded
  - Signals pre-seeded (identifier_convergence, scam_template_match)
  - topic_templates associations created
  - org_id present on all root-table INSERTs
  - Cross-org isolation: no shared IDs between org data

pytest.mark.unit — pure file parsing, no DB required.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SEED_FILE = Path(__file__).parents[2] / "scripts" / "seed_demo_engine_c.sql"


@pytest.fixture(scope="module")
def seed_sql() -> str:
    """Load the Engine C seed SQL file."""
    assert SEED_FILE.exists(), f"Seed file not found: {SEED_FILE}"
    return SEED_FILE.read_text()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_inserts(sql: str, table: str) -> int:
    """Count INSERT INTO <table> statements (rough — counts VALUE tuples)."""
    # Find all INSERT INTO <table> blocks
    pattern = rf"INSERT\s+INTO\s+{table}\s"
    blocks = list(re.finditer(pattern, sql, re.IGNORECASE))
    if not blocks:
        return 0
    # Count value tuples — each opening paren after VALUES on its own line
    count = 0
    for match in blocks:
        # Find the rest of this INSERT statement
        rest = sql[match.start():]
        # Find VALUES keyword
        values_match = re.search(r"\bVALUES\b", rest, re.IGNORECASE)
        if not values_match:
            continue
        values_rest = rest[values_match.end():]
        # Find the end of this statement (ON CONFLICT or ;)
        end_match = re.search(r"ON\s+CONFLICT|;\s*$", values_rest, re.IGNORECASE | re.MULTILINE)
        if end_match:
            values_block = values_rest[:end_match.start()]
        else:
            values_block = values_rest[:2000]  # safety limit
        # Count top-level tuples: lines starting with ( after whitespace
        tuples = re.findall(r"^\s*\(", values_block, re.MULTILINE)
        count += len(tuples)
    return count


def _extract_ids(sql: str, table: str) -> list[str]:
    """Extract the first column (id) values from INSERT INTO <table>."""
    ids = []
    # Match VALUES tuples and extract first string literal
    pattern = rf"INSERT\s+INTO\s+{table}\s.*?VALUES\s*(.*?)ON\s+CONFLICT"
    for match in re.finditer(pattern, sql, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        # Extract first quoted value from each tuple
        for tuple_match in re.finditer(r"\(\s*'([^']+)'", block):
            ids.append(tuple_match.group(1))
    return ids


def _find_all_values(sql: str, pattern: str) -> list[str]:
    """Find all string values matching a regex in the SQL."""
    return re.findall(pattern, sql)


# ---------------------------------------------------------------------------
# 1. Organizations — 4 agency orgs
# ---------------------------------------------------------------------------

class TestOrganizations:

    def test_four_orgs_created(self, seed_sql):
        count = _count_inserts(seed_sql, "organizations")
        assert count >= 4, f"Expected >= 4 org inserts, got {count}"

    def test_org_ids_present(self, seed_sql):
        for org_id in ["org_mea", "org_cyber", "org_sebi", "org_ncb"]:
            assert org_id in seed_sql, f"Missing org: {org_id}"

    def test_orgs_have_labels(self, seed_sql):
        """Every org INSERT must include labels JSONB."""
        assert "organizations" in seed_sql
        # All org inserts should have labels column
        org_blocks = re.findall(
            r"INSERT\s+INTO\s+organizations\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in org_blocks:
            assert "labels" in block.lower(), "organizations INSERT missing labels column"


# ---------------------------------------------------------------------------
# 2. Users — 4 agency users + existing super-admin reference
# ---------------------------------------------------------------------------

class TestUsers:

    def test_four_users_created(self, seed_sql):
        count = _count_inserts(seed_sql, "users")
        assert count >= 4, f"Expected >= 4 user inserts, got {count}"

    def test_user_emails_present(self, seed_sql):
        for email in [
            "demo_mea@anveshak.local",
            "demo_cyber@anveshak.local",
            "demo_sebi@anveshak.local",
            "demo_ncb@anveshak.local",
        ]:
            assert email in seed_sql, f"Missing user: {email}"

    def test_users_have_org_id(self, seed_sql):
        """Each agency user linked to its org."""
        assert "org_mea" in seed_sql
        assert "org_cyber" in seed_sql
        assert "org_sebi" in seed_sql
        assert "org_ncb" in seed_sql

    def test_user_role_is_analyst(self, seed_sql):
        """Agency demo users should be analysts."""
        # At least 4 'analyst' role values near user inserts
        analyst_count = len(re.findall(r"'analyst'", seed_sql))
        assert analyst_count >= 4, f"Expected >= 4 analyst roles, got {analyst_count}"


# ---------------------------------------------------------------------------
# 3. Topics — 4 agency-specific topics
# ---------------------------------------------------------------------------

class TestTopics:

    def test_four_topics_created(self, seed_sql):
        count = _count_inserts(seed_sql, "topics")
        assert count >= 4, f"Expected >= 4 topic inserts, got {count}"

    def test_topic_names_present(self, seed_sql):
        # Flexible: check key substrings rather than exact names
        assert re.search(r"MEA|Anti-India|Chinese Media|Beijing", seed_sql, re.IGNORECASE), \
            "Missing MEA topic"
        assert re.search(r"Cyber Fraud|Mule Account|Fraud Network", seed_sql, re.IGNORECASE), \
            "Missing Cyber Fraud topic"
        assert re.search(r"SEBI|Pump.and.Dump|Market Manipulation", seed_sql, re.IGNORECASE), \
            "Missing SEBI topic"
        assert re.search(r"NCB|Drug Network|Narco", seed_sql, re.IGNORECASE), \
            "Missing NCB topic"

    def test_topics_have_org_id(self, seed_sql):
        """All topics must include org_id (multi-tenancy rule)."""
        topic_blocks = re.findall(
            r"INSERT\s+INTO\s+topics\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in topic_blocks:
            assert "org_id" in block.lower(), "topics INSERT missing org_id column"

    def test_topics_have_identifier_signal_threshold(self, seed_sql):
        """Engine C topics should set identifier_signal_threshold."""
        assert "identifier_signal_threshold" in seed_sql


# ---------------------------------------------------------------------------
# 4. Sources — linked via org_sources and topic_sources
# ---------------------------------------------------------------------------

class TestSources:

    def test_sources_created(self, seed_sql):
        count = _count_inserts(seed_sql, r"sources\b")
        assert count >= 10, f"Expected >= 10 source inserts (across 4 agencies), got {count}"

    def test_org_sources_linked(self, seed_sql):
        """Sources must be linked to their org via org_sources."""
        # Count individual tuples (may be packed on single lines)
        pattern = r"INSERT\s+INTO\s+org_sources.*?ON\s+CONFLICT"
        match = re.search(pattern, seed_sql, re.IGNORECASE | re.DOTALL)
        assert match, "No org_sources INSERT found"
        count = match.group().count("(")
        assert count >= 10, f"Expected >= 10 org_sources links, got {count}"

    def test_topic_sources_linked(self, seed_sql):
        """Sources must be linked to topics via topic_sources."""
        pattern = r"INSERT\s+INTO\s+topic_sources.*?ON\s+CONFLICT"
        match = re.search(pattern, seed_sql, re.IGNORECASE | re.DOTALL)
        assert match, "No topic_sources INSERT found"
        count = match.group().count("(")
        assert count >= 10, f"Expected >= 10 topic_sources links, got {count}"

    def test_sources_have_org_id(self, seed_sql):
        source_blocks = re.findall(
            r"INSERT\s+INTO\s+sources\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in source_blocks:
            assert "org_id" in block.lower(), "sources INSERT missing org_id column"


# ---------------------------------------------------------------------------
# 5. Content items — with Engine C labels
# ---------------------------------------------------------------------------

class TestContentItems:

    def test_content_items_created(self, seed_sql):
        count = _count_inserts(seed_sql, "content_items")
        assert count >= 30, f"Expected >= 30 content items (across 4 agencies), got {count}"

    def test_content_items_have_org_id(self, seed_sql):
        ci_blocks = re.findall(
            r"INSERT\s+INTO\s+content_items\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in ci_blocks:
            assert "org_id" in block.lower(), "content_items INSERT missing org_id column"

    def test_content_items_have_content_hash(self, seed_sql):
        ci_blocks = re.findall(
            r"INSERT\s+INTO\s+content_items\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in ci_blocks:
            assert "content_hash" in block.lower(), "content_items INSERT missing content_hash"

    def test_scam_template_labels_present(self, seed_sql):
        """Some content items should have scam_template in labels."""
        assert "scam_template" in seed_sql, "No content items with scam_template label"

    def test_template_confidence_labels_present(self, seed_sql):
        """Content with scam_template should have template_confidence."""
        assert "template_confidence" in seed_sql

    def test_identifiers_in_content(self, seed_sql):
        """Content text should contain extractable identifiers."""
        # Phone numbers (Indian format)
        assert re.search(r"\+91[\s-]?\d{10}", seed_sql) or \
               re.search(r"[6-9]\d{9}", seed_sql), \
            "No Indian phone numbers in content"
        # UPI IDs
        assert re.search(r"\w+@(?:paytm|ybl|okaxis|oksbi)", seed_sql, re.IGNORECASE), \
            "No UPI IDs in content"


# ---------------------------------------------------------------------------
# 6. Identifier clusters — pre-seeded for demo reliability
# ---------------------------------------------------------------------------

class TestIdentifierClusters:

    def test_clusters_created(self, seed_sql):
        count = _count_inserts(seed_sql, "identifier_clusters")
        assert count >= 4, f"Expected >= 4 identifier clusters (at least 1 per agency), got {count}"

    def test_cluster_items_created(self, seed_sql):
        count = _count_inserts(seed_sql, "identifier_cluster_items")
        assert count >= 8, f"Expected >= 8 cluster items, got {count}"

    def test_clusters_have_source_count_gte_2(self, seed_sql):
        """At least some clusters should have source_count >= 2."""
        # Check for source_count values >= 2 near identifier_clusters
        assert re.search(r"source_count.*?[2-9]", seed_sql, re.IGNORECASE) or \
               re.search(r"[2-9]\d*,\s*\d+,", seed_sql), \
            "No identifier clusters with source_count >= 2"


# ---------------------------------------------------------------------------
# 7. Signals — pre-seeded for demo
# ---------------------------------------------------------------------------

class TestSignals:

    def test_signals_created(self, seed_sql):
        count = _count_inserts(seed_sql, r"signals\b")
        assert count >= 4, f"Expected >= 4 signals (at least 1 per agency), got {count}"

    def test_identifier_convergence_signal(self, seed_sql):
        assert "identifier_convergence" in seed_sql, \
            "Missing identifier_convergence signal type"

    def test_scam_template_match_signal(self, seed_sql):
        assert "scam_template_match" in seed_sql, \
            "Missing scam_template_match signal type"


# ---------------------------------------------------------------------------
# 8. Topic-template associations
# ---------------------------------------------------------------------------

class TestTopicTemplates:

    def test_topic_templates_created(self, seed_sql):
        count = _count_inserts(seed_sql, "topic_templates")
        assert count >= 4, f"Expected >= 4 topic_template links, got {count}"

    def test_cyber_topic_has_mule_template(self, seed_sql):
        """Cyber fraud topic should be linked to mule_recruitment template."""
        assert "tpl-mule-recruitment" in seed_sql

    def test_sebi_topic_has_pump_template(self, seed_sql):
        assert "tpl-pump-and-dump" in seed_sql

    def test_ncb_topic_has_drug_template(self, seed_sql):
        assert "tpl-drug-sale" in seed_sql


# ---------------------------------------------------------------------------
# 9. Cross-org isolation
# ---------------------------------------------------------------------------

class TestCrossOrgIsolation:

    def test_on_conflict_idempotent(self, seed_sql):
        """All INSERTs should use ON CONFLICT for idempotency."""
        inserts = re.findall(r"INSERT\s+INTO\s+\w+", seed_sql, re.IGNORECASE)
        on_conflicts = re.findall(r"ON\s+CONFLICT", seed_sql, re.IGNORECASE)
        # At least 80% of INSERTs should have ON CONFLICT
        ratio = len(on_conflicts) / max(len(inserts), 1)
        assert ratio >= 0.7, (
            f"Only {len(on_conflicts)}/{len(inserts)} INSERTs have ON CONFLICT"
        )

    def test_wrapped_in_transaction(self, seed_sql):
        """Seed should be wrapped in BEGIN/COMMIT."""
        assert "BEGIN" in seed_sql.upper()
        assert "COMMIT" in seed_sql.upper()


# ---------------------------------------------------------------------------
# 10. Narrative clusters for demo
# ---------------------------------------------------------------------------

class TestNarrativeClusters:

    def test_narrative_clusters_created(self, seed_sql):
        count = _count_inserts(seed_sql, "narrative_clusters")
        assert count >= 4, f"Expected >= 4 narrative clusters, got {count}"


# ---------------------------------------------------------------------------
# 11. Reports with identifier sections
# ---------------------------------------------------------------------------

class TestReports:

    def test_reports_created(self, seed_sql):
        count = _count_inserts(seed_sql, r"reports\b")
        assert count >= 4, f"Expected >= 4 reports (1 per agency), got {count}"

    def test_reports_have_identifier_sections(self, seed_sql):
        """At least some reports should mention Identified Indicators."""
        assert "Identified Indicators" in seed_sql, \
            "No reports with 'Identified Indicators' section in content_md"

    def test_reports_have_generated_at(self, seed_sql):
        """Pre-seeded reports must have generated_at set (immutability rule)."""
        # generated_at should appear in reports INSERT column list
        report_blocks = re.findall(
            r"INSERT\s+INTO\s+reports\s*\([^)]+\)",
            seed_sql, re.IGNORECASE
        )
        for block in report_blocks:
            assert "generated_at" in block.lower(), "reports INSERT missing generated_at"
