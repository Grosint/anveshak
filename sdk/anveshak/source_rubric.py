"""Structural Source credibility rubric - issue #51, ADR 0004.

Every Source used to be created at the same neutral score, so a corpus
spanning wire services, national outlets, party-affiliated publications,
anonymous partisan sites and fact-checkers treated all of them identically
and the credibility system demonstrated nothing.

This module computes the number a Source starts at. It is a sum of points
for structural properties of the outlet: whether editorial responsibility
is named and contactable, whether items carry authors, whether corrections
are published, whether ownership is disclosed. Every property is something
a reviewer can check by opening the outlet's own pages.

No property is a viewpoint. Two outlets with opposing politics and the same
structural properties get the same baseline, which is the claim the tests in
`tests/unit/test_source_rubric.py` exist to hold, and the claim an
evaluating officer is entitled to check.

Nothing here changes a score. Movement away from the baseline comes only
from behaviour observed in the platform, applied through the audited drop
and boost functions in `services/analyst/anveshak/analyst/credibility.py`,
so every change lands in `credibility_audit_log` (architectural rule 8).

The rubric itself is a versioned file the customer owns, and the per-outlet
assessments live in it rather than in code. Assessing an outlet is an
editorial act, and the agency accountable for it should be able to read and
edit the assessment without touching code.

It is read from a bind mount in development, so an edit applies on the next
restart, and from the image in production, so a deployed assessment is the
one reviewed at that tag. See ADR 0004.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

import structlog
import yaml

from .source_rubric_settings import SourceRubricSettings

log = structlog.get_logger(__name__)

# A credibility score is a percentage everywhere else in the system, and the
# column carries no CHECK constraint to catch a value that is not one.
SCORE_RANGE = (0.0, 100.0)

# What `changed_by` reads on an audit row a rubric wrote, whether at
# creation or when a baseline was applied to an existing Source. The prefix
# is what separates a structural baseline from a behavioural change in the
# audit log, and the re-run guard matches on it, so it is load-bearing
# rather than decorative.
CHANGED_BY_PREFIX = "rubric:source_credibility.v"

# The score an outlet meeting no criterion sits at, when the file states
# none. Neutral, and the same value a Source was created with before this
# rubric existed, so an undeclared outlet is unaffected by it.
NEUTRAL_BASELINE = 50.0


class RubricError(ValueError):
    """The rubric file cannot be used as written.

    Raised rather than logged and skipped. A rubric that quietly drops a
    property scores an outlet on fewer properties than the file says, and
    the resulting number still looks like a considered one.
    """


@dataclass(frozen=True)
class RubricCriterion:
    """One structural property, and what it is worth."""

    id: str
    label: str
    test: str
    points: float
    # Criteria that cannot be true of the same outlet, such as carrying
    # bylines and carrying none. Declared in the file rather than inferred
    # from the sign of the points, since two penalties can coexist.
    exclusive_with: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutletDeclaration:
    """The properties an outlet has been assessed as meeting."""

    handle: str
    name: str
    criteria_met: list[str]
    note: str = ""


@dataclass(frozen=True)
class SourceRubric:
    version: int
    owner: str
    baseline: float
    criteria: list[RubricCriterion]
    outlets: list[OutletDeclaration]

    @property
    def points_by_id(self) -> dict[str, float]:
        return {criterion.id: criterion.points for criterion in self.criteria}

    def baseline_for(self, criteria_met: Sequence[str]) -> float:
        """The score an outlet with these properties starts at.

        Pure, so the same properties produce the same number wherever it is
        computed, and order-independent, so a reviewer reordering the list
        in the file does not move a score.
        """
        points = self.points_by_id
        unknown = [name for name in criteria_met if name not in points]
        if unknown:
            raise RubricError(
                f"rubric v{self.version} has no criterion named {', '.join(sorted(unknown))}"
            )
        repeated = {name for name in criteria_met if list(criteria_met).count(name) > 1}
        if repeated:
            # A hand-edited file duplicates by copy-paste, and a property
            # counted twice produces a score nobody assessed while looking
            # like one that was.
            raise RubricError(
                f"rubric v{self.version}: {', '.join(sorted(repeated))} is listed more "
                "than once, so its points would be counted more than once"
            )
        conflict = self._conflicting(criteria_met)
        if conflict:
            raise RubricError(
                f"rubric v{self.version}: {conflict[0]} and {conflict[1]} contradict each "
                "other, so an outlet cannot meet both"
            )
        total = self.baseline + sum(points[name] for name in criteria_met)
        return clamp_score(total)

    def _conflicting(self, criteria_met: Sequence[str]) -> Optional[tuple[str, str]]:
        """The first pair of criteria that cannot both be true of one outlet.

        An outlet either carries bylines or it does not. A declaration
        naming both halves of a pair is a mistake, and the baseline it
        produces reads as a considered middle rather than as an error.
        """
        met = set(criteria_met)
        for criterion in self.criteria:
            for other in criterion.exclusive_with:
                if criterion.id in met and other in met:
                    return (criterion.id, other)
        return None

    def reason_for(self, declaration: OutletDeclaration) -> str:
        """The audit log reason for a baseline, naming its whole basis.

        An analyst answering a challenge to a score needs the properties it
        was built from, not the word "rubric".
        """
        met = ", ".join(declaration.criteria_met) if declaration.criteria_met else "no criterion"
        return (
            f"Structural baseline from source credibility rubric v{self.version}: "
            f"{met}. See docs/adr/0004-source-credibility-rubric.md."
        )


def rubric_changed_by(version: int) -> str:
    """The audit log author for a score written from rubric `version`."""
    return f"{CHANGED_BY_PREFIX}{version}"


def clamp_score(score: float) -> float:
    """Clamp a credibility score to the percentage range."""
    low, high = SCORE_RANGE
    return round(max(low, min(high, score)), 2)


def _resolve_rubric_path() -> Optional[Path]:
    """Find the rubric in a container or in a host checkout.

    Same lookup shape as the concern taxonomy and the mobilization lexicon:
    the configured path, then the two container mount points, then the
    repository root located by its uv.lock marker. Without the last one the
    file is invisible to a test run on a developer machine.
    """
    # Read at resolution time rather than at import, so a process that sets
    # the variable after importing this module still reads the file it named.
    configured = Path(SourceRubricSettings().source_rubric_path)
    if configured.is_file():
        return configured
    configured_missed = str(configured)

    project_root = Path(__file__).resolve().parent
    while project_root != project_root.parent:
        if (project_root / "uv.lock").exists():
            break
        project_root = project_root.parent

    relative = Path("infra/configs/credibility/source_rubric.yaml")
    for candidate in (
        Path("/app") / relative,
        Path("/workspace") / relative,
        project_root / relative,
    ):
        if candidate.is_file():
            log.warning(
                "source_rubric.configured_path_missing",
                configured=configured_missed,
                using=str(candidate),
                reason="SOURCE_RUBRIC_PATH does not exist, falling back to a shipped copy",
            )
            return candidate
    return None


@lru_cache(maxsize=1)
def load_rubric() -> SourceRubric:
    """Read and validate the versioned rubric file.

    Cached, since it is read once per process and does not change at
    runtime. A missing file logs the reason and yields an empty rubric, so
    every outlet reads as undeclared and Sources keep the neutral score
    they had before: the baseline is visibly unavailable rather than
    silently replaced by an invented number.

    A file that is present but wrong raises instead. An unreadable rubric is
    an operator error, and continuing on a partial one publishes scores
    nobody assessed.
    """
    resolved = _resolve_rubric_path()
    if resolved is None:
        log.warning(
            "source_rubric.missing",
            path=SourceRubricSettings().source_rubric_path,
            reason="SOURCE_RUBRIC_PATH does not exist, no structural baseline is applied",
        )
        return SourceRubric(version=0, owner="", baseline=NEUTRAL_BASELINE, criteria=[], outlets=[])

    try:
        return _read_rubric(resolved)
    except RubricError:
        raise
    except Exception as exc:
        raise RubricError(f"{resolved} cannot be read as a rubric: {exc}") from exc


def _read_rubric(resolved: Path) -> SourceRubric:
    raw = yaml.safe_load(resolved.read_text()) or {}
    if not isinstance(raw, dict):
        raise RubricError(f"{resolved} is not a mapping of rubric fields")
    criteria = [_parse_criterion(entry) for entry in raw.get("criteria", [])]
    known = {criterion.id for criterion in criteria}
    if len(known) != len(criteria):
        raise RubricError(f"{resolved}: two criteria share an id")

    outlets = [_parse_outlet(entry, known=known, path=resolved) for entry in raw.get("outlets", [])]
    handles = [outlet.handle for outlet in outlets]
    duplicates = {handle for handle in handles if handles.count(handle) > 1}
    if duplicates:
        raise RubricError(
            f"{resolved}: {', '.join(sorted(duplicates))} is declared more than once, "
            "so which assessment applies is an ordering accident"
        )

    rubric = SourceRubric(
        version=int(raw.get("version", 0)),
        owner=str(raw.get("owner", "")),
        baseline=float(raw.get("baseline", NEUTRAL_BASELINE)),
        criteria=criteria,
        outlets=outlets,
    )
    # Score every declaration now. A duplicated or contradictory property
    # would otherwise surface on the first Source that names that outlet,
    # which is a request failing rather than a file being wrong.
    for outlet in outlets:
        rubric.baseline_for(outlet.criteria_met)

    log.info(
        "source_rubric.loaded",
        version=rubric.version,
        criteria=len(criteria),
        outlets=len(outlets),
        path=str(resolved),
    )
    return rubric


def _parse_criterion(entry: Any) -> RubricCriterion:
    try:
        return RubricCriterion(
            id=str(entry["id"]),
            label=str(entry["label"]),
            test=str(entry["test"]),
            points=float(entry["points"]),
            exclusive_with=tuple(str(name) for name in entry.get("exclusive_with", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RubricError(f"criterion {entry!r} is incomplete: {exc}") from exc


def _parse_outlet(entry: Any, *, known: set[str], path: Path) -> OutletDeclaration:
    try:
        handle = str(entry["handle"])
        criteria_met = [str(name) for name in entry.get("criteria_met", [])]
    except (KeyError, TypeError) as exc:
        raise RubricError(f"{path}: outlet {entry!r} is incomplete: {exc}") from exc

    unknown = [name for name in criteria_met if name not in known]
    if unknown:
        raise RubricError(
            f"{path}: {handle} is declared as meeting {', '.join(sorted(unknown))}, "
            "which this rubric does not define"
        )
    return OutletDeclaration(
        handle=handle,
        name=str(entry.get("name", "")),
        criteria_met=criteria_met,
        note=str(entry.get("note", "")),
    )


def declaration_for(handle: str) -> Optional[OutletDeclaration]:
    """The assessment for an outlet, or None when nobody has assessed it."""
    for outlet in load_rubric().outlets:
        if outlet.handle == handle:
            return outlet
    return None


def baseline_for_handle(handle: str) -> Optional[float]:
    """The structural baseline for an outlet, or None when it is undeclared.

    None rather than the neutral baseline, so a caller can tell "assessed as
    ordinary" apart from "never assessed" and say which in its log.
    """
    declaration = declaration_for(handle)
    if declaration is None:
        return None
    return load_rubric().baseline_for(declaration.criteria_met)


def creation_score(
    handle: str, *, stated: Optional[float] = None
) -> tuple[float, str, Optional[OutletDeclaration]]:
    """The score a Source is created at, and the basis for it.

    One resolution point for every creation path: the API, the catalog
    approval route and the corpus importer. Each of them used to hardcode
    the neutral score, so an outlet assessed in the rubric got it only if it
    happened to arrive through the path that read the rubric.

    The basis is returned rather than left to be inferred, because a Source
    created at the neutral score because nobody assessed the outlet looks
    identical, on the row, to one assessed as thoroughly ordinary. The
    caller logs which happened.

    The declaration comes back with it, so a caller that logs or audits the
    properties behind a score does not scan the outlet list a second time.
    It is returned even when a stated score overrode it, because overriding
    an assessment that exists is worth saying out loud.
    """
    declaration = declaration_for(handle)
    if stated is not None:
        return clamp_score(stated), "stated", declaration

    if declaration is not None:
        return load_rubric().baseline_for(declaration.criteria_met), "rubric", declaration

    return NEUTRAL_BASELINE, "neutral", None
