"""Report audiences and their action sets - issue #57.

A report is addressed to a service, and the service decides what an action
means. A state police cyber cell files an FIR and requests a CDR. A domestic
intelligence consumer has neither power: its output is an assessment for a
decision maker, so an action telling it to file an FIR is mis-framed in the
first line an officer reads.

The action sets therefore live in a versioned file the customer owns, keyed by
audience and then by matched template, rather than in a module-level dict here.
Adding an audience is a file change. Nothing in this module knows an audience
or a template by name.

Two refusals are deliberate. An unrecognised audience resolves to nothing, and
an audience with no action set for a matched template produces no actions. In
both cases the reporter logs the reason rather than borrowing another
audience's set, because a silently borrowed prosecution step is the exact error
this module exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Optional, Union

import structlog
import yaml

from .settings import settings

log = structlog.get_logger(__name__)

# How a matched template's legal provisions are rendered for an audience.
LEGAL_OWN = "own"
LEGAL_ATTRIBUTED = "attributed"
LEGAL_OMITTED = "omitted"
LEGAL_MODES = frozenset({LEGAL_OWN, LEGAL_ATTRIBUTED, LEGAL_OMITTED})


class _DefaultAudience:
    """Marker for "resolve the configured default", distinct from "none applies".

    A caller that states no audience means "whatever this deployment is set to".
    An explicit None means an audience was stated and resolved to nothing, which
    yields no actions. Collapsing the two would make an unrecognised audience
    silently inherit the default's prosecution steps.
    """


DEFAULT_AUDIENCE: Final = _DefaultAudience()


@dataclass(frozen=True)
class ReportAudience:
    """One service a report can be addressed to."""

    id: str
    label: str
    actions_heading: str
    legal_provisions: str
    template_actions: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class AudienceConfig:
    version: int
    owner: str
    default_audience: str
    audiences: dict[str, ReportAudience]


# What a caller may pass for "which audience is this report for".
AudienceArg = Union[ReportAudience, None, _DefaultAudience]


def concrete_audience(audience: AudienceArg) -> Optional[ReportAudience]:
    """Resolve the default when no audience was stated, else pass it through."""
    if isinstance(audience, _DefaultAudience):
        return resolve_audience(None)
    return audience


def _resolve_config_path() -> Optional[Path]:
    """Find the action sets in the container or in a host checkout.

    Same lookup shape as the concern taxonomy and the credibility rubric:
    configured path, container mounts, then the repository root located by its
    uv.lock marker.
    """
    configured = Path(settings.report_audience_config_path)
    if configured.is_file():
        return configured

    # A checkout is located by its uv.lock marker. When the walk reaches the
    # filesystem root without finding one, there is no checkout, and
    # /infra/configs/... is not a fallback: it is whatever happens to be there.
    project_root: Optional[Path] = None
    candidate_root = Path(__file__).resolve().parent
    while candidate_root != candidate_root.parent:
        if (candidate_root / "uv.lock").exists():
            project_root = candidate_root
            break
        candidate_root = candidate_root.parent

    relative = Path("infra/configs/audiences/report_actions.yaml")
    candidates = [Path("/app") / relative, Path("/workspace") / relative]
    if project_root is not None:
        candidates.append(project_root / relative)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_audiences() -> AudienceConfig:
    """Read the versioned action sets.

    A missing, unreadable or malformed file logs the reason and yields no
    audiences, so a report still generates and says why it carries no actions.
    The actions block is additive to a report that is complete without it, and
    this file is hand-edited by the customer, so a typo must not wedge every
    report at generated_at IS NULL. A malformed entry is skipped, named in the
    log, and does not take the well-formed ones down with it.
    """
    resolved = _resolve_config_path()
    if resolved is None:
        log.warning(
            "reporter.audience_config_missing",
            path=settings.report_audience_config_path,
            reason="REPORT_AUDIENCE_CONFIG_PATH does not exist, reports carry no actions",
        )
        return AudienceConfig(version=0, owner="", default_audience="", audiences={})

    try:
        loaded = yaml.safe_load(resolved.read_text())
    except (yaml.YAMLError, OSError) as exc:
        log.error(
            "reporter.audience_config_unreadable",
            path=str(resolved),
            error=str(exc),
            reason="the action sets could not be parsed, reports carry no actions",
        )
        return AudienceConfig(version=0, owner="", default_audience="", audiences={})

    if not isinstance(loaded, dict):
        log.error(
            "reporter.audience_config_malformed",
            path=str(resolved),
            found=type(loaded).__name__,
            reason="the action sets must be a mapping, reports carry no actions",
        )
        return AudienceConfig(version=0, owner="", default_audience="", audiences={})

    raw: dict[str, Any] = loaded
    entries = raw.get("audiences") or []
    if not isinstance(entries, list):
        log.error(
            "reporter.audience_config_malformed",
            path=str(resolved),
            found=type(entries).__name__,
            reason="audiences must be a list of entries, reports carry no actions",
        )
        entries = []

    audiences: dict[str, ReportAudience] = {}
    for position, entry in enumerate(entries):
        parsed = _parse_audience(entry, position, str(resolved))
        if parsed is None:
            continue
        if parsed.id in audiences:
            # Copying an audience block to start a new one and forgetting to
            # change the id would otherwise replace the original's action set
            # with the copy's, and the load would still report both ids present.
            log.warning(
                "reporter.audience_duplicate_id",
                path=str(resolved),
                audience=parsed.id,
                position=position,
                reason="an id appears twice, keeping the first and ignoring this one",
            )
            continue
        audiences[parsed.id] = parsed

    if audiences:
        log.info(
            "reporter.audience_config_loaded",
            version=raw.get("version", 0),
            audiences=sorted(audiences),
            path=str(resolved),
        )
    else:
        log.warning(
            "reporter.audience_config_empty",
            version=raw.get("version", 0),
            path=str(resolved),
            reason="the file defines no usable audience, so no report carries actions",
        )
    return AudienceConfig(
        version=_as_int(raw.get("version"), field="version", path=str(resolved)),
        owner=str(raw.get("owner", "")),
        default_audience=str(raw.get("default_audience", "")),
        audiences=audiences,
    )


def _as_int(value: Any, *, field: str, path: str) -> int:
    """Read an integer field, logging rather than raising on a bad one."""
    try:
        return int(value)
    except (TypeError, ValueError):
        log.warning(
            "reporter.audience_config_field_malformed",
            path=path,
            field=field,
            value=str(value),
            reason="not an integer, reading as 0",
        )
        return 0


def _parse_audience(entry: Any, position: int, path: str) -> Optional[ReportAudience]:
    """Build one audience from its file entry, or log why it was skipped.

    Skipping one entry rather than refusing the file keeps a typo in a new
    audience from removing the actions from every other audience's reports.
    """
    if not isinstance(entry, dict):
        log.warning(
            "reporter.audience_entry_skipped",
            path=path,
            position=position,
            found=type(entry).__name__,
            reason="an audience entry must be a mapping",
        )
        return None

    audience_id = entry.get("id")
    if not audience_id:
        log.warning(
            "reporter.audience_entry_skipped",
            path=path,
            position=position,
            reason="an audience entry must state an id",
        )
        return None
    audience_id = str(audience_id)

    templates = entry.get("templates") or {}
    if not isinstance(templates, dict):
        log.warning(
            "reporter.audience_templates_ignored",
            path=path,
            audience=audience_id,
            found=type(templates).__name__,
            reason="templates must be a mapping of template name to actions",
        )
        templates = {}

    legal_provisions = str(entry.get("legal_provisions", LEGAL_OWN))
    if legal_provisions not in LEGAL_MODES:
        # Deny by default. A typo here would otherwise print another agency's
        # sections as this reader's own, which is the mis-framing this module
        # exists to prevent, and it would look deliberate on the page.
        log.warning(
            "reporter.audience_legal_mode_unknown",
            path=path,
            audience=audience_id,
            value=legal_provisions,
            known=sorted(LEGAL_MODES),
            reason="unrecognised legal_provisions, omitting provisions for this audience",
        )
        legal_provisions = LEGAL_OMITTED

    return ReportAudience(
        id=audience_id,
        label=str(entry.get("label", audience_id)),
        actions_heading=str(entry.get("actions_heading", "Recommended Actions")),
        legal_provisions=legal_provisions,
        template_actions={
            str(template): tuple(str(action) for action in actions or [])
            for template, actions in templates.items()
        },
    )


def resolve_audience(audience_id: Optional[str]) -> Optional[ReportAudience]:
    """Return the audience a report is addressed to.

    An organisation that states no audience gets the configured default, which
    ships as the prosecution set so a deployment that predates this file reads
    exactly as it did. An organisation that states an audience the file does
    not define gets nothing, logged, rather than someone else's actions.
    """
    config = load_audiences()

    if not audience_id:
        default = config.audiences.get(config.default_audience)
        if default is None:
            log.warning(
                "reporter.audience_default_missing",
                default_audience=config.default_audience,
                reason="no audience stated and the configured default is not defined",
            )
            return None
        log.info(
            "reporter.audience_defaulted",
            audience=default.id,
            reason="the organisation states no report audience",
        )
        return default

    audience = config.audiences.get(audience_id)
    if audience is None:
        log.warning(
            "reporter.audience_unknown",
            audience=audience_id,
            known=sorted(config.audiences),
            reason="the organisation states an audience the action sets do not define",
        )
    return audience
