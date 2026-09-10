"""No committed password or password hash - issue #41.

A demonstration account whose password lives in the repository is a shared
credential with no rotation story: every clone of the repository holds it, and
changing it means editing SQL. The demonstration seed therefore takes its
credentials from the environment, and this guard keeps it that way.

The scan globs every tracked text file and denies by default, so a new script
is covered the day it is added rather than the day someone remembers to list
it. Files that still carry a literal are named in KNOWN_SECRET_LITERALS
with a reason, following the EXEMPT_MODELS pattern in scripts/verify_labels.py.
That list is debt made visible; it must only ever shrink.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).relative_to(REPO_ROOT).as_posix()

SCANNED_SUFFIXES = {".py", ".sql", ".sh", ".yml", ".yaml", ".ts", ".tsx", ".md", ".example"}
SCANNED_NAMES = {"Makefile"}

# Built from parts so this file does not match its own guard.
BCRYPT_HASH = re.compile(r"\$2[aby]" + r"\$\d\d\$[./A-Za-z0-9]{53}")
DEMO_PASSWORD = re.compile("Anveshak" + r"[A-Za-z]*20\d\d!")

PATTERNS = (
    (BCRYPT_HASH, "a bcrypt password hash"),
    (DEMO_PASSWORD, "a demonstration password in clear text"),
)

# Agency demonstration seeds that still hard-code the shared demonstration
# password and its hash. Issue #41 scoped the fix to the demonstration seed and
# the scripts that log into it; each of these needs an account seeder of its
# own before it can be removed from this list.
KNOWN_SECRET_LITERALS = {
    "scripts/seed_demo_engine_c.sql": "#41 covered seed_demo.sql only; Engine C 4-agency scenarios",
    "scripts/seed_airforce_bengaluru_demo.sql": "#41 covered seed_demo.sql only; IAF scenario",
    "scripts/seed_bidadi_demo.sql": "#41 covered seed_demo.sql only; Bidadi scenario",
    "scripts/seed_ncb_demo.sql": "#41 covered seed_demo.sql only; NCB scenario",
    SELF: "the guard names the patterns it denies",
}


def _tracked_text_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = [Path(name) for name in listing.split("\0") if name]
    return [
        p
        for p in paths
        if (p.suffix in SCANNED_SUFFIXES or p.name in SCANNED_NAMES)
        and p.as_posix() not in KNOWN_SECRET_LITERALS
    ]


class TestNoCommittedCredentials:
    def test_tracked_files_carry_no_credential_literal(self) -> None:
        offenders: list[str] = []
        for relative in _tracked_text_files():
            try:
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for pattern, what in PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{relative.as_posix()} carries {what}")
        assert not offenders, "credential literals in tracked files: " + "; ".join(offenders)

    def test_the_demonstration_seed_is_guarded(self) -> None:
        # Guarding by glob is only meaningful if the file this issue fixed is
        # in the scanned set rather than quietly exempted.
        assert Path("scripts/seed_demo.sql") in _tracked_text_files()

    def test_exemptions_name_real_files_and_carry_a_reason(self) -> None:
        for name, reason in KNOWN_SECRET_LITERALS.items():
            assert (REPO_ROOT / name).exists(), f"exemption names a missing file: {name}"
            assert reason.strip(), f"exemption without a reason: {name}"

    def test_every_exemption_is_still_needed(self) -> None:
        # An exemption for a file that no longer carries a literal is a hole
        # left open. The list may only shrink.
        for name in KNOWN_SECRET_LITERALS:
            if name == SELF:
                continue
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            assert any(
                pattern.search(text) for pattern, _ in PATTERNS
            ), f"{name} carries no credential literal - remove it from the exemption list"

    def test_the_guard_would_catch_a_hash(self) -> None:
        # A pattern that matches nothing would pass this file silently.
        sample = "$2b" + "$12$" + "x" * 53
        assert BCRYPT_HASH.search(sample)


class TestDemonstrationCredentialsAreDeclared:
    def test_env_example_declares_every_demo_variable(self) -> None:
        from scripts.seed_demo_org import ACCOUNT_SLOTS

        example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for _role, username_var, _default, password_var in ACCOUNT_SLOTS:
            assert f"{username_var}=" in example, f"{username_var} missing from .env.example"
            assert f"{password_var}=" in example, f"{password_var} missing from .env.example"

    def test_env_example_carries_placeholders_only(self) -> None:
        from scripts.seed_demo_org import ACCOUNT_SLOTS

        example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for _role, _username_var, _default, password_var in ACCOUNT_SLOTS:
            line = next(ln for ln in example.splitlines() if ln.startswith(f"{password_var}="))
            assert line.split("=", 1)[1].startswith(
                "change-me"
            ), f"{password_var} in .env.example must be a placeholder"
