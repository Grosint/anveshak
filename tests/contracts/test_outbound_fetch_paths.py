"""Outbound fetches from untrusted addresses go through one guarded path (#55).

Scraped content chooses the addresses the scraper fetches, so a client built
with ``follow_redirects=True`` hands the choice of final host to whoever wrote
the link. ``anveshak.net.safe_fetch`` is the one place allowed to construct a
client for those paths: it walks the chain itself, revalidating each hop, and
connects to the address its guard approved.

This is a grep with a reason attached. It fails when a new fetch is added
outside the shared path, which is exactly when nobody remembers this rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

_REPO = Path(__file__).resolve().parents[2]

# Every module under these roots fetches addresses that scraped content named.
# services/api is here because source registration probes whatever URL it is
# handed, and discovery hands it addresses read out of scraped markup - from the
# process that holds the database credentials.
_GUARDED_ROOTS = (
    _REPO / "services" / "scraper",
    _REPO / "services" / "api" / "anveshak" / "api" / "routes" / "sources.py",
    _REPO / "sdk" / "anveshak" / "media",
)

# The shared path is where the redirect walk lives, so it is the one module
# that constructs a client and decides the redirect policy.
_FETCH_PATH = _REPO / "sdk" / "anveshak" / "net" / "safe_fetch.py"


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in _GUARDED_ROOTS:
        files.extend([root] if root.is_file() else sorted(root.rglob("*.py")))
    return files


def _client_constructions(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in {"AsyncClient", "Client"}:
            calls.append(node)
    return calls


def test_no_untrusted_fetch_path_builds_its_own_client():
    """A client built here bypasses the walk whatever its redirect policy says."""
    offenders = [
        f"{path.relative_to(_REPO)}:{call.lineno}"
        for path in _python_files()
        for call in _client_constructions(ast.parse(path.read_text(), filename=str(path)))
    ]

    assert offenders == [], (
        "these construct their own HTTP client, so the destination is judged once "
        f"at best; build them on anveshak.net.safe_fetch instead: {offenders}"
    )


def test_no_untrusted_fetch_path_follows_redirects_on_its_own():
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for call in _client_constructions(tree):
            for keyword in call.keywords:
                if keyword.arg != "follow_redirects":
                    continue
                if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    offenders.append(f"{path.relative_to(_REPO)}:{call.lineno}")

    assert offenders == [], (
        "these fetches let the client choose the final host; build them on "
        f"anveshak.net.safe_fetch instead: {offenders}"
    )


def test_the_shared_path_never_follows_redirects_implicitly():
    """The one module that may construct a client must still walk the chain itself."""
    tree = ast.parse(_FETCH_PATH.read_text(), filename=str(_FETCH_PATH))
    settings = [
        keyword.value.value
        for call in _client_constructions(tree)
        for keyword in call.keywords
        if keyword.arg == "follow_redirects" and isinstance(keyword.value, ast.Constant)
    ]
    source = _FETCH_PATH.read_text()

    assert '"follow_redirects": False' in source or False in settings, (
        "safe_fetch must disable client-side redirects, since it validates each hop itself"
    )
