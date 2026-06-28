"""Queue routing tests — verify jobs land in correct Redis sorted set.

Uses real Redis (not mocks). Enqueues test jobs to each service queue
and verifies they appear in the correct ARQ sorted set key.

This catches the exact class of bug where _queue_name is missing or wrong —
jobs silently go to a queue nobody listens on.

Tests:
  Q1-Q5: Each service queue receives enqueued jobs
  Q6: Wrong queue name → job NOT in target queue
"""
from __future__ import annotations

import pytest
from arq import create_pool
from arq.connections import RedisSettings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

REDIS_URL = "redis://localhost:6379"

# All 5 service queues
SERVICE_QUEUES = {
    "analyst": "arq:analyst",
    "scraper": "arq:scraper",
    "reporter": "arq:reporter",
    "vision": "arq:vision",
    "social": "arq:social",
}

# Test prefix to avoid colliding with real jobs
_TEST_PREFIX = "__queue_routing_test__"


@pytest.fixture
async def arq_pool():
    """Real ARQ Redis pool for queue routing tests."""
    try:
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    except Exception:
        pytest.skip("Redis not available — skipping queue routing tests")
    yield pool
    await pool.aclose()


@pytest.fixture(autouse=True)
async def cleanup_test_jobs(arq_pool):
    """Remove test jobs after each test to avoid pollution."""
    yield
    redis = arq_pool._redis if hasattr(arq_pool, "_redis") else arq_pool
    # Clean up any test job results
    async for key in redis.scan_iter(f"arq:result:*"):
        val = await redis.get(key)
        if val and _TEST_PREFIX.encode() in (val if isinstance(val, bytes) else b""):
            await redis.delete(key)
    # Drain test entries from queue sorted sets
    for qn in SERVICE_QUEUES.values():
        await redis.delete(f"{qn}:{_TEST_PREFIX}")


# ---------------------------------------------------------------------------
# Q1-Q5: Each queue receives its jobs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("service,queue_name", list(SERVICE_QUEUES.items()))
async def test_job_lands_in_correct_queue(arq_pool, service, queue_name):
    """Job enqueued with _queue_name=X must appear in Redis sorted set X."""
    redis = arq_pool._redis if hasattr(arq_pool, "_redis") else arq_pool

    # Record queue size before
    before = await redis.zcard(queue_name)

    # Enqueue a dummy job
    job = await arq_pool.enqueue_job(
        f"{_TEST_PREFIX}_{service}_probe",
        f"test-id-{service}",
        _queue_name=queue_name,
    )
    assert job is not None, f"enqueue_job returned None for {queue_name}"

    # Verify queue grew by 1
    after = await redis.zcard(queue_name)
    assert after == before + 1, (
        f"Queue {queue_name} should have grown by 1: "
        f"before={before}, after={after}"
    )

    # Cleanup: remove the test job from queue
    # ARQ stores job data as the sorted set member (msgpack-encoded)
    members = await redis.zrange(queue_name, -1, -1)
    if members:
        await redis.zrem(queue_name, members[-1])
    # Remove job result key
    await redis.delete(f"arq:result:{job.job_id}")


# ---------------------------------------------------------------------------
# Q6: Wrong queue name → job not in target queue
# ---------------------------------------------------------------------------

async def test_wrong_queue_job_not_in_target(arq_pool):
    """Job enqueued to wrong queue must NOT appear in the intended queue.

    This is the exact bug pattern: _queue_name="arq:queue" (default) but
    worker listens on "arq:social". Job sits in "arq:queue" forever.
    """
    redis = arq_pool._redis if hasattr(arq_pool, "_redis") else arq_pool
    wrong_queue = "arq:wrong_test_queue"
    target_queue = "arq:social"

    before = await redis.zcard(target_queue)

    # Enqueue to WRONG queue
    job = await arq_pool.enqueue_job(
        f"{_TEST_PREFIX}_wrong_queue_probe",
        "test-id-wrong",
        _queue_name=wrong_queue,
    )

    # Target queue should NOT have grown
    after = await redis.zcard(target_queue)
    assert after == before, (
        f"Job enqueued to {wrong_queue} should NOT appear in {target_queue}: "
        f"before={before}, after={after}"
    )

    # But wrong queue should have the job
    wrong_count = await redis.zcard(wrong_queue)
    assert wrong_count >= 1, (
        f"Job should be in {wrong_queue} (count={wrong_count})"
    )

    # Cleanup
    await redis.delete(wrong_queue)
    await redis.delete(f"arq:result:{job.job_id}")
