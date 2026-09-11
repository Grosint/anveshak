"""Apply the structural credibility baseline to existing Sources - issue #51.

A Source created before the rubric existed, or before its outlet was
assessed, sits at the neutral score. This script gives it the baseline the
rubric computes, through the same audited pair of statements the analyst
service writes: the score never moves without a row in
credibility_audit_log (architectural rule 8), and the row names the rubric
version and every property the baseline was built from, so an analyst
challenged on a score can answer with its basis rather than with the word
"rubric".

What it deliberately does not do
--------------------------------

It does not touch a Source whose baseline has already been applied. Once a
baseline is set, movement comes only from behaviour this platform observed,
through the audited drop and boost passes. A second run that reset every
score to its structural number would erase that, and would erase it
silently, since the audit row would read like an ordinary rubric
application. `--rebaseline` overrides that, for the case where the rubric
itself changed, and says so in the reason it writes.

It writes nothing without `--apply`. The default run prints what it would
do, because publishing credibility scores to a customer is not something to
discover after the fact.

Usage
-----

    POSTGRES_URL=... uv run python -m scripts.apply_source_rubric
    POSTGRES_URL=... uv run python -m scripts.apply_source_rubric --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

import asyncpg
import structlog
from anveshak.source_rubric import CHANGED_BY_PREFIX, load_rubric, rubric_changed_by

log = structlog.get_logger(__name__)

# Re-exported from the SDK, where the API creation path reads it too. A
# second copy of the prefix would let the two drift, and the re-run guard
# would stop recognising rows the other path wrote.
__all__ = ["CHANGED_BY_PREFIX", "apply_rubric", "changed_by", "decide"]

# Below this, the two scores are the same number and an audit row would say
# nothing. Credibility is stored to two decimal places.
EPSILON = 0.01

_LABELS_JSON = json.dumps({"classification": "OPEN", "domain": "osint"})

# ---------------------------------------------------------------------------
# SQL - module-level constants
# ---------------------------------------------------------------------------

SQL_FIND_SOURCE = """
    SELECT id, name, credibility_score, org_id
    FROM sources
    WHERE url_or_handle = $1
      AND ($2::text IS NULL OR org_id = $2)
"""

# left(...) rather than LIKE: the prefix contains three underscores, each a
# single-character wildcard in LIKE, so a LIKE on it also matches a
# neighbouring author string and reads the Source as already baselined.
SQL_COUNT_RUBRIC_ROWS = """
    SELECT COUNT(*) AS applied
    FROM credibility_audit_log
    WHERE source_id = $1 AND left(changed_by, $2) = $3
"""

SQL_UPDATE_SOURCE_SCORE = """
    UPDATE sources SET credibility_score = $1, updated_at = $2 WHERE id = $3
"""

SQL_INSERT_AUDIT_LOG = """
    INSERT INTO credibility_audit_log (
        id, source_id, old_score, new_score, reason, changed_by, created_at, labels, org_id
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
"""


def changed_by(version: int) -> str:
    """The audit log author for a baseline written from rubric `version`."""
    return rubric_changed_by(version)


@dataclass(frozen=True)
class Decision:
    apply: bool
    reason_skipped: str = ""


def decide(
    *,
    old_score: float,
    new_score: float,
    already_baselined: bool,
    rebaseline: bool = False,
) -> Decision:
    """Whether this Source's score should change, and why not when it should not.

    Pure, because the cases that matter are the refusals: a Source that
    behaviour has moved away from its baseline, and a Source already sitting
    on it.
    """
    if already_baselined and not rebaseline:
        return Decision(
            apply=False,
            reason_skipped=(
                "a baseline was already applied and behaviour may have moved the score "
                "since; pass --rebaseline to set it again"
            ),
        )
    if abs(new_score - old_score) < EPSILON:
        return Decision(apply=False, reason_skipped="already at its structural baseline")
    return Decision(apply=True)


@dataclass(frozen=True)
class Outcome:
    handle: str
    name: str
    old_score: Optional[float]
    new_score: Optional[float]
    status: str
    detail: str = ""


async def apply_rubric(
    pool: asyncpg.Pool,
    *,
    apply_changes: bool,
    rebaseline: bool,
    org_id: Optional[str] = None,
) -> list[Outcome]:
    """Walk every declared outlet and set the Sources it names to its baseline.

    A Source is a global entity, so one handle can carry a score several
    organisations see through org_sources, while the audit row lands under
    the organisation that owns the row and that table is RLS-protected.
    `org_id` scopes a run for that reason. The default walks every
    organisation, which is right for a single-tenant deployment and is
    stated rather than assumed.
    """
    rubric = load_rubric()
    if not rubric.outlets:
        log.info(
            "source_rubric.no_outlets_declared",
            version=rubric.version,
            reason="the rubric declares no outlet, so there is no baseline to apply",
        )
        return []

    now = datetime.now(UTC)
    author = changed_by(rubric.version)
    outcomes: list[Outcome] = []

    async with pool.acquire() as conn:
        for declaration in rubric.outlets:
            baseline = rubric.baseline_for(declaration.criteria_met)
            rows = await conn.fetch(SQL_FIND_SOURCE, declaration.handle, org_id)
            if not rows:
                outcomes.append(
                    Outcome(
                        handle=declaration.handle,
                        name=declaration.name,
                        old_score=None,
                        new_score=baseline,
                        status="no_source",
                        detail=(
                            "the rubric declares this outlet, no Source in this "
                            "organisation uses that handle"
                            if org_id
                            else "the rubric declares this outlet, no Source uses that handle"
                        ),
                    )
                )
                continue

            for row in rows:
                applied_before = await conn.fetchval(
                    SQL_COUNT_RUBRIC_ROWS,
                    row["id"],
                    len(CHANGED_BY_PREFIX),
                    CHANGED_BY_PREFIX,
                )
                decision = decide(
                    old_score=float(row["credibility_score"]),
                    new_score=baseline,
                    already_baselined=bool(applied_before),
                    rebaseline=rebaseline,
                )
                if not decision.apply:
                    outcomes.append(
                        Outcome(
                            handle=declaration.handle,
                            name=row["name"],
                            old_score=float(row["credibility_score"]),
                            new_score=baseline,
                            status="skipped",
                            detail=decision.reason_skipped,
                        )
                    )
                    continue

                if apply_changes:
                    reason = rubric.reason_for(declaration)
                    if rebaseline and applied_before:
                        reason = f"{reason} Re-applied on a rubric change."
                    # One transaction, the same shape the analyst service
                    # uses: a score that moved without its audit row is the
                    # silent change rule 8 exists to prevent.
                    async with conn.transaction():
                        await conn.execute(SQL_UPDATE_SOURCE_SCORE, baseline, now, row["id"])
                        await conn.execute(
                            SQL_INSERT_AUDIT_LOG,
                            str(uuid.uuid4()),
                            row["id"],
                            float(row["credibility_score"]),
                            baseline,
                            reason,
                            author,
                            now,
                            _LABELS_JSON,
                            row["org_id"],
                        )
                    log.info(
                        "source_rubric.baseline_applied",
                        source_id=row["id"],
                        handle=declaration.handle,
                        old_score=float(row["credibility_score"]),
                        new_score=baseline,
                        criteria_met=declaration.criteria_met,
                    )

                outcomes.append(
                    Outcome(
                        handle=declaration.handle,
                        name=row["name"],
                        old_score=float(row["credibility_score"]),
                        new_score=baseline,
                        status="applied" if apply_changes else "would_apply",
                    )
                )

    return outcomes


def _report(outcomes: list[Outcome], *, apply_changes: bool, org_id: Optional[str]) -> None:
    # The scope is printed, since --org-id defaults to SEED_ORG_ID and a
    # shell that exports it would otherwise scope a run silently.
    print(f"Organisation: {org_id or 'all'}")
    if not outcomes:
        print("The rubric declares no outlet. Nothing to apply.")
        return

    for outcome in outcomes:
        old = "-" if outcome.old_score is None else f"{outcome.old_score:.2f}"
        new = "-" if outcome.new_score is None else f"{outcome.new_score:.2f}"
        line = f"{outcome.status:<12} {old:>6} -> {new:<6} {outcome.handle}"
        if outcome.detail:
            line = f"{line}  ({outcome.detail})"
        print(line)

    changed = sum(1 for o in outcomes if o.status in ("applied", "would_apply"))
    if not apply_changes and changed:
        print(f"\n{changed} score(s) would change. Re-run with --apply to write them.")


async def _run(args: argparse.Namespace) -> int:
    pool = await asyncpg.create_pool(args.postgres_url, min_size=1, max_size=2)
    if pool is None:
        print("Could not open a connection pool.", file=sys.stderr)
        return 1
    try:
        outcomes = await apply_rubric(
            pool,
            apply_changes=args.apply,
            rebaseline=args.rebaseline,
            org_id=args.org_id or None,
        )
    finally:
        await pool.close()

    _report(outcomes, apply_changes=args.apply, org_id=args.org_id or None)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply the structural credibility baseline to existing Sources"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes. Without it the run prints what it would do.",
    )
    parser.add_argument(
        "--org-id",
        default=os.getenv("SEED_ORG_ID", ""),
        help=(
            "Scope the run to one organisation. Defaults to SEED_ORG_ID, and "
            "walks every organisation when neither is set."
        ),
    )
    parser.add_argument(
        "--rebaseline",
        action="store_true",
        help=(
            "Also set the baseline on a Source that already has one. Use after "
            "a rubric change, knowing it discards behavioural movement."
        ),
    )
    args = parser.parse_args()

    # Read from the environment and never from a flag, following the other
    # scripts: a DSN on argv is a password in `ps` output and in shell history.
    args.postgres_url = os.getenv("POSTGRES_URL", "")
    if not args.postgres_url:
        print(
            "Set POSTGRES_URL. This script takes no database URL on the command line.",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
