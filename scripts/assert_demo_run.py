"""Assert a demonstration Replay against the plan written before it - issue #54.

The run is the test. What makes it a test rather than a demonstration of
whatever happened is that the expectations were recorded first, in
``infra/configs/corpora/*.yaml``, and this script compares the database to them
afterwards.

Five assertions, each at a seam that already exists:

1. A Candidate Topic was raised from a Watch Space and promoted. That is the
   unaided-discovery claim, and it is the first thing a customer checks.
2. Every expected Signal fired, dated inside the phase that predicted it. A
   Signal of the right type in the wrong phase is not the Signal the plan
   expected: it means the evidence arrived somewhere else in the arc.
3. The Sentiment Timeline has buckets across the arc, and states how much it
   excluded. A chart with no stated exclusion count cannot be judged.
4. Three report points exist in every requested format, with distinct
   generation timestamps, which is what shows an assessment changing rather
   than a snapshot.
5. The surfaces a text corpus is not expected to populate are empty. An honest
   empty state is part of the demonstration: it tells an evaluating officer
   what the platform does not have.

A failure here is a finding to investigate, never a threshold to tune. Record
it in ``docs/tuning_history.md`` whether or not it changes anything.

Usage::

    export POSTGRES_URL=postgresql://anveshak:...@localhost:5433/anveshak
    uv run python scripts/assert_demo_run.py --org-id org-demo

``POSTGRES_URL`` comes from the environment and never from a flag, because a
DSN on argv is a password in ``ps`` output and in shell history. Where it is
unset the DSN is assembled from ``POSTGRES_PASSWORD`` exactly as the demo
detection run assembles it, so a host with a `.env` needs nothing else.

The assertions are scoped to one Topic as well as one organisation. An
organisation holds other Topics, and a Signal, a report or a day of content
belonging to one of them would otherwise satisfy an expectation about this
arc. ``--topic-id`` names it, and where it is omitted the Topic promoted from a
Watch Space is used, which is the one the demonstration is about.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.corpus_plan import (  # noqa: E402
    DEFAULT_PLAN_PATH,
    KNOWN_EMPTY_SURFACES,
    CorpusPlan,
    PlanError,
    load_plan,
)
from scripts.run_demo_detection import resolve_postgres_url  # noqa: E402


@dataclass(frozen=True)
class Check:
    """One assertion, its result, and enough detail to act on a failure."""

    name: str
    passed: bool
    detail: str


# ---------------------------------------------------------------------------
# SQL. Module level and org scoped, so both facts are testable without a
# database: a query that forgot org_id reads another organisation's run.
# ---------------------------------------------------------------------------

SQL_PROMOTED_CANDIDATES = """
    SELECT ct.id, ct.status, ct.promoted_topic_id, ct.run_count, t.name AS watch_space
    FROM candidate_topics ct
    JOIN topics t ON t.id = ct.watch_space_id AND t.is_watch_space = TRUE
    WHERE ct.org_id = $1
      AND ct.status = 'accepted'
      AND ct.promoted_topic_id IS NOT NULL
"""

SQL_SIGNALS = """
    SELECT s.signal_type, s.created_at
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    WHERE t.org_id = $1
      AND s.topic_id = $2
    ORDER BY s.created_at
"""

# The Topic predicate matches the Sentiment Timeline's own: content reaches a
# Topic either directly or through the join table, and a chart that read only
# one of them would show a different arc from the workbench.
SQL_TIMELINE_BUCKETS = """
    SELECT DATE_TRUNC('day', ci.published_at) AS bucket, COUNT(*) AS items
    FROM content_items ci
    WHERE ci.org_id = $1
      AND (
        ci.topic_id = $2
        OR EXISTS (
            SELECT 1 FROM topic_content_items tci
            WHERE tci.topic_id = $2 AND tci.content_item_id = ci.id
        )
      )
      AND ci.published_at IS NOT NULL
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    GROUP BY 1
    ORDER BY 1
"""

# Stated rather than silently dropped, exactly as the Sentiment Timeline's own
# footnote does: an analyst who cannot see how much was excluded cannot judge
# the chart.
SQL_TIMELINE_EXCLUDED = """
    SELECT COUNT(*) AS excluded
    FROM content_items ci
    WHERE ci.org_id = $1
      AND (
        ci.topic_id = $2
        OR EXISTS (
            SELECT 1 FROM topic_content_items tci
            WHERE tci.topic_id = $2 AND tci.content_item_id = ci.id
        )
      )
      AND ci.published_at IS NULL
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
"""

SQL_REPORTS = """
    SELECT r.report_type, r.generated_at
    FROM reports r
    JOIN topics t ON t.id = r.topic_id
    WHERE t.org_id = $1
      AND r.topic_id = $2
      AND r.generated_at IS NOT NULL
    ORDER BY r.generated_at
"""

SQL_EMPTY_SURFACES: dict[str, str] = {
    "vision_results": """
        SELECT COUNT(*) AS rows_present
        FROM vision_results vr
        JOIN media_assets ma ON ma.id = vr.media_asset_id
        JOIN content_items ci ON ci.id = ma.content_item_id
        WHERE ci.org_id = $1
          AND (
            ci.topic_id = $2
            OR EXISTS (
                SELECT 1 FROM topic_content_items tci
                WHERE tci.topic_id = $2 AND tci.content_item_id = ci.id
            )
          )
    """,
    "media_assets": """
        SELECT COUNT(*) AS rows_present
        FROM media_assets ma
        JOIN content_items ci ON ci.id = ma.content_item_id
        WHERE ci.org_id = $1
          AND (
            ci.topic_id = $2
            OR EXISTS (
                SELECT 1 FROM topic_content_items tci
                WHERE tci.topic_id = $2 AND tci.content_item_id = ci.id
            )
          )
    """,
}


# Every surface the plan may declare has a query here, and the plan refuses a
# name this dict does not carry. Without the pairing an unknown surface would
# report empty having queried nothing. Raised rather than asserted, because
# `python -O` strips an assert and this is a correctness gate.
if set(SQL_EMPTY_SURFACES) != set(KNOWN_EMPTY_SURFACES):
    raise RuntimeError(
        "SQL_EMPTY_SURFACES and corpus_plan.KNOWN_EMPTY_SURFACES have drifted: "
        f"{sorted(set(SQL_EMPTY_SURFACES) ^ set(KNOWN_EMPTY_SURFACES))}"
    )


# ---------------------------------------------------------------------------
# The assertions, over rows rather than over a connection
# ---------------------------------------------------------------------------


def check_promotion(rows: Sequence[Mapping[str, Any]]) -> Check:
    """A Candidate Topic was raised from a Watch Space and promoted."""
    if not rows:
        return Check(
            name="candidate promoted from a Watch Space",
            passed=False,
            detail=(
                "no accepted Candidate Topic with a promoted Topic. The "
                "unaided-discovery claim rests on this one: check the four "
                "promotion gates against the run's candidate rows rather than "
                "lowering them."
            ),
        )
    names = sorted({str(row["watch_space"]) for row in rows})
    # The run count is the persistence gate a promotion had to pass, and the
    # run sheet narrates it, so the assertion states it rather than leaving the
    # operator to open the row.
    runs = sorted({int(row["run_count"]) for row in rows if row.get("run_count") is not None})
    seen = (
        f", seen across {', '.join(str(count) for count in runs)} detection run(s)" if runs else ""
    )
    return Check(
        name="candidate promoted from a Watch Space",
        passed=True,
        detail=f"{len(rows)} promoted from {', '.join(names)}{seen}",
    )


def check_expected_signals(
    rows: Sequence[Mapping[str, Any]],
    plan: CorpusPlan,
) -> list[Check]:
    """Every expected Signal fired, dated inside the phase that predicted it."""
    checks: list[Check] = []
    for expected in plan.expected_signals:
        phase = plan.phase(expected.phase)
        matching = [
            row
            for row in rows
            if row["signal_type"] == expected.signal_type
            and phase.contains(_as_date(row["created_at"]))
        ]
        elsewhere = [row for row in rows if row["signal_type"] == expected.signal_type]
        if matching:
            detail = f"{len(matching)} in phase {phase.number}"
        elif elsewhere:
            # The same type in a different phase is a different finding from no
            # Signal at all: the detector works and the evidence landed
            # somewhere else in the arc.
            dates = ", ".join(
                sorted({_as_date(row["created_at"]).isoformat() for row in elsewhere})
            )
            detail = (
                f"none in phase {phase.number} ({phase.start} to {phase.end}); "
                f"the same type fired on {dates}. Expected because: {expected.reasoning}"
            )
        else:
            detail = f"never fired anywhere in the run. Expected because: {expected.reasoning}"
        checks.append(
            Check(
                name=f"phase {phase.number} {expected.signal_type}",
                passed=bool(matching),
                detail=detail,
            )
        )
    return checks


def check_timeline(
    buckets: Sequence[Mapping[str, Any]],
    excluded: Optional[int],
    plan: CorpusPlan,
) -> Check:
    """Non-empty buckets across the arc, with a stated excluded count."""
    if excluded is None:
        return Check(
            name="Sentiment Timeline",
            passed=False,
            detail="the excluded count is unknown, so the chart cannot be judged",
        )

    covered = {
        phase.number
        for phase in plan.phases
        for bucket in buckets
        if phase.contains(_as_date(bucket["bucket"]))
    }
    missing = [phase.number for phase in plan.phases if phase.number not in covered]
    if missing:
        return Check(
            name="Sentiment Timeline",
            passed=False,
            detail=(
                f"no bucket in phase(s) {', '.join(str(number) for number in missing)}: "
                f"the arc has a gap the story did not have. {excluded} item(s) "
                f"excluded for carrying no Publication Time."
            ),
        )
    return Check(
        name="Sentiment Timeline",
        passed=True,
        detail=(
            f"{len(buckets)} daily bucket(s) across all {len(plan.phases)} phases, "
            f"{excluded} item(s) excluded for carrying no Publication Time"
        ),
    )


def check_reports(rows: Sequence[Mapping[str, Any]], plan: CorpusPlan) -> list[Check]:
    """A report at each point, in each format, and the points distinct in time."""
    checks: list[Check] = []
    for report_type in plan.report_types:
        of_type = [row for row in rows if row["report_type"] == report_type]
        found: list[date] = []
        for reported in plan.report_dates:
            # The report is generated at the end of the stage carrying its
            # date, so the timestamp lands inside that stage rather than on the
            # date itself. The width comes from the plan, because a Replay run
            # with a different --stage-days would otherwise mis-window every
            # point and report a correct run as a failure.
            window_end = reported + timedelta(days=plan.stage_days)
            if any(reported <= _as_date(row["generated_at"]) <= window_end for row in of_type):
                found.append(reported)
        missing = [reported for reported in plan.report_dates if reported not in found]
        checks.append(
            Check(
                name=f"report points, {report_type}",
                passed=not missing,
                detail=(
                    f"{len(found)} of {len(plan.report_dates)} report point(s)"
                    if not missing
                    else "no report generated at "
                    + ", ".join(reported.isoformat() for reported in missing)
                ),
            )
        )

        # Distinct within a format, not across the whole set. A Replay generates
        # every requested format at one stage's reference time, so the brief and
        # the full report at one point share a generated_at by construction:
        # they are the same moment assessed twice, which is what rule 4 means by
        # a point-in-time snapshot. What has to differ is the three points.
        stamps = [row["generated_at"] for row in of_type]
        distinct = len(set(stamps))
        checks.append(
            Check(
                name=f"report points differ in time, {report_type}",
                passed=distinct == len(plan.report_dates),
                detail=(
                    f"{distinct} distinct generation timestamp(s)"
                    if distinct == len(plan.report_dates)
                    else f"{distinct} distinct generation timestamp(s) across "
                    f"{len(stamps)} report(s), expected {len(plan.report_dates)}: "
                    f"an assessment that does not change over the life of the "
                    f"narrative demonstrates a snapshot"
                ),
            )
        )
    return checks


def check_empty_surfaces(counts: Mapping[str, int], plan: CorpusPlan) -> list[Check]:
    """The surfaces a text corpus is not expected to populate are empty."""
    checks: list[Check] = []
    for surface in plan.empty_surfaces:
        present = counts.get(surface, 0)
        checks.append(
            Check(
                name=f"{surface} is empty",
                passed=present == 0,
                detail=(
                    "empty, as an honest empty state"
                    if present == 0
                    else f"{present} row(s) present, which the plan did not expect"
                ),
            )
        )
    return checks


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"expected a date or datetime, found {type(value).__name__}")


# ---------------------------------------------------------------------------
# Running them against a database
# ---------------------------------------------------------------------------


class TopicNotResolvedError(RuntimeError):
    """The Topic the assertions run against could not be determined."""


async def resolve_topic_id(pool: asyncpg.Pool, *, org_id: str) -> str:
    """The Topic promoted from a Watch Space, where there is exactly one.

    The demonstration is about the Topic the platform raised, and its id is not
    known until the run produces it, so it is read back rather than typed in.
    Two promoted Topics, or none, is ambiguous, and asserting against whichever
    one came first would answer a question nobody asked.
    """
    rows = await pool.fetch(SQL_PROMOTED_CANDIDATES, org_id)
    promoted = sorted({str(row["promoted_topic_id"]) for row in rows})
    if len(promoted) == 1:
        return promoted[0]
    if not promoted:
        raise TopicNotResolvedError(
            f"no Topic in organisation {org_id} was promoted from a Watch Space, "
            f"so there is nothing the demonstration is about yet. Run the Replay "
            f"first, or name a Topic with --topic-id."
        )
    raise TopicNotResolvedError(
        f"{len(promoted)} Topics in organisation {org_id} were promoted from a "
        f"Watch Space, so the one to assert against is ambiguous. Name it with "
        f"--topic-id."
    )


async def run_assertions(
    pool: asyncpg.Pool,
    plan: CorpusPlan,
    *,
    org_id: str,
    topic_id: str,
) -> list[Check]:
    """Every assertion, in the order the plan states them.

    Scoped to one Topic as well as one organisation. An organisation holds
    other Topics, and a Signal, a report or a day of content belonging to one
    of them would otherwise satisfy an expectation about this arc.
    """
    checks: list[Check] = [check_promotion(await pool.fetch(SQL_PROMOTED_CANDIDATES, org_id))]
    checks.extend(check_expected_signals(await pool.fetch(SQL_SIGNALS, org_id, topic_id), plan))
    checks.append(
        check_timeline(
            await pool.fetch(SQL_TIMELINE_BUCKETS, org_id, topic_id),
            await pool.fetchval(SQL_TIMELINE_EXCLUDED, org_id, topic_id),
            plan,
        )
    )
    checks.extend(check_reports(await pool.fetch(SQL_REPORTS, org_id, topic_id), plan))

    counts = {
        surface: int(await pool.fetchval(sql, org_id, topic_id))
        for surface, sql in SQL_EMPTY_SURFACES.items()
        if surface in plan.empty_surfaces
    }
    checks.extend(check_empty_surfaces(counts, plan))
    return checks


def report(checks: Sequence[Check]) -> int:
    """Print every check, passed or failed, and return the exit code.

    Passes are printed too. A run that prints only failures cannot be read as
    evidence that the rest was asserted at all.
    """
    failed = [check for check in checks if not check.passed]
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"  [{marker}] {check.name}: {check.detail}")
    print(f"\n  {len(checks) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print(
            "\n  A failure here is a finding to investigate at the seam, not a "
            "threshold to tune. Record it in docs/tuning_history.md.",
        )
    return 1 if failed else 0


async def _run(args: argparse.Namespace) -> int:
    try:
        plan = load_plan(args.plan)
    except PlanError as exc:
        print(f"Plan refused: {exc}", file=sys.stderr)
        return 2
    # POSTGRES_URL wins where it is set, and otherwise the DSN is assembled from
    # POSTGRES_PASSWORD, which is the one credential a .env carries. Shared with
    # the demo detection run rather than reimplemented, because two spellings of
    # the same resolution drift and one of them then connects to nothing.
    postgres_url = resolve_postgres_url(dict(os.environ))
    if not postgres_url:
        print(
            "Set POSTGRES_URL, or POSTGRES_PASSWORD for the default host and port.",
            file=sys.stderr,
        )
        return 2

    pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=4)
    if pool is None:
        print("Could not open a database pool", file=sys.stderr)
        return 2
    try:
        topic_id = args.topic_id
        if not topic_id:
            try:
                topic_id = await resolve_topic_id(pool, org_id=args.org_id)
            except TopicNotResolvedError as exc:
                print(f"Cannot assert: {exc}", file=sys.stderr)
                return 2
        print(f"  plan: {plan.name}, organisation {args.org_id}, Topic {topic_id}")
        return report(await run_assertions(pool, plan, org_id=args.org_id, topic_id=topic_id))
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Assert a demonstration Replay against its plan")
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Corpus plan (default: {DEFAULT_PLAN_PATH}).",
    )
    parser.add_argument(
        "--org-id",
        default=os.getenv("SEED_ORG_ID", ""),
        help="Organisation whose Replay is asserted. Defaults to SEED_ORG_ID.",
    )
    parser.add_argument(
        "--topic-id",
        default="",
        help=(
            "Topic the assertions are scoped to. Defaults to the Topic promoted "
            "from a Watch Space, which is the one the demonstration is about."
        ),
    )
    args = parser.parse_args()
    if not args.org_id:
        print("--org-id is required, or set SEED_ORG_ID", file=sys.stderr)
        return 2
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
