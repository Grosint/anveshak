"""The analyst worker's mem_limit must be sized for its max_jobs.

AGENTS.md requires an invariant test wherever two settings can defeat each
other, and this pair did exactly that in production: `mem_limit: 6g` shipped
alongside `ANALYST_MAX_JOBS=4`, and the worker was OOM-killed 12 times in 15
hours while every outward signal read healthy.

The failure is invisible without this test. Docker reports `exit=0
OOM=false`, because the kernel kills a worker process rather than PID 1;
`restart: unless-stopped` brings the container straight back; the ARQ
heartbeat resumes; and `failed_jobs` stays empty, because a SIGKILL cannot
write a dead letter row. Nothing but the VM's kernel log records it.

pytest.mark.unit — parses compose, no Docker, no containers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

COMPOSE = Path(__file__).resolve().parents[2] / "infra" / "compose.yml"

# Measured on the development deployment 2026-09-15, recorded in hardware.md
# under Re-measurement. The baseline is not the 1010 MiB the five resident
# models weigh: torch and glibc do not return freed inference activations to
# the OS, so a worker that has done work idles near 3 GiB and never falls back.
BASELINE_GIB = 3.0
# Peak anon-rss was 6.27 GB with two jobs running, over that baseline.
ACTIVATION_GIB_PER_JOB = 1.6


def _service_block(name: str) -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    start = text.index(f"\n  {name}:\n")
    # A service ends where the next two-space key begins.
    nxt = re.search(r"\n  [a-z][a-z0-9-]*:\n", text[start + 1 :])
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def _compose_default(block: str, pattern: str) -> str:
    """Read a compose value, unwrapping ${VAR:-default} to the default."""
    raw = re.search(pattern, block).group(1).strip()
    env = re.fullmatch(r"\$\{[A-Z_]+:-(.+)\}", raw)
    return env.group(1) if env else raw


def _gib(value: str) -> float:
    number, unit = float(value[:-1]), value[-1].lower()
    return number if unit == "g" else number / 1024


@pytest.fixture(scope="module")
def worker() -> dict:
    block = _service_block("analyse-worker")
    return {
        "mem_limit_gib": _gib(_compose_default(block, r"mem_limit:\s*(\S+)")),
        "max_jobs": int(_compose_default(block, r"ANALYST_MAX_JOBS:\s*(\S+)")),
    }


def test_mem_limit_covers_concurrent_activations(worker):
    """The invariant. Raise mem_limit, or lower ANALYST_MAX_JOBS, but never
    ship a pair where the peak does not fit."""
    required = BASELINE_GIB + ACTIVATION_GIB_PER_JOB * worker["max_jobs"]
    assert worker["mem_limit_gib"] >= required, (
        f"mem_limit {worker['mem_limit_gib']}g cannot hold "
        f"ANALYST_MAX_JOBS={worker['max_jobs']} "
        f"({BASELINE_GIB} GiB baseline + {ACTIVATION_GIB_PER_JOB} GiB/job "
        f"= {required} GiB). Raise mem_limit or lower ANALYST_MAX_JOBS. "
        "See hardware.md, Re-measurement 2026-09-15."
    )


def test_max_jobs_is_at_least_one(worker):
    """A zero would make the worker consume nothing while looking healthy,
    which is the same class of silent failure this file exists for."""
    assert worker["max_jobs"] >= 1


def test_the_invariant_rejects_the_combination_that_failed(worker):
    """Characterisation of the known bad pair, so the formula itself cannot be
    loosened until 6g/4 passes again."""
    required = BASELINE_GIB + ACTIVATION_GIB_PER_JOB * 4
    assert required > 6.0, "formula must still reject mem_limit=6g at max_jobs=4"


# ---------------------------------------------------------------------------
# The same invariant, against the local .env rather than the compose defaults
# ---------------------------------------------------------------------------
#
# The tests above read what is committed. They pass on a host whose own .env
# overrides both values into the failing pair, which is exactly what happened
# here: the compose default was 6g/4, the local .env set ANALYST_MAX_JOBS=2 to
# escape it, and 2 was still over. Checking only the committed values gives
# false confidence about the machine the worker actually runs on.
#
# Skipped rather than failed when there is no .env, because CI has none and a
# missing local override file is not a misconfiguration.

ENV_FILE = COMPOSE.parent.parent / ".env"


def _env_overrides() -> dict[str, str]:
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


@pytest.mark.skipif(not ENV_FILE.exists(), reason="no local .env to check")
def test_local_env_overrides_also_satisfy_the_invariant(worker):
    """A local override may lower both values together, never just one."""
    env = _env_overrides()
    mem_limit_gib = _gib(env.get("ANALYST_MEM_LIMIT", f"{worker['mem_limit_gib']:g}g"))
    max_jobs = int(env.get("ANALYST_MAX_JOBS", worker["max_jobs"]))

    required = BASELINE_GIB + ACTIVATION_GIB_PER_JOB * max_jobs
    assert mem_limit_gib >= required, (
        f".env sets ANALYST_MEM_LIMIT={mem_limit_gib}g with "
        f"ANALYST_MAX_JOBS={max_jobs}, which needs {required} GiB. "
        "Lower ANALYST_MAX_JOBS or raise ANALYST_MEM_LIMIT."
    )
