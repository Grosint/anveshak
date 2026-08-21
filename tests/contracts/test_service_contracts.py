"""Service contract tests — verify cross-service wiring at the source level.

These tests catch mismatches between producers and consumers WITHOUT
running any infrastructure. Pure Python source scanning + import introspection.

Contracts verified:
  C1: Every enqueue_job _queue_name has a WorkerSettings that listens on it
  C2: Every WorkerSettings.queue_name has at least one enqueue caller
  C3: Every enqueue_job function name exists in target WorkerSettings.functions
  C4: No code uses the default ARQ queue ("arq:queue")
  C5: Job function names registered in WorkerSettings are importable
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

_SERVICES_DIR = Path(__file__).resolve().parents[2] / "services"

# ---------------------------------------------------------------------------
# Worker registry — single source of truth
# ---------------------------------------------------------------------------

WORKER_MODULES = {
    "analyst": "anveshak.analyst.jobs",
    "scraper": "anveshak.scraper.jobs",
    "reporter": "anveshak.reporter.worker",
    "vision": "anveshak.vision.jobs",
    "social": "anveshak.social.jobs",
}


def _load_worker_settings():
    """Import all WorkerSettings and return {queue_name: (service, functions_list)}."""
    workers = {}
    errors = []
    for service, module_path in WORKER_MODULES.items():
        try:
            mod = importlib.import_module(module_path)
            ws = getattr(mod, "WorkerSettings")
            qn = getattr(ws, "queue_name", None)
            funcs = getattr(ws, "functions", [])
            func_names = [
                getattr(f, "__name__", None)
                or getattr(f, "name", None)
                or (f.coroutine.__name__ if hasattr(f, "coroutine") else str(f))
                for f in funcs
            ]
            workers[qn or "arq:queue"] = {
                "service": service,
                "module": module_path,
                "functions": func_names,
            }
        except Exception as exc:
            errors.append(f"{service} ({module_path}): {type(exc).__name__}: {exc}")
    if errors:
        import warnings

        warnings.warn("Failed to import some WorkerSettings:\n" + "\n".join(errors))
    return workers


def _scan_enqueue_calls():
    """Scan all service Python files for enqueue_job calls.

    Returns list of {file, line, queue_name, function_name}.

    Uses the AST rather than line regexes: `ruff format` freely wraps a call
    across several lines, and a line-oriented scanner silently sees nothing
    when `enqueue_job(` and the job name land on different lines. Walking the
    AST also drops the need to track docstring and comment state by hand, and
    binds `_queue_name` to its own call instead of guessing from a line window.
    """
    results = []
    for py_file in sorted(_SERVICES_DIR.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(errors="ignore"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_enqueue = (isinstance(func, ast.Attribute) and func.attr == "enqueue_job") or (
                isinstance(func, ast.Name) and func.id == "enqueue_job"
            )
            if not is_enqueue:
                continue

            # Job name is the first positional arg. Skip dynamic names — the
            # contract can only be checked against a literal.
            if not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue

            queue_name = None
            for kw in node.keywords:
                if kw.arg == "_queue_name" and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, str):
                        queue_name = kw.value.value

            results.append(
                {
                    "file": str(py_file.relative_to(_SERVICES_DIR)),
                    "line": node.lineno,
                    "queue_name": queue_name,
                    "function_name": first.value,
                }
            )

    return results


# ---------------------------------------------------------------------------
# C1: Every enqueue target has a matching worker
# ---------------------------------------------------------------------------


class TestEnqueueTargetsMatchWorkers:
    """Every _queue_name used in enqueue_job must have a WorkerSettings listening."""

    def test_all_enqueue_targets_have_worker(self):
        workers = _load_worker_settings()
        enqueues = _scan_enqueue_calls()
        worker_queues = set(workers.keys())

        orphans = []
        for eq in enqueues:
            if eq["queue_name"] and eq["queue_name"] not in worker_queues:
                orphans.append(
                    f"{eq['file']}:{eq['line']}: "
                    f"enqueues to {eq['queue_name']!r} "
                    f"(function={eq['function_name']!r}) — no worker listens"
                )

        assert not orphans, "Jobs enqueued to queues with no worker:\n" + "\n".join(orphans)

    def test_all_enqueue_calls_specify_queue(self):
        """Every enqueue_job call must explicitly set _queue_name (no default)."""
        enqueues = _scan_enqueue_calls()

        missing = []
        for eq in enqueues:
            if eq["queue_name"] is None:
                missing.append(
                    f"{eq['file']}:{eq['line']}: "
                    f"enqueue_job({eq['function_name']!r}) "
                    f"missing _queue_name"
                )

        assert not missing, "enqueue_job calls without explicit _queue_name:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# C2: Every worker has at least one enqueue caller
# ---------------------------------------------------------------------------


class TestWorkersHaveCallers:
    """Every WorkerSettings.queue_name should have at least one enqueue caller."""

    def test_all_workers_have_enqueue_callers(self):
        workers = _load_worker_settings()
        enqueues = _scan_enqueue_calls()
        enqueue_targets = {eq["queue_name"] for eq in enqueues if eq["queue_name"]}

        # Exclude cron-only workers (they don't receive enqueued jobs from outside)
        # All our workers receive at least some enqueued jobs
        uncalled = set(workers.keys()) - enqueue_targets
        assert not uncalled, f"Workers listening on queues nobody enqueues to: {uncalled}"


# ---------------------------------------------------------------------------
# C3: Job function names in enqueue match WorkerSettings.functions
# ---------------------------------------------------------------------------


class TestFunctionNamesMatch:
    """Every function name in enqueue_job must be registered in target worker."""

    def test_enqueue_function_names_in_worker_functions(self):
        workers = _load_worker_settings()
        enqueues = _scan_enqueue_calls()

        mismatches = []
        for eq in enqueues:
            qn = eq["queue_name"]
            if not qn or qn not in workers:
                continue  # Covered by C1
            registered = workers[qn]["functions"]
            if eq["function_name"] not in registered:
                mismatches.append(
                    f"{eq['file']}:{eq['line']}: "
                    f"enqueues {eq['function_name']!r} to {qn} "
                    f"but worker only has: {registered}"
                )

        assert not mismatches, (
            "Jobs enqueued with function names not registered in worker:\n" + "\n".join(mismatches)
        )


# ---------------------------------------------------------------------------
# C4: No default queue usage
# ---------------------------------------------------------------------------


class TestNoDefaultQueue:
    """No code should use _queue_name='arq:queue' (ARQ default = bug)."""

    def test_no_default_queue_usage(self):
        pattern = re.compile(r"""_queue_name\s*=\s*['"]arq:queue['"]""")
        violations = []

        for py_file in _SERVICES_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    rel = py_file.relative_to(_SERVICES_DIR)
                    violations.append(f"{rel}:{i}: {line.strip()}")

        assert not violations, "Found _queue_name using default 'arq:queue':\n" + "\n".join(
            violations
        )


# ---------------------------------------------------------------------------
# C5: All WorkerSettings.functions are importable
# ---------------------------------------------------------------------------


class TestWorkerFunctionsImportable:
    """Every function listed in WorkerSettings.functions must be importable."""

    def test_all_registered_functions_exist(self):
        workers = _load_worker_settings()
        missing = []

        for qn, info in workers.items():
            mod = importlib.import_module(info["module"])
            ws = getattr(mod, "WorkerSettings")
            for func in ws.functions:
                # ARQ wraps functions in arq.Function objects — both are valid
                is_valid = (
                    callable(func)
                    or hasattr(func, "coroutine")  # arq.Function
                    or hasattr(func, "name")  # arq.Function
                )
                if not is_valid:
                    missing.append(
                        f"{info['service']}: {func!r} in WorkerSettings.functions "
                        f"is not a valid ARQ function"
                    )

        assert not missing, "Non-callable entries in WorkerSettings.functions:\n" + "\n".join(
            missing
        )


# ---------------------------------------------------------------------------
# C6: every ARQ worker is health-checked against its own heartbeat
# ---------------------------------------------------------------------------

_COMPOSE = Path(__file__).resolve().parents[2] / "infra" / "compose.yml"
_HEALTH_SCRIPT = Path(__file__).resolve().parents[2] / "sdk" / "arq_health.sh"


class TestWorkerHealthchecks:
    """A worker's container healthcheck must read that worker's ARQ health key.

    `kill -0 1` only proves PID 1 exists, which is exactly what let a wedged
    analyst worker report healthy for 40 minutes while its event loop was frozen.
    ARQ expires its health key after health_check_interval + 1 seconds, so key
    presence is the one liveness signal a frozen loop cannot fake.

    See docs/venv_rebuild_plan.md item 9.
    """

    def test_health_script_exists(self):
        """A typo'd path would make every healthcheck below fail closed at runtime."""
        assert _HEALTH_SCRIPT.exists(), _HEALTH_SCRIPT

    def test_every_worker_queue_has_a_healthcheck(self):
        """Each WorkerSettings.queue_name is named by a compose healthcheck."""
        workers = _load_worker_settings()
        compose = _COMPOSE.read_text()

        missing = [
            queue
            for queue in workers
            if f'"/workspace/sdk/arq_health.sh", "{queue}"' not in compose
        ]
        assert not missing, (
            f"queues with no arq_health.sh healthcheck in infra/compose.yml: {missing}. "
            f"A worker without one is only checked for PID 1 being alive."
        )

    def test_no_worker_uses_an_import_probe(self):
        """Only healthcheck `test:` lines are scanned, never the comments around them."""
        probes = [
            line.strip()
            for line in _COMPOSE.read_text().splitlines()
            if line.lstrip().startswith("test:")
        ]
        offenders = [p for p in probes if "python -c 'import anveshak" in p]
        assert not offenders, (
            f"an import-based healthcheck is back: {offenders}. Importing the job "
            f"graph pulls in crawl4ai and torch; it was measured at 17.9s against a "
            f"10s timeout and flapped the container to unhealthy on its own cost."
        )

    def test_every_worker_sets_health_check_interval(self):
        """ARQ defaults to 3600s, so an unset interval means an hour-long blind spot."""
        unset = []
        for service, module_path in WORKER_MODULES.items():
            mod = importlib.import_module(module_path)
            interval = getattr(mod.WorkerSettings, "health_check_interval", None)
            if interval is None or interval > 60:
                unset.append(f"{service}={interval}")
        assert not unset, (
            f"WorkerSettings without a short health_check_interval: {unset}. "
            f"The container healthcheck reads the key this writes, so the interval "
            f"is the detection window for a frozen event loop."
        )


# Compose service name -> module holding that scheduler's HEARTBEAT_NAME.
SCHEDULER_MODULES = {
    "scrape-web-scheduler": "anveshak.scraper.main",
    "scrape-social-scheduler": "anveshak.social.main",
}


class TestSchedulerHeartbeats:
    """The two schedulers are plain asyncio loops, not ARQ workers.

    Nothing wrote a health key for them, so their container healthcheck was
    `kill -0 1`, which is the check item 9 removed everywhere else. They now beat
    into `anveshak:scheduler:<name>:health-check` and are probed by the same
    shell script. See docs/venv_rebuild_plan.md.
    """

    def test_no_service_uses_kill_0_1(self):
        """The probe that cannot tell a wedged loop from a working one."""
        probes = [
            line.strip()
            for line in _COMPOSE.read_text().splitlines()
            if line.lstrip().startswith("test:")
        ]
        offenders = [p for p in probes if "kill -0 1" in p]
        assert not offenders, (
            f"a PID-1 healthcheck is back: {offenders}. It proves only that the "
            f"process exists, which a frozen event loop also does."
        )

    @pytest.mark.parametrize("service,module_path", sorted(SCHEDULER_MODULES.items()))
    def test_scheduler_healthcheck_matches_its_heartbeat_key(self, service, module_path):
        """A rename on either side leaves the probe reading a key nobody writes."""
        from anveshak.heartbeat import health_key

        mod = importlib.import_module(module_path)
        name = getattr(mod, "HEARTBEAT_NAME", None)
        assert name, f"{module_path} defines no HEARTBEAT_NAME"

        prefix = health_key(name).removesuffix(":health-check")
        compose = _COMPOSE.read_text()
        assert f'"/workspace/sdk/arq_health.sh", "{prefix}"' in compose, (
            f"{service} has no healthcheck reading {prefix}:health-check, the key "
            f"{module_path} writes."
        )

    @pytest.mark.parametrize("module_path", sorted(SCHEDULER_MODULES.values()))
    def test_scheduler_sleeps_with_a_heartbeat(self, module_path):
        """A bare asyncio.sleep between cycles lets the key expire mid-sleep."""
        source = Path(importlib.import_module(module_path).__file__).read_text()
        assert "sleep_with_heartbeat" in source, (
            f"{module_path} sleeps without refreshing its health key; the container "
            f"would report unhealthy while the loop is perfectly fine."
        )
