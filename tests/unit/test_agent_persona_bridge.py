"""Personas are discoverable through one mechanism - issue #53.

Personas are authored harness-agnostically in `.agents/personas/` and reach
Claude Code only through a per-persona symlink under `.claude/agents/`. A
persona written without its symlink is invisible to the harness that is meant
to invoke it, and a symlink whose frontmatter name disagrees with its filename
is invoked under a name nobody types.

Both failures are silent: the review lens simply never runs. This test is the
check the issue asks for, that a new persona is discoverable by exactly the
same mechanism as the existing ones, rather than by whoever remembers the
symlink.

`make agents-check` asserts the same two properties for a reader who is not
running pytest, and deliberately duplicates them: it is the gate Codex and
Cursor users run, and nothing in `make test-ci` invokes it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_DIR = REPO_ROOT / ".agents" / "personas"
AGENT_DIR = REPO_ROOT / ".claude" / "agents"

# Every persona is a review lens, so every persona states what it reviews.
LENS_MARKER = "Review the proposal covering:"

NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)

# A description is what the harness routes an invocation on, so a one-word
# placeholder is worse than no persona: it is a lens nothing ever selects. The
# shortest of the existing eight is well over this.
MIN_DESCRIPTION_CHARS = 40


def _personas() -> list[Path]:
    return sorted(PERSONA_DIR.glob("persona-*.md"))


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: no frontmatter block"
    end = text.index("\n---", 4)
    return text[4:end]


def test_personas_exist() -> None:
    assert _personas(), f"no personas found under {PERSONA_DIR}"


def test_intelligence_bureau_persona_exists() -> None:
    """Issue #53: the review lenses carried no domestic intelligence audience."""
    assert (PERSONA_DIR / "persona-ib.md").is_file()


@pytest.mark.parametrize("persona", _personas(), ids=lambda p: p.stem)
def test_persona_is_symlinked_into_claude_agents(persona: Path) -> None:
    link = AGENT_DIR / persona.name
    assert link.is_symlink(), f"{persona.name} is not symlinked into .claude/agents"
    assert link.resolve() == persona.resolve(), (
        f"{persona.name} symlink points at {link.resolve()}, not at the persona"
    )


@pytest.mark.parametrize("persona", _personas(), ids=lambda p: p.stem)
def test_persona_frontmatter_matches_filename(persona: Path) -> None:
    frontmatter = _frontmatter(persona)
    name = NAME_RE.search(frontmatter)
    assert name is not None, f"{persona.name}: frontmatter has no name field"
    assert name.group(1) == persona.stem, (
        f"{persona.name}: frontmatter name is {name.group(1)}, expected {persona.stem}"
    )

    description = DESCRIPTION_RE.search(frontmatter)
    assert description is not None, f"{persona.name}: frontmatter has no description"
    assert len(description.group(1).strip(' "')) > MIN_DESCRIPTION_CHARS, (
        f"{persona.name}: description is too short to route an invocation on"
    )


@pytest.mark.parametrize("persona", _personas(), ids=lambda p: p.stem)
def test_persona_states_what_it_reviews(persona: Path) -> None:
    assert LENS_MARKER in persona.read_text(encoding="utf-8"), (
        f"{persona.name}: missing '{LENS_MARKER}', so it is a description rather than a lens"
    )


def test_no_persona_symlink_without_a_persona() -> None:
    stale = [
        link.name
        for link in sorted(AGENT_DIR.glob("persona-*.md"))
        if not (PERSONA_DIR / link.name).is_file()
    ]
    assert stale == [], f"stale persona symlinks in .claude/agents: {stale}"


def test_personas_are_not_git_ignored() -> None:
    """A blanket ignore on .agents/ excludes every new persona, silently.

    The tracked personas keep working, because git never stops tracking a file
    it already tracks, so the rule looks harmless on a machine that has them.
    A persona added afterwards is simply never committed, and the harness that
    was meant to invoke it never sees it. This is the blanket-pattern trap in
    the git-build skill, applied to agent configuration rather than to a
    Python package.
    """
    ignored = subprocess.run(
        ["git", "check-ignore", *(str(p) for p in _personas())],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    assert ignored == [], f"personas excluded by .gitignore: {ignored}"
