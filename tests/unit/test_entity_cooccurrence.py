"""Unit tests for entity co-occurrence and intelligence endpoints.

Tests:
  - SQL queries are well-formed
  - Entity co-occurrence query joins correctly
  - Topic similarity uses pgvector distance
  - Cluster duplicates use cosine similarity threshold
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestEntityCooccurrenceSQL:

    def test_cooccurrence_query_has_topic_filter(self):
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE

        assert "topic_id = $1" in SQL_ENTITY_COOCCURRENCE

    def test_cooccurrence_query_self_join(self):
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE

        assert "e1.content_item_id = e2.content_item_id" in SQL_ENTITY_COOCCURRENCE
        assert "e1.id < e2.id" in SQL_ENTITY_COOCCURRENCE

    def test_cooccurrence_filters_entity_types(self):
        from anveshak.api.routes.intelligence import SQL_ENTITY_COOCCURRENCE

        assert "PERSON" in SQL_ENTITY_COOCCURRENCE
        assert "ORG" in SQL_ENTITY_COOCCURRENCE


class TestTopicSimilaritySQL:

    def test_similarity_query_uses_pgvector(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_SIMILARITY

        assert "<=>" in SQL_TOPIC_SIMILARITY

    def test_similarity_excludes_self(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_SIMILARITY

        assert "t.id != $1" in SQL_TOPIC_SIMILARITY

    def test_similarity_filters_active_topics(self):
        from anveshak.api.routes.intelligence import SQL_TOPIC_SIMILARITY

        assert "status = 'active'" in SQL_TOPIC_SIMILARITY


class TestClusterDuplicatesSQL:

    def test_duplicates_query_uses_cosine_distance(self):
        from anveshak.api.routes.intelligence import SQL_CLUSTER_DUPLICATES

        assert "<=>" in SQL_CLUSTER_DUPLICATES

    def test_duplicates_avoids_self_comparison(self):
        from anveshak.api.routes.intelligence import SQL_CLUSTER_DUPLICATES

        assert "nc1.id < nc2.id" in SQL_CLUSTER_DUPLICATES

    def test_duplicates_has_similarity_threshold(self):
        from anveshak.api.routes.intelligence import SQL_CLUSTER_DUPLICATES

        assert ">= $2" in SQL_CLUSTER_DUPLICATES


class TestSourceDiscoverySQL:

    def test_outbound_links_extracts_urls(self):
        from anveshak.api.routes.intelligence import SQL_OUTBOUND_LINKS

        assert "regexp_matches" in SQL_OUTBOUND_LINKS
        assert "https?://" in SQL_OUTBOUND_LINKS

    def test_existing_sources_query(self):
        from anveshak.api.routes.intelligence import SQL_EXISTING_SOURCE_URLS

        assert "url_or_handle" in SQL_EXISTING_SOURCE_URLS
        assert "is_active = TRUE" in SQL_EXISTING_SOURCE_URLS
