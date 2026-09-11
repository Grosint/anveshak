"""The reference time a detection pass runs at. See ADR 0003.

Detection was written against the system clock, which made historic analysis
impossible in two directions at once. Capture Time set to the historic date
made every relative window exclude everything, so nothing fired. Capture Time
set to the import time made detection fire but dated every Signal the day of
the import, so an analyst navigating back to the day an event occurred found
nothing.

The fix is a parameter rather than a global. Every detection query and every
detection write takes a reference time that defaults to the current time, so
live behaviour is unchanged and the default path needs no flag.

The guard has one job: a Replay capability must not be reachable in a live
deployment. It does that with three properties, the same deny-by-default shape
as the cloud model guard.

1. ``VIRTUAL_CLOCK_ENABLED`` defaults to false, so an override raises unless
   someone set the flag deliberately.
2. An override is refused rather than ignored. Falling back to the wall clock
   would date a whole Replay stage the day it ran, which is the failure this
   module exists to prevent, arriving silently.
3. A naive timestamp is refused. A guessed zone moves a reference time across
   a day boundary, and a day is the unit an analyst reads.

Nothing here backdates a row after the fact. The reference time is supplied
when detection runs, and the row is written with it once.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from pydantic_settings import BaseSettings

log = structlog.get_logger(__name__)

_FLAG = "VIRTUAL_CLOCK_ENABLED"
_ALLOWLIST = "VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS"


class ClockOverrideRefusedError(RuntimeError):
    """A reference time was supplied where the override is not permitted."""


class ClockSettings(BaseSettings):
    """Clock configuration. Off by default, and refused outside the allowlist."""

    # Matches the ENVIRONMENT variable the logging setup already reads.
    environment: str = "production"

    virtual_clock_enabled: bool = False

    # Environments where the override is permitted at all. An allowlist, never
    # a denylist, for the reason ADR 0002 gives: "prod", "staging", "preprod"
    # and "prod-dr" are all environments a denylist of "production" would have
    # let through. One flag is one layer, and a Replay flag copied into a
    # production .env would then be the whole gate.
    virtual_clock_allowed_environments: list[str] = ["development", "test", "local", "replay"]

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


def _refusal_reason(settings: ClockSettings) -> str | None:
    """Return why the override is refused, or None when it is permitted.

    Deny by default at every step.
    """
    if not settings.virtual_clock_enabled:
        return (
            f"A reference time was supplied but {_FLAG} is false. Backdating "
            "detection output is a Replay capability and is not reachable in a "
            "live deployment. See docs/adr/0003-virtual-clock.md."
        )
    environment = settings.environment.strip().lower()
    allowed = {name.strip().lower() for name in settings.virtual_clock_allowed_environments}
    if environment not in allowed:
        return (
            f"{_FLAG} is true in environment {environment!r}, which is not in "
            f"{_ALLOWLIST}. A Replay runs on a dedicated deployment; a live one "
            "never dates its own output by hand."
        )
    return None


def resolve_reference_time(
    reference_time: datetime | None = None,
    *,
    settings: ClockSettings | None = None,
) -> datetime:
    """Return the time detection should treat as now, in UTC.

    Args:
        reference_time: explicit reference time, or None for the wall clock.
        settings: injected for tests. Read from the environment otherwise.

    Raises:
        ClockOverrideRefusedError: a reference time was supplied while the
            override is not permitted, or it carried no timezone, or it lies
            in the future.
    """
    if reference_time is None:
        return datetime.now(UTC)

    resolved_settings = settings if settings is not None else ClockSettings()
    reason = _refusal_reason(resolved_settings)
    if reason is not None:
        raise ClockOverrideRefusedError(reason)

    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ClockOverrideRefusedError(
            f"Reference time {reference_time.isoformat()} is naive. A guessed "
            "zone moves the reference across a day boundary, and a day is the "
            "unit an analyst reads. Supply an explicit offset."
        )

    resolved = reference_time.astimezone(UTC)
    if resolved > datetime.now(UTC):
        # A Replay runs over history. A reference time in the future is a
        # typo, and it would outlive its own mistake: a report dated ahead of
        # now keeps matching every "since NOW() - interval" query forever.
        raise ClockOverrideRefusedError(
            f"Reference time {resolved.isoformat()} is in the future. A Replay "
            "runs at a moment that has already happened."
        )

    log.info(
        "clock.reference_time_override",
        reference_time=resolved.isoformat(),
        reason=f"{_FLAG} is true, so detection runs at a simulated time",
    )
    return resolved


def parse_reference_time(
    raw: str | datetime | None,
    *,
    settings: ClockSettings | None = None,
) -> datetime | None:
    """Parse a reference time carried as an ARQ job argument.

    Returns None for None, so a job invoked without one takes the live path.

    A parsed value is put through :func:`resolve_reference_time` before it is
    returned, so the guard runs at the job boundary as well as at the entry
    point it is handed to. Parsing that only validated the string shape would
    hand an unguarded datetime to whatever called it next, and the guard would
    then hold only while every caller remembered it.

    Raises:
        ClockOverrideRefusedError: the value is not an ISO-8601 timestamp with
            an offset, or the override is not permitted here. Never falls back
            to the wall clock, because a Replay stage that silently ran live
            would date every Signal the day of the run.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        parsed = raw
    else:
        try:
            parsed = datetime.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise ClockOverrideRefusedError(
                f"Reference time {raw!r} is not an ISO-8601 timestamp: {exc}"
            ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ClockOverrideRefusedError(
            f"Reference time {raw!r} carries no timezone offset. Supply one, "
            "such as 2026-05-16T09:30:00+05:30."
        )
    return resolve_reference_time(parsed, settings=settings)


def describe_clock(settings: ClockSettings) -> dict[str, object]:
    """Describe the resolved clock for a startup log line.

    Never raises, because startup disclosure must survive a configuration that
    :func:`resolve_reference_time` refuses.
    """
    if not settings.virtual_clock_enabled:
        return {
            "clock": "system",
            "reason": f"{_FLAG} is not set, so detection runs at the system clock",
        }
    reason = _refusal_reason(settings)
    if reason is not None:
        return {"clock": "refused", "reason": reason}
    return {
        "clock": "virtual",
        "reason": f"{_FLAG} is set in environment {settings.environment!r}, so a "
        "Replay may run detection at a past moment",
    }


def live_detection_suspended(settings: ClockSettings | None = None) -> str | None:
    """Why a wall-clock detection pass must not run here, or None.

    A deployment where a Replay can actually run writes detection rows dated
    months ago. A live pass beside it writes rows dated today, and the two
    corrupt each other silently.

    The Signal dedup window is measured back from the pass's reference time and
    has no upper bound, so one Signal fired today suppresses every stage Signal
    for that cluster for the rest of the Replay. The Candidate Topic
    persistence gate counts detection passes, so a live hourly pass promotes a
    narrative the Replay's own stages never promoted. And a re-run after a reset
    stops reproducing the first run, because the number of live passes that
    landed between stages is a function of how long the operator took.

    The same shape as the archival suspension ADR 0003 describes, for the same
    reason: staleness and dedup are both wall-clock judgements about rows that
    no longer carry wall-clock dates.

    The test is the same one a Replay itself has to pass, both layers, not the
    flag alone. A host with the flag set in an environment off the allowlist
    refuses every override, so no Replay can run there and there is nothing to
    protect; suspending live detection there would stop a production pipeline
    over a stray flag and leave one INFO line to explain it.
    """
    try:
        resolved = settings if settings is not None else ClockSettings()
    except Exception as exc:
        # A malformed clock configuration refuses every override too, so no
        # Replay can be running here either. Stay live and say so, rather than
        # stopping detection over a value nobody can act on from a log line.
        log.warning(
            "clock.settings_unreadable",
            error=str(exc),
            reason="live detection continues, since no Replay can run on this configuration",
        )
        return None

    if describe_clock(resolved)["clock"] != "virtual":
        return None
    return (
        f"{_FLAG} is true in environment {resolved.environment!r}, so this "
        "deployment can write backdated detection output and a Replay may be "
        "running. A wall-clock pass would date its rows today, and the Signal "
        "dedup window a Replay stage measures back from a past reference time "
        "would then suppress that stage's Signals. "
        "See docs/adr/0003-virtual-clock.md and docs/replay.md."
    )


def log_clock_startup(settings: ClockSettings, service: str) -> None:
    """Log which clock is in use and why, at INFO, at startup.

    A capability that can date a Signal to a day it was not produced on
    discloses itself before it is used, not only when it is. So does the
    consequence: on a Replay host every wall-clock detection pass is off, and
    an analyst seeing no Signals needs that stated rather than inferred.
    """
    log.info(
        "clock.mode_selected",
        service=service,
        live_detection="suspended" if live_detection_suspended(settings) else "running",
        **describe_clock(settings),
    )
