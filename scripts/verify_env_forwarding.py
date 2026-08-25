#!/usr/bin/env python3
"""Verify that every variable in .env.example reaches a container.

AGENTS.md, "Compose environment forwarding": every env var a service reads MUST
appear in that service's compose `environment:` block. A missing var does not
error. Pydantic falls back to the code default, so the feature silently runs on
a value nobody chose, and tuning `.env` does nothing while looking correct.

This checks the reverse direction, which is the one that bites: a variable
documented in `.env.example` that `infra/compose.yml` never references. Either
compose is missing the forward, or the variable is dead and should be deleted.

Both failures are reported separately, because the fixes are opposite:

  UNFORWARDED  a settings field or os.getenv() reader exists  -> add to compose
  DEAD         nothing in the tree reads it                   -> delete from .env*

Usage:
    python scripts/verify_env_forwarding.py
    make verify-env
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ENV_EXAMPLE = REPO_ROOT / ".env.example"
COMPOSE = REPO_ROOT / "infra" / "compose.yml"
SOURCE_ROOTS = (REPO_ROOT / "services", REPO_ROOT / "sdk")

# Variables that are deliberately not in compose.yml, with a reason each.
# Deny by default: anything not listed here must be forwarded or deleted.
EXEMPT_VARS: dict[str, str] = {
    # Consumed by the Makefile and helper scripts on the host, never inside a
    # container. Forwarding them would imply a service reads them, which is worse.
    "ANVESHAK_ALLOW_LIVE": "host-only guard for scripts/seed_demo.py --live",
    "COMPOSE_PROJECT_NAME": "read by the docker compose CLI itself, not by a service",
}

# Matches `FOO=` at the start of a line in a .env file.
_ENV_ASSIGN = re.compile(r"^([A-Z][A-Z0-9_]*)=")
# Matches `${FOO}` / `${FOO:-default}` interpolation in compose.
_COMPOSE_INTERP = re.compile(r"\$\{([A-Z][A-Z0-9_]*)")
# Matches a `FOO: value` key inside an indented compose environment block.
_COMPOSE_KEY = re.compile(r"^\s{4,}([A-Z][A-Z0-9_]*):", re.MULTILINE)
# Matches os.getenv("FOO") / os.environ["FOO"] / os.environ.get("FOO").
_OS_ENV = re.compile(r"os\.(?:getenv|environ(?:\.get)?)\(?\[?[\"']([A-Z][A-Z0-9_]*)[\"']")


def env_example_vars() -> dict[str, int]:
    """Return {VAR: line number} for every assignment in .env.example."""
    found: dict[str, int] = {}
    for lineno, line in enumerate(ENV_EXAMPLE.read_text().splitlines(), start=1):
        match = _ENV_ASSIGN.match(line.strip())
        if match:
            found.setdefault(match.group(1), lineno)
    return found


def compose_vars() -> set[str]:
    """Return every env var compose.yml interpolates or declares."""
    text = COMPOSE.read_text()
    return set(_COMPOSE_INTERP.findall(text)) | set(_COMPOSE_KEY.findall(text))


def settings_fields() -> set[str]:
    """Return the upper-cased name of every BaseSettings field in the tree.

    pydantic-settings maps a field `foo_bar` to the env var `FOO_BAR` under the
    empty env_prefix every settings class in this repo uses.
    """
    names: set[str] = set()
    for root in SOURCE_ROOTS:
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if not _is_settings_class(node):
                    continue
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        names.add(stmt.target.id.upper())
    return names


def _is_settings_class(node: ast.ClassDef) -> bool:
    """True if the class inherits from something named *Settings."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("Settings"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("Settings"):
            return True
    return False


def os_env_readers() -> set[str]:
    """Return every env var read directly via os.getenv/os.environ."""
    names: set[str] = set()
    for root in SOURCE_ROOTS:
        for path in root.rglob("*.py"):
            try:
                names.update(_OS_ENV.findall(path.read_text()))
            except UnicodeDecodeError:
                continue
    return names


def main() -> int:
    declared = env_example_vars()
    forwarded = compose_vars()
    readers = settings_fields() | os_env_readers()

    unforwarded: list[tuple[str, int]] = []
    dead: list[tuple[str, int]] = []

    for var, lineno in sorted(declared.items()):
        if var in forwarded or var in EXEMPT_VARS:
            continue
        (unforwarded if var in readers else dead).append((var, lineno))

    if not unforwarded and not dead:
        print(f"OK: all {len(declared)} .env.example vars are forwarded in infra/compose.yml")
        return 0

    if unforwarded:
        print(
            f"\nUNFORWARDED ({len(unforwarded)}) — a service reads these, compose never passes them."
        )
        print("The service silently uses its code default and .env has no effect.\n")
        for var, lineno in unforwarded:
            print(f"  {var}  (.env.example:{lineno})")
        print("\n  Fix: add to the environment: block of the service that reads it, as")
        print("       VAR: ${VAR:-<same default as settings.py>}")

    if dead:
        print(f"\nDEAD ({len(dead)}) — nothing in services/ or sdk/ reads these.")
        print("Tuning them does nothing but looks correct.\n")
        for var, lineno in dead:
            print(f"  {var}  (.env.example:{lineno})")
        print("\n  Fix: delete from .env and .env.example, or wire up a reader.")

    print(f"\nFAILED: {len(unforwarded) + len(dead)} of {len(declared)} vars unaccounted for")
    return 1


if __name__ == "__main__":
    sys.exit(main())
