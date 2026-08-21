"""Tests for pipeline funnel Prometheus metrics (scraper + analyst).

RED phase: these tests define the expected new metrics before they exist.
"""

import pytest


class TestScraperPipelineMetrics:
    """New scraper metrics for pipeline funnel dashboard."""

    @pytest.mark.unit
    def test_content_quality_counter_exists(self):
        from anveshak.scraper.metrics import scraper_content_quality_total

        assert scraper_content_quality_total._name == "scraper_content_quality"

    @pytest.mark.unit
    def test_content_quality_counter_labels(self):
        from anveshak.scraper.metrics import scraper_content_quality_total

        assert "quality" in scraper_content_quality_total._labelnames
        assert "gate" in scraper_content_quality_total._labelnames

    @pytest.mark.unit
    def test_content_quality_counter_increments(self):
        from anveshak.scraper.metrics import REGISTRY, scraper_content_quality_total

        scraper_content_quality_total.labels(quality="good", gate="passed").inc()
        val = REGISTRY.get_sample_value(
            "scraper_content_quality_total",
            {"quality": "good", "gate": "passed"},
        )
        assert val is not None and val >= 1.0

    @pytest.mark.unit
    def test_url_seen_skip_counter_exists(self):
        from anveshak.scraper.metrics import scraper_url_seen_skip_total

        assert scraper_url_seen_skip_total._name == "scraper_url_seen_skip"

    @pytest.mark.unit
    def test_links_discovered_histogram_exists(self):
        from anveshak.scraper.metrics import scraper_links_discovered

        assert scraper_links_discovered._name == "scraper_links_discovered"


class TestAnalystPipelineMetrics:
    """New analyst metrics for pipeline funnel dashboard."""

    @pytest.mark.unit
    def test_embedding_completed_counter_exists(self):
        from anveshak.analyst.metrics import analyst_embedding_completed_total

        assert analyst_embedding_completed_total._name == "analyst_embedding_completed"

    @pytest.mark.unit
    def test_content_skipped_quality_counter_exists(self):
        from anveshak.analyst.metrics import analyst_content_skipped_quality_total

        assert analyst_content_skipped_quality_total._name == "analyst_content_skipped_quality"

    @pytest.mark.unit
    def test_content_skipped_quality_has_gate_label(self):
        from anveshak.analyst.metrics import analyst_content_skipped_quality_total

        assert "gate" in analyst_content_skipped_quality_total._labelnames

    @pytest.mark.unit
    def test_content_skipped_quality_increments(self):
        from anveshak.analyst.metrics import REGISTRY, analyst_content_skipped_quality_total

        analyst_content_skipped_quality_total.labels(gate="too_short").inc()
        val = REGISTRY.get_sample_value(
            "analyst_content_skipped_quality_total",
            {"gate": "too_short"},
        )
        assert val is not None and val >= 1.0

    @pytest.mark.unit
    def test_clustering_items_gauge_exists(self):
        from anveshak.analyst.metrics import analyst_clustering_items

        assert analyst_clustering_items._name == "analyst_clustering_items"

    @pytest.mark.unit
    def test_clustering_items_has_labels(self):
        from anveshak.analyst.metrics import analyst_clustering_items

        assert "topic_id" in analyst_clustering_items._labelnames
        assert "status" in analyst_clustering_items._labelnames

    @pytest.mark.unit
    def test_orphan_sweep_counter_exists(self):
        from anveshak.analyst.metrics import analyst_orphan_sweep_total

        assert analyst_orphan_sweep_total._name == "analyst_orphan_sweep"

    @pytest.mark.unit
    def test_clustering_edges_gauge_exists(self):
        from anveshak.analyst.metrics import analyst_clustering_edges

        assert analyst_clustering_edges._name == "analyst_clustering_edges"

    @pytest.mark.unit
    def test_clustering_edges_has_topic_label(self):
        from anveshak.analyst.metrics import analyst_clustering_edges

        assert "topic_id" in analyst_clustering_edges._labelnames
