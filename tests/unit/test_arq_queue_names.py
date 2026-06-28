"""ARQ queue name consistency tests.

Every service worker MUST define an explicit queue_name.
Every enqueue_job() call MUST use _queue_name matching the target worker.
No service should rely on ARQ's default queue name.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Queue name constants — single source of truth
# ---------------------------------------------------------------------------

EXPECTED_QUEUES = {
    "analyst": "arq:analyst",
    "scraper": "arq:scraper",
    "reporter": "arq:reporter",
    "vision": "arq:vision",
    "social": "arq:social",
}


# ---------------------------------------------------------------------------
# Test: Every WorkerSettings has explicit queue_name
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestWorkerQueueNames:
    """Every ARQ WorkerSettings class must define an explicit queue_name."""

    @pytest.mark.parametrize("service,expected_queue", [
        ("analyst", "arq:analyst"),
        ("scraper", "arq:scraper"),
        ("reporter", "arq:reporter"),
        ("vision", "arq:vision"),
        ("social", "arq:social"),
    ])
    def test_worker_settings_has_explicit_queue_name(self, service, expected_queue):
        """WorkerSettings.queue_name must be explicitly set to the expected value."""
        # Map service to its WorkerSettings module
        module_map = {
            "analyst": "anveshak.analyst.jobs",
            "scraper": "anveshak.scraper.jobs",
            "reporter": "anveshak.reporter.worker",
            "vision": "anveshak.vision.jobs",
            "social": "anveshak.social.jobs",
        }
        mod = importlib.import_module(module_map[service])
        ws = getattr(mod, "WorkerSettings")
        assert hasattr(ws, "queue_name"), (
            f"{service} WorkerSettings missing queue_name attribute"
        )
        assert ws.queue_name == expected_queue, (
            f"{service} WorkerSettings.queue_name = {ws.queue_name!r}, "
            f"expected {expected_queue!r}"
        )


# ---------------------------------------------------------------------------
# Test: No enqueue_job uses the default ARQ queue
# ---------------------------------------------------------------------------

_DEFAULT_QUEUE = "arq:queue"
_SERVICES_DIR = Path(__file__).resolve().parents[2] / "services"


@pytest.mark.unit
class TestNoDefaultQueueUsage:
    """No enqueue_job call should target the default 'arq:queue'."""

    def test_no_enqueue_to_default_queue(self):
        """No Python file should contain _queue_name="arq:queue" (the default).

        Multi-line enqueue_job calls split _queue_name onto a separate line,
        so we scan for the string literal rather than requiring enqueue_job
        on the same line.
        """
        violations = []
        # Pattern: _queue_name="arq:queue" or _queue_name='arq:queue'
        pattern = re.compile(r"""_queue_name\s*=\s*['"]arq:queue['"]""")
        for py_file in _SERVICES_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    rel = py_file.relative_to(_SERVICES_DIR)
                    violations.append(f"{rel}:{i}: {line.strip()}")

        assert not violations, (
            f"Found _queue_name using default queue '{_DEFAULT_QUEUE}':\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Test: Social scheduler enqueues to arq:social
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSocialSchedulerQueue:
    """Social scheduler must enqueue poll_social_topic to arq:social."""

    def test_enqueue_topic_polls_uses_social_queue(self):
        """main.py enqueue_job('poll_social_topic') must use _queue_name='arq:social'."""
        main_path = _SERVICES_DIR / "social" / "anveshak" / "social" / "main.py"
        content = main_path.read_text()

        # Find lines with enqueue_job("poll_social_topic"
        poll_enqueues = [
            line.strip() for line in content.splitlines()
            if "enqueue_job" in line and "poll_social_topic" in line
        ]
        assert poll_enqueues, "No enqueue_job('poll_social_topic') found in social/main.py"

        for line in poll_enqueues:
            assert '_queue_name="arq:social"' in line or "_queue_name='arq:social'" in line, (
                f"poll_social_topic enqueue missing _queue_name='arq:social': {line}"
            )
