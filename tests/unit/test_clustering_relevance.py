"""Unit tests for clustering relevance filtering (Phase: Topic Relevance Gate).

pytest.mark.unit — tests SQL constants and function signatures, no DB required.
"""

from __future__ import annotations


class TestClusteringSQLRelevanceFilter:
    """Verify clustering SQL includes topic_relevance_score predicate."""

    def test_sql_topic_embeddings_filters_by_relevance(self):
        from anveshak.analyst.clustering import SQL_TOPIC_EMBEDDINGS

        assert "topic_relevance_score" in SQL_TOPIC_EMBEDDINGS
        # NULL scores should be included (backward compat)
        assert "IS NULL" in SQL_TOPIC_EMBEDDINGS
        # Threshold parameter ($2) must be present
        assert "$2" in SQL_TOPIC_EMBEDDINGS

    def test_sql_topic_embeddings_windowed_filters_by_relevance(self):
        from anveshak.analyst.clustering import SQL_TOPIC_EMBEDDINGS_WINDOWED

        assert "topic_relevance_score" in SQL_TOPIC_EMBEDDINGS_WINDOWED
        assert "IS NULL" in SQL_TOPIC_EMBEDDINGS_WINDOWED
        # Threshold is $2, window days is $3
        assert "$2" in SQL_TOPIC_EMBEDDINGS_WINDOWED
        assert "$3" in SQL_TOPIC_EMBEDDINGS_WINDOWED


class TestLoadEmbeddingsSignature:
    """Verify load_embeddings accepts relevance_threshold parameter."""

    def test_has_relevance_threshold_parameter(self):
        import inspect

        from anveshak.analyst.clustering import load_embeddings

        sig = inspect.signature(load_embeddings)
        assert "relevance_threshold" in sig.parameters
        # Default should be 0.0 (include everything if not specified)
        assert sig.parameters["relevance_threshold"].default == 0.0


class TestResolveThresholdInClustering:
    """Verify run_clustering uses resolve_threshold."""

    def test_sql_get_topic_relevance_threshold_exists(self):
        from anveshak.analyst.clustering import SQL_GET_TOPIC_RELEVANCE_THRESHOLD

        assert "topic_relevance_threshold" in SQL_GET_TOPIC_RELEVANCE_THRESHOLD
        assert "topics" in SQL_GET_TOPIC_RELEVANCE_THRESHOLD
