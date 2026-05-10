"""Dead-letter queue repository — store and retrieve failed ARQ job payloads.

When an ARQ job fails after max retries, the on_job_result callback
calls record_failed_job() to persist the failure for admin review.
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_FAILED_JOB = """
    INSERT INTO failed_jobs (
        id, job_id, function_name, args, error, queue_name,
        failed_at, labels
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (job_id) DO NOTHING
"""

SQL_LIST_FAILED_JOBS = """
    SELECT id, job_id, function_name, args, error, queue_name, failed_at
    FROM failed_jobs
    WHERE ($1::text IS NULL OR queue_name = $1)
    ORDER BY failed_at DESC
    LIMIT $2
"""

_LABELS_JSON = '{"classification":"OPEN","domain":"system","owner_org":"anveshak"}'

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


async def record_failed_job(
    conn: asyncpg.Connection,
    job_id: str,
    function_name: str,
    args: str,
    error: str,
    queue_name: str,
) -> None:
    """Insert a failed job into the dead-letter queue. Idempotent via ON CONFLICT."""
    await conn.execute(
        SQL_INSERT_FAILED_JOB,
        str(uuid.uuid4()),
        job_id,
        function_name,
        args,
        error,
        queue_name,
        datetime.now(UTC),
        _LABELS_JSON,
    )


async def list_failed_jobs(
    conn: asyncpg.Connection,
    queue_name: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List failed jobs, optionally filtered by queue_name."""
    rows = await conn.fetch(SQL_LIST_FAILED_JOBS, queue_name, limit)
    return [dict(r) for r in rows]
