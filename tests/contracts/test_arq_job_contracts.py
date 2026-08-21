"""Contract tests — verify ARQ job enqueue calls match job function signatures.

If a service enqueues a job with wrong arguments, the job silently fails at
runtime. These tests catch that at test time using inspect.signature.

No external dependencies required — pure Python introspection.
"""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.contract


# ---------------------------------------------------------------------------
# Job function registry — maps job name to (module_path, function_name)
# ---------------------------------------------------------------------------

JOB_FUNCTIONS = {
    "analyse_content": ("anveshak.analyst.jobs", "analyse_content"),
    "run_clustering": ("anveshak.analyst.jobs", "run_clustering"),
    "generate_cluster_label": ("anveshak.analyst.jobs", "generate_cluster_label"),
    "run_cross_verification": ("anveshak.analyst.jobs", "run_cross_verification"),
    "backfill_topic_job": ("anveshak.analyst.jobs", "backfill_topic_job"),
    "generate_report": ("anveshak.reporter.worker", "generate_report"),
    "scrape_topic": ("anveshak.scraper.jobs", "scrape_topic"),
    "poll_rss_sources": ("anveshak.scraper.jobs", "poll_rss_sources"),
    "scrape_darkweb_topic": ("anveshak.scraper.jobs", "scrape_darkweb_topic"),
    "run_vision_analysis": ("anveshak.vision.jobs", "run_vision_analysis"),
}


def _get_job_func(module_path: str, func_name: str):
    """Import and return the job function."""
    import importlib

    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, func_name)
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Contract: every ARQ job function has (ctx: dict, ...) signature
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "job_name,module_func", list(JOB_FUNCTIONS.items()), ids=list(JOB_FUNCTIONS.keys())
)
def test_arq_job_has_ctx_first_param(job_name, module_func):
    """Every ARQ job function must accept ctx as first parameter."""
    module_path, func_name = module_func
    func = _get_job_func(module_path, func_name)
    if func is None:
        pytest.skip(f"Could not import {module_path}.{func_name}")

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    assert len(params) >= 1, f"{job_name}: no parameters"
    assert params[0] == "ctx", f"{job_name}: first param should be 'ctx', got '{params[0]}'"


@pytest.mark.parametrize(
    "job_name,module_func", list(JOB_FUNCTIONS.items()), ids=list(JOB_FUNCTIONS.keys())
)
def test_arq_job_is_async(job_name, module_func):
    """Every ARQ job function must be async."""
    module_path, func_name = module_func
    func = _get_job_func(module_path, func_name)
    if func is None:
        pytest.skip(f"Could not import {module_path}.{func_name}")

    assert inspect.iscoroutinefunction(func), f"{job_name}: must be async def, not plain def"


# ---------------------------------------------------------------------------
# Contract: job functions that take a single string ID after ctx
# ---------------------------------------------------------------------------

SINGLE_ID_JOBS = [
    "analyse_content",
    "generate_report",
    "scrape_topic",
    "poll_rss_sources",
    "scrape_darkweb_topic",
    "run_vision_analysis",
    "run_clustering",
    "generate_cluster_label",
    "run_cross_verification",
    "backfill_topic_job",
]


@pytest.mark.parametrize("job_name", SINGLE_ID_JOBS)
def test_single_id_job_accepts_string_after_ctx(job_name):
    """Jobs that take a single entity ID must accept (ctx, id: str)."""
    module_path, func_name = JOB_FUNCTIONS[job_name]
    func = _get_job_func(module_path, func_name)
    if func is None:
        pytest.skip(f"Could not import {module_path}.{func_name}")

    sig = inspect.signature(func)
    params = list(sig.parameters.items())
    assert len(params) >= 2, (
        f"{job_name}: must have at least 2 params (ctx + id), got {len(params)}"
    )
    second_name, second_param = params[1]
    # Verify the second parameter accepts a string
    annotation = second_param.annotation
    if annotation != inspect.Parameter.empty:
        # With `from __future__ import annotations`, annotation is a string "str"
        assert annotation in (str, "str"), (
            f"{job_name}: second param '{second_name}' should be str, got {annotation}"
        )


# ---------------------------------------------------------------------------
# Contract: poll_social_topic has include_x parameter
# ---------------------------------------------------------------------------


def test_poll_social_topic_has_include_x():
    """poll_social_topic must accept include_x keyword argument."""
    try:
        from anveshak.social.jobs import poll_social_topic
    except ImportError:
        pytest.skip("Cannot import poll_social_topic")

    sig = inspect.signature(poll_social_topic)
    params = sig.parameters
    assert "include_x" in params, (
        f"poll_social_topic must accept 'include_x' kwarg, got params: {list(params.keys())}"
    )
    # Must have a default value (callers may omit it)
    assert params["include_x"].default is not inspect.Parameter.empty, (
        "include_x must have a default value"
    )
