# Contract Tests via Source Scanning

## Problem

Integration tests mock `enqueue_job` with AsyncMock — they verify the call happened
but never that a real worker picks it up. Queue name mismatches, missing function
registrations, and orphan queues go undetected.

5 queue name bugs shipped to production because unit tests mocked the boundary.

## Pattern

Source-scan contract tests — no infrastructure needed, runs in <1s:

1. Import all `WorkerSettings` → collect `{queue_name: [function_names]}` registry
2. Regex scan all `services/**/*.py` for `enqueue_job("name", ..., _queue_name="queue")`
3. Cross-reference: every enqueue target has a matching worker
4. Cross-reference: every worker has at least one enqueue caller
5. Verify: function names in enqueue match `WorkerSettings.functions` list
6. Scan for default queue usage (`arq:queue`) — always a bug

Key implementation details:
- Handle ARQ `Function` objects: `getattr(f, "__name__", None) or f.coroutine.__name__`
- Handle multi-line enqueue calls: search 8-line window after `enqueue_job(` for `_queue_name=`
- Skip docstrings/comments: toggle state on triple-quotes, skip `#` lines

## Where Used

`tests/contracts/test_service_contracts.py` — 6 tests, catches class of bugs
that mocked integration tests miss entirely.

## Lesson

**Test contracts, not components.** If service A writes to queue X and service B
reads from queue Y, both services pass their own tests but the system is broken.
Contract tests verify A's output matches B's input without running either service.
