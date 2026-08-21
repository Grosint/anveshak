"""Every .env.example variable must reach a container that reads it.

pytest.mark.unit -- reads files only, no external dependencies.

AGENTS.md, "Compose environment forwarding": a var a service reads but compose
never passes does not error. Pydantic falls back to the code default, so the
feature runs on a value nobody chose and tuning `.env` looks correct while doing
nothing. This was how all eight CREDIBILITY_* knobs, both EMBEDDING_* knobs and
JWT_EXPIRE_MINUTES sat dead: declared in `.env.example`, absent from compose.

The same scanner backs `make verify-env`, so the gate and this test cannot drift.

See: learned/compose-environment-consistency.md, learned/compose-dead-env-var-cleanup.md
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_env_forwarding.py"


def _load_verifier():
    """Import the real script, so the test and `make verify-env` share one scanner."""
    spec = importlib.util.spec_from_file_location("verify_env_forwarding", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_env_forwarding"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
class TestEnvForwarding:
    def test_no_unforwarded_or_dead_vars(self):
        """No .env.example var is missing from compose or unread by any service."""
        verifier = _load_verifier()
        declared = verifier.env_example_vars()
        forwarded = verifier.compose_vars()
        readers = verifier.settings_fields() | verifier.os_env_readers()

        unforwarded = []
        dead = []
        for var in sorted(declared):
            if var in forwarded or var in verifier.EXEMPT_VARS:
                continue
            (unforwarded if var in readers else dead).append(var)

        assert not unforwarded, (
            f"{len(unforwarded)} vars are read by a service but never forwarded by "
            f"infra/compose.yml, so .env has no effect on them: {unforwarded}"
        )
        assert not dead, (
            f"{len(dead)} vars in .env.example are read by nothing in services/ or "
            f"sdk/. Delete them or wire up a reader: {dead}"
        )

    def test_every_exemption_carries_a_reason(self):
        """EXEMPT_VARS denies by default -- an exemption without a reason is a silent hole."""
        verifier = _load_verifier()
        for var, reason in verifier.EXEMPT_VARS.items():
            assert reason.strip(), f"EXEMPT_VARS['{var}'] has no reason"

    def test_scanner_finds_the_files_it_needs(self):
        """A path typo would make every check above pass vacuously."""
        verifier = _load_verifier()
        assert verifier.ENV_EXAMPLE.exists(), verifier.ENV_EXAMPLE
        assert verifier.COMPOSE.exists(), verifier.COMPOSE
        assert len(verifier.env_example_vars()) > 50, "suspiciously few vars parsed"
        assert len(verifier.compose_vars()) > 50, "suspiciously few compose refs parsed"
        assert len(verifier.settings_fields()) > 50, "suspiciously few settings fields parsed"


@pytest.mark.unit
class TestNoInlineCommentsOnNumericEnvVars:
    """Pydantic reads `PORT=8000 # api` as the string "8000 # api" and crashes.

    Compose strips the trailing comment, which is why this never fired in the
    containers, but anything reading `.env` directly gets the raw string.

    See: learned/dotenv-inline-comment-int-fields.md
    """

    def test_env_example_has_no_inline_comment_on_a_numeric_value(self):
        import re

        pattern = re.compile(r"^([A-Z][A-Z0-9_]*)=([0-9]+(?:\.[0-9]+)?)\s+#")
        offenders = [
            f"{lineno}: {line}"
            for lineno, line in enumerate(
                (REPO_ROOT / ".env.example").read_text().splitlines(), start=1
            )
            if pattern.match(line)
        ]
        assert not offenders, (
            "int/float env vars must not carry an inline comment; put it on the "
            f"line above: {offenders}"
        )
