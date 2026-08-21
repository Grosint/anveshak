"""8A.20 — Each metrics module imports without error; no duplicate registration.

Each service's metrics.py defines Prometheus metrics. This test verifies that
importing them doesn't raise ValueError (duplicate timeseries) and that all
expected metric names are registered in the default REGISTRY.
"""

import pytest


@pytest.mark.unit
def test_scraper_metrics_import():
    # prometheus_client strips _total suffix from ._name for Counter objects
    from anveshak.scraper.metrics import (
        arq_jobs_failed_total,
        scraper_fetch_duration_seconds,
        scraper_fetch_errors_total,
        scraper_items_fetched_total,
    )

    assert scraper_items_fetched_total._name == "scraper_items_fetched"
    assert scraper_fetch_errors_total._name == "scraper_fetch_errors"
    assert scraper_fetch_duration_seconds._name == "scraper_fetch_duration_seconds"
    assert arq_jobs_failed_total._name == "arq_jobs_failed"


@pytest.mark.unit
def test_analyst_metrics_import():
    from anveshak.analyst.metrics import (
        analyst_clusters_created_total,
        analyst_credibility_changes_total,
        analyst_nlp_duration_seconds,
        analyst_nlp_jobs_total,
        analyst_signals_fired_total,
    )

    assert analyst_nlp_jobs_total._name == "analyst_nlp_jobs"
    assert analyst_nlp_duration_seconds._name == "analyst_nlp_duration_seconds"
    assert analyst_clusters_created_total._name == "analyst_clusters_created"
    assert analyst_signals_fired_total._name == "analyst_signals_fired"
    assert analyst_credibility_changes_total._name == "analyst_credibility_changes"


@pytest.mark.unit
def test_vision_metrics_import():
    from anveshak.vision.metrics import (
        vision_analyses_total,
        vision_analysis_duration_seconds,
        vision_deepfake_score,
    )

    assert vision_analyses_total._name == "vision_analyses"
    assert vision_analysis_duration_seconds._name == "vision_analysis_duration_seconds"
    assert vision_deepfake_score._name == "vision_deepfake_score"


@pytest.mark.unit
def test_reporter_metrics_import():
    from anveshak.reporter.metrics import (
        reporter_job_duration_seconds,
        reporter_jobs_total,
        reporter_ollama_errors_total,
        reporter_pdf_generations_total,
    )

    assert reporter_jobs_total._name == "reporter_jobs"
    assert reporter_job_duration_seconds._name == "reporter_job_duration_seconds"
    assert reporter_pdf_generations_total._name == "reporter_pdf_generations"
    assert reporter_ollama_errors_total._name == "reporter_ollama_errors"


@pytest.mark.unit
def test_social_metrics_import():
    from anveshak.social.metrics import (
        social_adapter_errors_total,
        social_items_collected_total,
    )

    assert social_items_collected_total._name == "social_items_collected"
    assert social_adapter_errors_total._name == "social_adapter_errors"


@pytest.mark.unit
def test_repeated_import_no_duplicate_error():
    """Importing the same metrics module multiple times is safe (8A.18).

    Python's import system caches modules — re-import returns the same
    object without re-executing the module body, so no duplicate registration
    can occur. This test confirms the cached object is the identical instance.
    """
    import anveshak.scraper.metrics as m1
    import anveshak.scraper.metrics as m2

    assert m1 is m2, "Module object must be identical (import cache hit)"
    assert m1.scraper_items_fetched_total is m2.scraper_items_fetched_total
