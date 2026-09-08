"""Every SQL placeholder has an argument at its call site.

A renumbered placeholder without a renumbered call is an asyncpg
InterfaceError at runtime, not a test failure, unless something checks. This
has now happened twice on one branch, in two different modules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

MODULES = [
    Path("services/api/anveshak/api/db/actors.py"),
    Path("services/api/anveshak/api/db/candidates.py"),
    Path("services/api/anveshak/api/db/timeline.py"),
    Path("services/api/anveshak/api/db/concern.py"),
    Path("services/analyst/anveshak/analyst/detection.py"),
    Path("services/analyst/anveshak/analyst/manufactured.py"),
    Path("services/analyst/anveshak/analyst/mobilization.py"),
    Path("services/analyst/anveshak/analyst/stance.py"),
]


def _sql_constants(tree: ast.Module) -> dict[str, int]:
    """Module-level SQL constants mapped to their highest placeholder."""
    highest: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.startswith("SQL_"):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        placeholders = re.findall(r"\$(\d+)", node.value.value)
        if placeholders:
            highest[target.id] = max(int(p) for p in placeholders)
    return highest


def _calls(tree: ast.Module) -> list[tuple[str, int]]:
    """(constant name, argument count) for every fetch/execute call."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"fetch", "fetchrow", "fetchval", "execute", "executemany"}:
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        name = node.args[0].id
        if name.startswith("SQL_"):
            # First argument is the statement; the rest are its parameters.
            found.append((name, len(node.args) - 1))
    return found


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_every_placeholder_has_an_argument(path: Path):
    tree = ast.parse(path.read_text())
    highest = _sql_constants(tree)

    for name, arg_count in _calls(tree):
        if name not in highest:
            continue
        expected = highest[name]
        # executemany passes one sequence of parameter tuples, not the
        # parameters themselves.
        assert arg_count in (expected, 1), (
            f"{path.name}: {name} has ${expected} but its call passes {arg_count} arguments"
        )
