# Anveshak — canonical ARQ job name constants + enqueue helper.
# Import these instead of using raw string literals in enqueue_job() calls.

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Job name constants — one source of truth for all ARQ job identifiers
# ---------------------------------------------------------------------------

# M2 — Scraper
JOB_SCRAPE_TOPIC = "scrape_topic"
JOB_BACKFILL_TOPIC = "backfill_topic_job"

# M3 — Social
JOB_POLL_SOCIAL_TOPIC = "poll_social_topic"

# M1/M2 — Analyst
JOB_ANALYSE_CONTENT = "analyse_content"
JOB_GENERATE_CLUSTER_LABEL = "generate_cluster_label"

# M4 — Vision
JOB_RUN_VISION_ANALYSIS = "run_vision_analysis"

# M5 — Reporter
JOB_GENERATE_REPORT = "generate_report"

# ---------------------------------------------------------------------------
# Enqueue helper — thin wrapper so callers don't hold an arq pool reference
# ---------------------------------------------------------------------------

async def enqueue(pool: Any, job_name: str, *args: Any, **kwargs: Any) -> Any:
    """Enqueue an ARQ job and return the job handle.

    Usage:
        from anveshak.jobs import enqueue, JOB_GENERATE_REPORT
        job = await enqueue(arq_pool, JOB_GENERATE_REPORT, report_id)
    """
    return await pool.enqueue_job(job_name, *args, **kwargs)
