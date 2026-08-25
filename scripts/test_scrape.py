"""Host-side orchestrator for source connectivity tests.

Copies test scripts into scraper and social containers, runs them via
docker exec, collects JSON results, and prints a colored summary table.

Usage:
    make test-scrape
    # or directly:
    uv run python scripts/test_scrape.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------

_RST = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_GRN = "\033[32m"
_YEL = "\033[33m"
_BLU = "\033[34m"
_CYN = "\033[36m"
_DIM = "\033[2m"

COMPOSE_CMD = [
    "docker",
    "compose",
    "--env-file",
    ".env",
    "-p",
    "anveshak",
    "-f",
    "infra/compose.yml",
]


def _run_docker_exec(container: str, script_path: str, timeout: int = 300) -> list[dict]:
    """Run a test script inside a container and parse JSON output."""
    cmd = ["docker", "exec", container, "python", script_path]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Parse JSON from stdout (stderr may have log output)
        stdout = result.stdout.strip()
        if not stdout:
            return [
                {
                    "type": "error",
                    "name": container,
                    "status": "FAIL",
                    "chars": 0,
                    "reason": f"No output. stderr: {result.stderr[-200:]}"
                    if result.stderr
                    else "No output",
                    "elapsed_s": 0,
                }
            ]

        # Find the JSON array in stdout (skip any log lines before it)
        json_start = stdout.rfind("[")
        if json_start == -1:
            return [
                {
                    "type": "error",
                    "name": container,
                    "status": "FAIL",
                    "chars": 0,
                    "reason": f"No JSON in output: {stdout[-200:]}",
                    "elapsed_s": 0,
                }
            ]

        return json.loads(stdout[json_start:])

    except subprocess.TimeoutExpired as exc:
        # The in-container scripts write `[progress] ...` to stderr precisely so a
        # killed run is diagnosable. TimeoutExpired carries what was read before
        # the kill, so report the last progress line rather than a bare timeout.
        captured = exc.stderr or b""
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", "replace")
        progress = [ln for ln in captured.splitlines() if ln.startswith("[progress]")]
        where = f", last: {progress[-1][len('[progress] ') :]}" if progress else ""
        return [
            {
                "type": "error",
                "name": container,
                "status": "FAIL",
                "chars": 0,
                "reason": f"Timeout ({timeout}s){where}",
                "elapsed_s": timeout,
            }
        ]
    except json.JSONDecodeError as exc:
        return [
            {
                "type": "error",
                "name": container,
                "status": "FAIL",
                "chars": 0,
                "reason": f"JSON parse error: {exc}",
                "elapsed_s": 0,
            }
        ]
    except Exception as exc:
        return [
            {
                "type": "error",
                "name": container,
                "status": "FAIL",
                "chars": 0,
                "reason": str(exc)[:120],
                "elapsed_s": 0,
            }
        ]


def _copy_script(service: str, local_path: str, remote_path: str) -> bool:
    """Copy a script into a running container."""
    cmd = COMPOSE_CMD + ["cp", local_path, f"{service}:{remote_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  {_RED}Failed to copy {local_path} to {service}:{remote_path}{_RST}")
        if result.stderr:
            print(f"  {_DIM}{result.stderr.strip()[:200]}{_RST}")
        return False
    return True


def _print_table(results: list[dict]) -> None:
    """Print a colored results table."""
    # Column widths
    type_w = 10
    name_w = 38
    status_w = 8
    chars_w = 8
    time_w = 7

    # Header
    print()
    print(
        f"  {_BOLD}{'TYPE':<{type_w}}  {'SOURCE':<{name_w}}  {'STATUS':<{status_w}}  "
        f"{'CHARS':>{chars_w}}  {'TIME':>{time_w}}  REASON{_RST}"
    )
    print(
        f"  {'─' * type_w}  {'─' * name_w}  {'─' * status_w}  "
        f"{'─' * chars_w}  {'─' * time_w}  {'─' * 30}"
    )

    for r in results:
        src_type = r.get("type", "?")
        name = r.get("name", "?")
        status = r.get("status", "?")
        chars = r.get("chars", 0)
        reason = r.get("reason", "")
        elapsed = r.get("elapsed_s", 0)

        # Truncate name if too long
        if len(name) > name_w:
            name = name[: name_w - 3] + "..."

        # Color status. SKIP is its own state: an adapter that is switched off has
        # not been tested, and calling that a failure makes a stock config red.
        if status == "PASS":
            status_str = f"{_GRN}✓ PASS{_RST}"
        elif status == "SKIP":
            status_str = f"{_DIM}- SKIP{_RST}"
        else:
            status_str = f"{_RED}✗ FAIL{_RST}"

        # Color type
        type_colors = {
            "rss": _CYN,
            "web": _BLU,
            "onion": _YEL,
            "telegram": _BLU,
            "x": _CYN,
            "reddit": _YEL,
            "error": _RED,
        }
        type_color = type_colors.get(src_type, "")
        type_str = f"{type_color}{src_type:<{type_w}}{_RST}"

        time_str = f"{elapsed:>{time_w - 1}.1f}s"

        print(
            f"  {type_str}  {name:<{name_w}}  {status_str:<{status_w + 9}}  "
            f"{chars:>{chars_w}}  {time_str}  {_DIM}{reason}{_RST}"
        )

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    failed = total - passed - skipped
    tested = total - skipped

    skip_note = f", {skipped} skipped" if skipped else ""
    print()
    if failed == 0:
        print(f"  {_GRN}{_BOLD}SUMMARY: {passed}/{tested} passed{skip_note}{_RST}")
    else:
        print(
            f"  {_YEL}{_BOLD}SUMMARY: {passed}/{tested} passed, "
            f"{failed}/{tested} failed{skip_note}{_RST}"
        )
    print()


def main() -> int:
    # Ensure we're in the project root
    if not os.path.exists("infra/compose.yml"):
        # Try going up
        if os.path.exists("../infra/compose.yml"):
            os.chdir("..")
        else:
            print(f"  {_RED}Error: Run from project root (where infra/compose.yml is){_RST}")
            return 1

    print(f"\n  {_DIM}Copying test scripts into containers...{_RST}")

    # Copy scripts into containers
    ok1 = _copy_script(
        "scrape-web-scheduler", "scripts/test_scrape_sources.py", "/tmp/test_scrape_sources.py"
    )
    ok2 = _copy_script(
        "scrape-social-scheduler", "scripts/test_scrape_social.py", "/tmp/test_scrape_social.py"
    )

    results: list[dict] = []

    # Run scraper tests (RSS, web, onion)
    if ok1:
        print(
            f"  {_DIM}Running scraper tests (RSS, web, onion) — this may take a few minutes...{_RST}"
        )
        # Measured end to end on 2026-08-21: 1330s, of which the ten RSS feeds are
        # 1128s. Live feeds are fetched at production's per-domain rate limit, so
        # this is inherent rather than a stall. At the old 600s budget the run was
        # killed mid-RSS every time and every partial result was discarded, which
        # is how a healthy scraper reported as one `Timeout (600s)` row.
        scraper_results = _run_docker_exec(
            "anveshak-scrape-web-scheduler-1",
            "/tmp/test_scrape_sources.py",
            timeout=1800,
        )
        results.extend(scraper_results)
    else:
        results.append(
            {
                "type": "error",
                "name": "scrape-web-scheduler container",
                "status": "FAIL",
                "chars": 0,
                "reason": "Failed to copy script",
                "elapsed_s": 0,
            }
        )

    # Run social tests (Telegram, X, Reddit)
    if ok2:
        print(f"  {_DIM}Running social tests (Telegram, X, Reddit)...{_RST}")
        social_results = _run_docker_exec(
            "anveshak-scrape-social-scheduler-1",
            "/tmp/test_scrape_social.py",
            timeout=120,
        )
        results.extend(social_results)
    else:
        results.append(
            {
                "type": "error",
                "name": "scrape-social-scheduler container",
                "status": "FAIL",
                "chars": 0,
                "reason": "Failed to copy script",
                "elapsed_s": 0,
            }
        )

    _print_table(results)

    # Exit code: 0 if nothing failed. A SKIP is a disabled adapter, not a failure.
    any_failed = any(r.get("status") == "FAIL" for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
