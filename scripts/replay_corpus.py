"""Replay a dated corpus in chronological stages - issue #47.

A single bulk import of a historic corpus produces the wrong result even when
every timestamp in it is correct. Candidate Topic promotion requires
persistence across clustering runs, and a bulk import gives one run. Hostility
shift requires a prior baseline, and a bulk import has none. The end state
arrives with none of the history that makes it meaningful.

This driver ingests the corpus in weekly stages. Each stage sets the reference
time to the end of its week, imports the items whose Publication Time falls in
that week, and then runs detection at that moment, so a cluster grows, a
baseline forms and a Signal carries the date its evidence existed.

Weekly rather than daily: a week gives the persistence and novelty gates enough
runs to behave normally and the timeline real slope, without paying for
clustering and language model labelling on CPU once per day.

What a stage runs, in order:

  import       the week's items, through the same ingest path a Backfill uses
  embed        wait for the analyst worker to embed what was just imported
  cluster      near-duplicate detection, then Leiden, at the stage's clock
  signal       every detector, at the stage's clock
  candidate    one Candidate Topic detection pass, at the stage's clock
  report       only at the stages carrying a requested report date

Clustering and the Signal detectors are called in this process rather than
dispatched, which is what ADR 0003 describes: the reference time is a parameter
on those functions, so one pass reads and writes a single moment. Labelling and
cross-verification are enqueued exactly as the scheduler's own cluster loop
enqueues them. Embedding stays in the analyst worker, because that is where the
models are.

Reset is unconditional. A Replay deletes the organisation's content and every
row detection produced for it before the first stage runs, because an
incremental re-run drifts from the corpus and leaves an operator unable to say
which run produced an artifact. Watch Spaces and Sources survive: they are
configuration the Replay imports into, not output it produced.

The capability is gated behind the clock override, so it cannot run against a
live deployment: VIRTUAL_CLOCK_ENABLED must be on and ENVIRONMENT must be on
VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS. See docs/adr/0003-virtual-clock.md.

Usage::

    POSTGRES_URL=... uv run python scripts/replay_corpus.py corpus.jsonl \\
        --topic-id <uuid> --org-id org-demo --report-date 2026-07-25

See docs/replay.md for the run sheet.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Sequence

import asyncpg
import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings


def _repo_root() -> Path:
    """Directory holding the workspace pyproject.toml.

    Searched for by marker rather than counted with parents[N], because the
    index starts at the file's directory and an off-by-one resolves to a path
    that exists and is wrong.
    """
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError("No workspace pyproject.toml above scripts/replay_corpus.py")


# Running this as a script puts scripts/ on sys.path rather than the repository
# root, so the sibling importer is not importable as scripts.import_corpus.
# Tests import it that way, and one import path for one module keeps the
# importer's parsing rules the only ones a corpus has to satisfy.
if str(_repo_root()) not in sys.path:
    sys.path.insert(0, str(_repo_root()))

from anveshak.analyst.clustering import run_clustering  # noqa: E402
from anveshak.analyst.convergence import check_cross_topic_convergence  # noqa: E402
from anveshak.analyst.credibility import run_cross_verification_update  # noqa: E402
from anveshak.analyst.dedup import (  # noqa: E402
    detect_near_duplicates,
    upsert_near_duplicates,
)
from anveshak.analyst.detection import detect_candidate_topics  # noqa: E402
from anveshak.analyst.labeller import check_label_staleness  # noqa: E402
from anveshak.analyst.signal_engine import (  # noqa: E402
    check_hostility_shifts,
    check_identifier_signals,
    check_manufactured_narratives,
    check_mobilization_calls,
    check_signals,
    check_template_signals,
)
from anveshak.clock import ClockSettings, describe_clock  # noqa: E402
from anveshak.models.report import ReportType  # noqa: E402
from anveshak.reporter.db import create_report_row  # noqa: E402

from scripts.import_corpus import (  # noqa: E402
    CorpusFormatError,
    CorpusItem,
    SourceStateError,
    TopicAccessError,
    import_corpus,
    load_corpus,
    verify_topic_access,
)

log = structlog.get_logger(__name__)

ANALYST_QUEUE = "arq:analyst"
REPORTER_QUEUE = "arq:reporter"

# Weekly. See the module docstring for why not daily.
DEFAULT_STAGE_DAYS = 7

DEFAULT_REPORT_TYPE = "intelligence_brief"
# The formats a Replay may be asked for, named by the enum the reporter stores
# rather than by a list kept here: a typo on the command line would otherwise
# reach the worker and fail a report point hours into a run.
REPORT_TYPES = tuple(member.value for member in ReportType)
DEFAULT_REPORT_CREDIBILITY_MIN = 30.0

# A stage's embedding wait. Generous: translation costs roughly 30s per article
# on CPU, and a busy week of a large corpus is a few hundred items.
EMBED_TIMEOUT_S = 1800
EMBED_POLL_S = 5
# Items that fail the analyst's quality gate are never embedded and never
# marked, so a wait for "zero unembedded" would burn the whole timeout at every
# stage. Progress stopping for this long means the worker is done with what it
# can do, and the rest is reported rather than waited on.
EMBED_STALL_S = 180

# One report at a time, and generously bounded: report generation is the
# slowest thing in the arc on CPU, and concurrent generations are known to
# time out.
REPORT_TIMEOUT_S = 3600

# ---------------------------------------------------------------------------
# SQL - module-level constants (patterns.md convention)
# ---------------------------------------------------------------------------

SQL_ACTIVE_TOPICS = """
    SELECT id FROM topics
    WHERE org_id = $1 AND status = 'active'
    ORDER BY created_at ASC
"""

# The stage's own items, identified by the Capture Time the stage imported them
# with. A count over the whole Topic would never settle while an earlier
# stage's quality-gated item sat unembedded forever.
SQL_UNEMBEDDED_IN_STAGE = """
    SELECT COUNT(*) FROM content_items
    WHERE topic_id = $1
      AND captured_at = $2
      AND embedding IS NULL
"""

SQL_REPORT_STATUS = "SELECT generated_at, generation_error FROM reports WHERE id = $1"

SQL_TOPIC_REPORT_SETTINGS = "SELECT credibility_min FROM topics WHERE id = $1"

# Every other organisation with an active Topic on this deployment. The Signal
# detectors and Candidate Topic detection are deployment-wide, exactly as they
# are in the scheduler, so a Replay fires them against every active Topic on
# the host. For another organisation that means Signals backdated months, which
# this organisation's reset does not remove.
SQL_OTHER_ORGS_WITH_ACTIVE_TOPICS = """
    SELECT org_id, COUNT(*) AS topics
    FROM topics
    WHERE status = 'active' AND org_id <> $1
    GROUP BY org_id
    ORDER BY org_id
"""

# Reset. Ordered deepest child first, and every statement scoped to one
# organisation. The cluster foreign key is nulled explicitly before the
# clusters go: content_items.narrative_cluster_id is ON DELETE SET NULL, so the
# database would do it anyway, and stating it keeps the order readable as a
# teardown rather than as a dependency on a constraint's delete rule.
# See .agents/skills/learned/references/fk-cascade-teardown-order.md.
RESET_STATEMENTS: tuple[tuple[str, str], ...] = (
    (
        "vision_results",
        """
        DELETE FROM vision_results WHERE media_asset_id IN (
            SELECT ma.id FROM media_assets ma
            JOIN content_items ci ON ci.id = ma.content_item_id
            WHERE ci.org_id = $1
        )
        """,
    ),
    (
        "media_assets",
        """
        DELETE FROM media_assets WHERE content_item_id IN (
            SELECT id FROM content_items WHERE org_id = $1
        )
        """,
    ),
    (
        "extracted_entities",
        """
        DELETE FROM extracted_entities WHERE content_item_id IN (
            SELECT id FROM content_items WHERE org_id = $1
        )
        """,
    ),
    (
        "report_source_warnings",
        """
        DELETE FROM report_source_warnings WHERE report_id IN (
            SELECT r.id FROM reports r
            JOIN topics t ON t.id = r.topic_id
            WHERE t.org_id = $1
        )
        """,
    ),
    (
        "reports",
        """
        DELETE FROM reports WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    (
        "near_duplicates",
        """
        DELETE FROM near_duplicates
        WHERE content_item_a_id IN (SELECT id FROM content_items WHERE org_id = $1)
           OR content_item_b_id IN (SELECT id FROM content_items WHERE org_id = $1)
        """,
    ),
    (
        "signals",
        """
        DELETE FROM signals WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    ("candidate_topics", "DELETE FROM candidate_topics WHERE org_id = $1"),
    (
        "identifier_cluster_items",
        """
        DELETE FROM identifier_cluster_items WHERE identifier_cluster_id IN (
            SELECT ic.id FROM identifier_clusters ic
            JOIN topics t ON t.id = ic.topic_id
            WHERE t.org_id = $1
        )
        """,
    ),
    (
        "identifier_clusters",
        """
        DELETE FROM identifier_clusters WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    (
        "content_items.narrative_cluster_id",
        """
        UPDATE content_items SET narrative_cluster_id = NULL
        WHERE org_id = $1 AND narrative_cluster_id IS NOT NULL
        """,
    ),
    (
        "narrative_clusters",
        """
        DELETE FROM narrative_clusters WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    (
        "topic_content_items",
        """
        DELETE FROM topic_content_items WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    ("content_items", "DELETE FROM content_items WHERE org_id = $1"),
    (
        "analysis_jobs",
        """
        DELETE FROM analysis_jobs WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    # Both are produced from the content a Replay imports rather than
    # configured: a discovered Source is proposed off items in the corpus, and
    # an archive row indexes content retention wrote out. Trackers and Source
    # assessments are left alone, because an analyst configures those and a
    # Replay does not create them.
    (
        "discovered_sources",
        """
        DELETE FROM discovered_sources WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    (
        "content_archives",
        """
        DELETE FROM content_archives WHERE topic_id IN (
            SELECT id FROM topics WHERE org_id = $1
        )
        """,
    ),
    # Credibility is restored to the score each Source held before this
    # organisation's first audited change, then that audit trail is deleted in
    # the same transaction. Architectural rule 8 forbids a silent credibility
    # change, and this leaves no unlogged delta: the changes being reversed and
    # the rows recording them go together. Without the restore a re-run would
    # start from drifted scores and produce different Signals from the same
    # corpus.
    #
    # Bounded to Sources this organisation owns. A Source is a global entity,
    # and the audit row carries the owning organisation rather than the one
    # whose Replay moved the score, so a wider restore would overwrite a value
    # another organisation's own assessment produced and leave their audit rows
    # describing a score the row no longer holds. Their drift stays, with its
    # trail intact, which is the recoverable half of the two.
    (
        "sources.credibility_score",
        """
        UPDATE sources s
        SET credibility_score = first_change.old_score,
            updated_at = NOW()
        FROM (
            SELECT DISTINCT ON (source_id) source_id, old_score
            FROM credibility_audit_log
            WHERE org_id = $1
            ORDER BY source_id, created_at ASC
        ) AS first_change
        WHERE s.id = first_change.source_id
          AND s.org_id = $1
          AND s.credibility_score IS DISTINCT FROM first_change.old_score
        """,
    ),
    ("credibility_audit_log", "DELETE FROM credibility_audit_log WHERE org_id = $1"),
)


class ReplayRefusedError(RuntimeError):
    """The Replay cannot run as asked, and running it anyway would mislead."""


class ReplayStageError(RuntimeError):
    """A stage could not complete, so the stages after it would be wrong."""


# ---------------------------------------------------------------------------
# The environment guard
# ---------------------------------------------------------------------------


def verify_replay_permitted(settings: ClockSettings | None = None) -> None:
    """Refuse to run where backdated detection output is not permitted.

    The same two layers the clock override uses, checked once up front rather
    than discovered at the first write: a Replay that failed halfway would have
    already reset the organisation's data.
    """
    resolved = settings if settings is not None else ClockSettings()
    described = describe_clock(resolved)
    if described["clock"] != "virtual":
        raise ReplayRefusedError(
            f"{described['reason']} A Replay writes Signals, clusters and "
            "reports dated in the past, so it runs only where that is "
            "permitted. See docs/adr/0003-virtual-clock.md."
        )


async def verify_sole_tenant(
    pool: asyncpg.Pool,
    org_id: str,
    *,
    allow_shared_host: bool = False,
) -> None:
    """Refuse a Replay on a deployment another organisation is using.

    The Signal detectors and Candidate Topic detection sweep every active Topic
    on the host, the way the scheduler runs them. During a Replay they run at a
    past reference time, so another organisation's Topic would collect Signals
    and Candidate Topics dated months ago that it never produced, and the reset
    is scoped to one organisation so nothing would remove them.

    A Replay runs on a dedicated deployment. allow_shared_host is for a
    development machine where the other organisations are test fixtures and the
    operator has decided that is acceptable.
    """
    rows = await pool.fetch(SQL_OTHER_ORGS_WITH_ACTIVE_TOPICS, org_id)
    if not rows:
        return

    described = ", ".join(f"{row['org_id']} ({row['topics']} Topic(s))" for row in rows)
    if allow_shared_host:
        log.warning(
            "replay.shared_host",
            org_id=org_id,
            other_orgs=described,
            reason=(
                "detection is deployment-wide, so this run can write backdated "
                "Signals against Topics the reset will not clean up"
            ),
        )
        return

    raise ReplayRefusedError(
        f"Other organisations have active Topics on this deployment: {described}. "
        "Detection is deployment-wide, so a Replay would date their Signals "
        "months ago and this organisation's reset would not remove them. "
        "Archive those Topics, or pass --allow-shared-host to accept it."
    )


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """One chronological slice of the corpus, and the moment it runs at."""

    index: int
    total: int
    start: datetime
    end: datetime
    reference_time: datetime
    items: tuple[CorpusItem, ...]
    report_dates: tuple[date, ...] = ()
    # Items with no Publication Time, carried by the first stage.
    undated: int = 0
    # True when the reference time was pulled back to now, because the stage
    # ends after today and the clock refuses a reference time in the future.
    clamped: bool = False

    @property
    def label(self) -> str:
        return f"{self.start.date().isoformat()} to {self.end.date().isoformat()}"


def plan_stages(
    items: Sequence[CorpusItem],
    *,
    stage_days: int = DEFAULT_STAGE_DAYS,
    report_dates: Iterable[date] = (),
    now: datetime | None = None,
) -> list[Stage]:
    """Split a corpus into chronological stages by Publication Time.

    Stages are contiguous and anchored at UTC midnight of the first Publication
    Time, so a boundary is a date rather than a time of day. A stage with no
    items is kept: a quiet week is evidence, and dropping it would compress the
    timeline into something the story did not do.
    """
    if stage_days < 1:
        raise ReplayRefusedError("stage_days must be at least 1 day")
    if not items:
        raise ReplayRefusedError("The corpus is empty, so there is nothing to Replay")

    resolved_now = now if now is not None else datetime.now(UTC)
    dated = [item for item in items if item.published_at is not None]
    undated = [item for item in items if item.published_at is None]
    if not dated:
        raise ReplayRefusedError(
            "No item in the corpus carries a Publication Time, so it cannot be "
            "staged chronologically. Import it with scripts/import_corpus.py "
            "instead, which does not claim an order."
        )

    ahead = [item for item in dated if item.published_at > resolved_now]  # type: ignore[operator]
    if ahead:
        # Every stage past today would clamp onto the same reference time, so
        # their items would share a Capture Time, the embedding wait would
        # count two stages at once and the 24 hour Signal dedup would suppress
        # the later stage. A date in the future is a corpus error either way.
        earliest = min(item.published_at for item in ahead)  # type: ignore[type-var]
        raise ReplayRefusedError(
            f"{len(ahead)} item(s) carry a Publication Time after now, the "
            f"earliest {earliest.isoformat()}. A Replay runs over history."
        )

    first = min(item.published_at for item in dated)  # type: ignore[type-var]
    last = max(item.published_at for item in dated)  # type: ignore[type-var]
    anchor = datetime(first.year, first.month, first.day, tzinfo=UTC)
    span = last - anchor
    total = max(1, math.ceil((span.total_seconds() + 1) / (stage_days * 86400)))

    wanted = sorted(set(report_dates))
    stages: list[Stage] = []
    for index in range(total):
        start = anchor + timedelta(days=stage_days * index)
        end = start + timedelta(days=stage_days)
        in_stage = sorted(
            (item for item in dated if start <= item.published_at < end),  # type: ignore[operator]
            key=lambda item: item.published_at,  # type: ignore[arg-type,return-value]
        )
        if index == 0 and undated:
            # An undated item cannot sit on a timeline, but it still carries a
            # Source into the independent source count. Running it in the first
            # stage keeps it in the corpus rather than silently dropping it.
            in_stage = in_stage + undated

        reference_time = min(end, resolved_now)
        stage_reports = tuple(d for d in wanted if start.date() <= d < end.date())

        stages.append(
            Stage(
                index=index + 1,
                total=total,
                start=start,
                end=end,
                reference_time=reference_time,
                items=tuple(in_stage),
                report_dates=stage_reports,
                undated=len(undated) if index == 0 else 0,
                clamped=reference_time < end,
            )
        )

    placed = {d for stage in stages for d in stage.report_dates}
    missing = [d for d in wanted if d not in placed]
    if missing:
        # Generating no report for a date an operator asked for would leave
        # them waiting for an artifact that was never going to exist.
        dates = ", ".join(d.isoformat() for d in missing)
        raise ReplayRefusedError(
            f"Report date(s) {dates} fall outside the corpus, which runs "
            f"{anchor.date().isoformat()} to {stages[-1].end.date().isoformat()}."
        )
    return stages


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


async def reset_org_state(
    pool: asyncpg.Pool,
    org_id: str,
    *,
    clock_settings: ClockSettings | None = None,
) -> dict[str, int]:
    """Delete everything a previous Replay wrote for one organisation.

    Returns rows affected per statement. One transaction: a teardown that
    stopped partway would leave content without the clusters that explain it,
    and the next run would import on top of the remains.

    The guard runs here as well as at the entry point, the same reason
    parse_reference_time re-checks it: this function is importable, and a
    teardown protected only by whatever its callers remember to do is protected
    by nothing.
    """
    verify_replay_permitted(clock_settings)
    affected: dict[str, int] = {}
    async with pool.acquire() as conn, conn.transaction():
        for label, sql in RESET_STATEMENTS:
            status = await conn.execute(sql, org_id)
            affected[label] = _rows_affected(status)
    log.info(
        "replay.reset",
        org_id=org_id,
        **{key: value for key, value in affected.items() if value},
    )
    return affected


def _rows_affected(status: str) -> int:
    """Row count from an asyncpg command tag such as 'DELETE 12'."""
    tail = status.rsplit(" ", 1)[-1]
    return int(tail) if tail.isdigit() else 0


# ---------------------------------------------------------------------------
# Stage steps
# ---------------------------------------------------------------------------

EmbedFn = Callable[[asyncpg.Pool, str, datetime], Awaitable[int]]


async def wait_for_embeddings(
    pool: asyncpg.Pool,
    topic_id: str,
    captured_at: datetime,
    *,
    timeout_s: int = EMBED_TIMEOUT_S,
    poll_s: int = EMBED_POLL_S,
    stall_s: int = EMBED_STALL_S,
) -> int:
    """Wait for the analyst worker to embed the stage's items.

    Returns how many are still unembedded. Never raises: an item the quality
    gate skipped is never embedded and never marked, so a wait for zero would
    burn the timeout at every stage. Progress stalling means the worker has
    done what it can, and the remainder is reported rather than waited on.
    """
    waited = 0
    stalled = 0
    remaining = await _unembedded(pool, topic_id, captured_at)
    while remaining:
        await asyncio.sleep(poll_s)
        waited += poll_s
        current = await _unembedded(pool, topic_id, captured_at)
        stalled = stalled + poll_s if current == remaining else 0
        remaining = current
        if remaining == 0:
            break
        if stalled >= stall_s or waited >= timeout_s:
            log.warning(
                "replay.embeddings_incomplete",
                topic_id=topic_id,
                remaining=remaining,
                waited_s=waited,
                reason=(
                    "the analyst worker stopped making progress; the quality "
                    "gate skips embedding for boilerplate, and those items "
                    "never cluster"
                ),
            )
            break
    return remaining


async def _unembedded(pool: asyncpg.Pool, topic_id: str, captured_at: datetime) -> int:
    return int(await pool.fetchval(SQL_UNEMBEDDED_IN_STAGE, topic_id, captured_at))


@dataclass(frozen=True)
class DetectionCounts:
    """What one stage's detection pass produced."""

    clusters: int
    signals: int
    candidates: int


async def _noop_broadcast(payload: dict) -> None:
    """No WebSocket from here, which is what the scheduler does too."""
    return None


async def run_detection(
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    *,
    org_id: str,
    reference_time: datetime,
) -> DetectionCounts:
    """Run one full detection pass for an organisation at a reference time.

    Mirrors the deployment: the scheduler's cluster loop calls clustering in
    process and enqueues labelling, and its signal loop calls every detector.
    Each of them is handed the stage's reference time instead of reading the
    wall clock.

    The Signal detectors and Candidate Topic detection are deployment-wide,
    exactly as they are in the scheduler, so they see every active Topic on the
    host rather than this organisation's alone. run_replay refuses to start
    where another organisation has one, since a Signal it fired would be dated
    months ago and this organisation's reset would not remove it.
    """
    cluster_count = 0

    topic_ids = [row["id"] for row in await pool.fetch(SQL_ACTIVE_TOPICS, org_id)]
    for topic_id in topic_ids:
        # Near-duplicates first, exactly as the cluster loop does: the
        # independent source count a Signal fires on is wrong without it.
        pairs = await detect_near_duplicates(topic_id, pool)
        if pairs:
            await upsert_near_duplicates(pairs, pool)

        cluster_ids = await run_clustering(topic_id, pool, reference_time=reference_time)
        cluster_count += len(cluster_ids)
        if not cluster_ids:
            continue

        for cluster_id in cluster_ids:
            try:
                if await check_label_staleness(cluster_id, pool):
                    await arq_pool.enqueue_job(
                        "generate_cluster_label",
                        cluster_id,
                        _queue_name=ANALYST_QUEUE,
                    )
            except Exception as exc:
                # Labelling is enrichment: a cluster without a label still
                # clusters, signals and appears in a report.
                log.warning(
                    "replay.label_enqueue_failed",
                    cluster_id=cluster_id,
                    error=str(exc),
                )

        # Cross-verification runs here rather than on the worker, unlike the
        # scheduler's fire-and-forget enqueue. It writes credibility, and a
        # boost that lands at whatever point the worker reaches it changes the
        # credibility_score_at_capture of whichever later stage it overtakes,
        # so two runs of the same corpus would not agree.
        await run_cross_verification_update(pool, topic_id, reference_time=reference_time)

    signals = 0
    for detector in (
        check_signals,
        check_hostility_shifts,
        check_identifier_signals,
        check_template_signals,
        check_manufactured_narratives,
        check_mobilization_calls,
    ):
        signals += await detector(pool, _noop_broadcast, reference_time)
    signals += await check_cross_topic_convergence(pool, reference_time)

    candidates = await detect_candidate_topics(pool, reference_time=reference_time)

    return DetectionCounts(clusters=cluster_count, signals=signals, candidates=candidates)


async def generate_stage_report(
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    *,
    topic_id: str,
    reference_time: datetime,
    window_start: datetime,
    report_type: str = DEFAULT_REPORT_TYPE,
    timeout_s: int = REPORT_TIMEOUT_S,
) -> str:
    """Create a report row and generate it at the stage's reference time.

    One at a time and awaited, because concurrent report generation on CPU is
    known to time out. created_at is the wall clock, because the row is created
    now; generated_at comes from the reference time, which is what makes the
    row, the PDF footer and the report's own relative windows agree.

    The row is written by the reporter's own create_report_row rather than by
    SQL of this script's, so a Replay report and a report an analyst asked for
    are the same row, written once, by one statement.
    """
    report_id = str(uuid.uuid4())
    # The Topic's own credibility floor, which is what the reporter's scheduled
    # path reads. A fixed default here would admit sources into a Replay report
    # that a live report for the same Topic excludes.
    credibility_min = await pool.fetchval(SQL_TOPIC_REPORT_SETTINGS, topic_id)
    await create_report_row(
        pool,
        report_id=report_id,
        topic_id=topic_id,
        report_type=report_type,
        time_window_start=window_start,
        time_window_end=reference_time,
        credibility_min=float(
            credibility_min if credibility_min is not None else DEFAULT_REPORT_CREDIBILITY_MIN
        ),
    )

    job = await arq_pool.enqueue_job(
        "generate_report",
        report_id,
        reference_time.isoformat(),
        _queue_name=REPORTER_QUEUE,
    )
    if job is None:
        raise ReplayStageError(
            f"Report {report_id} could not be enqueued. The reporter queue "
            "already holds a job with the same id."
        )
    try:
        await job.result(timeout=timeout_s)
    except asyncio.TimeoutError as exc:
        raise ReplayStageError(
            f"Report {report_id} did not finish within {timeout_s}s. Check the "
            "reporter worker logs."
        ) from exc

    row = await pool.fetchrow(SQL_REPORT_STATUS, report_id)
    if row is None or row["generated_at"] is None:
        error = row["generation_error"] if row else "the report row disappeared"
        raise ReplayStageError(f"Report {report_id} was not generated: {error}")
    return report_id


# ---------------------------------------------------------------------------
# The Replay
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageResult:
    """One stage's outcome, for the run sheet and for the progress line."""

    stage: Stage
    imported: int
    duplicates: int
    unembedded: int
    clusters: int
    signals: int
    candidates: int
    reports: tuple[str, ...]


@dataclass(frozen=True)
class ReplaySummary:
    """Everything a run produced, so an artifact is traceable to it."""

    stages: tuple[StageResult, ...]
    reset: dict[str, int]

    @property
    def imported(self) -> int:
        return sum(result.imported for result in self.stages)

    @property
    def signals(self) -> int:
        return sum(result.signals for result in self.stages)

    @property
    def candidates(self) -> int:
        return sum(result.candidates for result in self.stages)

    @property
    def reports(self) -> tuple[str, ...]:
        return tuple(report for result in self.stages for report in result.reports)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    """Order-preserving de-duplication of the requested report formats.

    A format asked for twice is one artifact either way: rule 4 makes a report
    immutable, so the second generation is a duplicate row rather than a
    refreshed one, and it costs a language model run on CPU to produce.
    """
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return tuple(seen)


def _progress(stage: Stage, message: str) -> None:
    print(f"  [{stage.index}/{stage.total}] {stage.label}  {message}", flush=True)


async def run_stage(
    stage: Stage,
    *,
    topic_id: str,
    org_id: str,
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    corpus_start: datetime,
    embed: EmbedFn = wait_for_embeddings,
    report_types: Sequence[str] = (DEFAULT_REPORT_TYPE,),
) -> StageResult:
    """Import one stage's items and run detection at that stage's clock."""
    summary = await import_corpus(
        stage.items,
        topic_id=topic_id,
        org_id=org_id,
        pool=pool,
        arq_pool=arq_pool,
        # Capture Time is the stage's moment, not the run's. The hostility
        # shift Signal compares a recent window against a prior one and both
        # filter Capture Time, so a corpus imported in one moment measures a
        # delta of zero however correct its Publication Times are.
        captured_at=stage.reference_time,
    )

    unembedded = await embed(pool, topic_id, stage.reference_time)
    counts = await run_detection(
        pool,
        arq_pool,
        org_id=org_id,
        reference_time=stage.reference_time,
    )

    reports: list[str] = []
    for report_date in stage.report_dates:
        # One format at a time and awaited, for the reason the report point
        # itself is awaited: concurrent generation on CPU times out.
        for report_type in _unique(report_types):
            _progress(stage, f"generating the {report_date.isoformat()} {report_type}")
            reports.append(
                await generate_stage_report(
                    pool,
                    arq_pool,
                    topic_id=topic_id,
                    reference_time=stage.reference_time,
                    window_start=corpus_start,
                    report_type=report_type,
                )
            )

    return StageResult(
        stage=stage,
        imported=summary.imported,
        duplicates=summary.duplicates,
        unembedded=unembedded,
        clusters=counts.clusters,
        signals=counts.signals,
        candidates=counts.candidates,
        reports=tuple(reports),
    )


async def run_replay(
    items: Sequence[CorpusItem],
    *,
    topic_id: str,
    org_id: str,
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    stage_days: int = DEFAULT_STAGE_DAYS,
    report_dates: Iterable[date] = (),
    embed: EmbedFn = wait_for_embeddings,
    report_types: Sequence[str] = (DEFAULT_REPORT_TYPE,),
    now: datetime | None = None,
    clock_settings: ClockSettings | None = None,
    allow_shared_host: bool = False,
) -> ReplaySummary:
    """Reset, then Replay a corpus stage by stage into one Topic.

    allow_shared_host permits a run where another organisation has an active
    Topic. Off by default, because the Signal detectors are deployment-wide.
    """
    verify_replay_permitted(clock_settings)
    await verify_topic_access(pool, topic_id=topic_id, org_id=org_id)
    await verify_sole_tenant(pool, org_id, allow_shared_host=allow_shared_host)

    stages = plan_stages(items, stage_days=stage_days, report_dates=report_dates, now=now)
    for stage in stages:
        if stage.clamped:
            log.info(
                "replay.reference_time_clamped",
                stage=stage.index,
                stage_end=stage.end.isoformat(),
                reference_time=stage.reference_time.isoformat(),
                reason="the stage ends after now, and a reference time in the future is refused",
            )

    reset = await reset_org_state(pool, org_id, clock_settings=clock_settings)
    print(
        f"  reset: {sum(reset.values())} row(s) removed for organisation {org_id} "
        f"across {len([k for k, v in reset.items() if v])} table(s)",
        flush=True,
    )

    corpus_start = stages[0].start
    results: list[StageResult] = []
    for stage in stages:
        _progress(stage, f"importing {len(stage.items)} item(s)")
        result = await run_stage(
            stage,
            topic_id=topic_id,
            org_id=org_id,
            pool=pool,
            arq_pool=arq_pool,
            corpus_start=corpus_start,
            embed=embed,
            report_types=report_types,
        )
        _progress(
            stage,
            f"imported {result.imported}, already present {result.duplicates}, "
            f"clusters {result.clusters}, Signals {result.signals}, "
            f"Candidate Topics {result.candidates}"
            + (f", unembedded {result.unembedded}" if result.unembedded else ""),
        )
        results.append(result)

    return ReplaySummary(stages=tuple(results), reset=reset)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> int:
    items = load_corpus(args.corpus)
    print(f"  corpus read: {len(items)} items from {args.corpus}", flush=True)

    pool = await asyncpg.create_pool(args.postgres_url, min_size=1, max_size=4)
    if pool is None:
        print("Could not open a database pool", file=sys.stderr)
        return 1
    arq_pool = await create_pool(RedisSettings.from_dsn(args.redis_url))
    try:
        summary = await run_replay(
            items,
            topic_id=args.topic_id,
            org_id=args.org_id,
            pool=pool,
            arq_pool=arq_pool,
            stage_days=args.stage_days,
            report_dates=args.report_dates,
            report_types=tuple(args.report_types) or (DEFAULT_REPORT_TYPE,),
            allow_shared_host=args.allow_shared_host,
        )
    except ReplayStageError as exc:
        # Stages already run stay in the database. Recovery is a re-run, which
        # resets first, rather than a resume: resuming from a partial state is
        # the incremental run this driver exists to refuse.
        print(f"  stage failed: {exc}", file=sys.stderr)
        print(
            "        Re-run the Replay. It resets first, so the result is the same as a first run.",
            file=sys.stderr,
        )
        return 1
    finally:
        await arq_pool.aclose()
        await pool.close()

    print(
        f"  done: {len(summary.stages)} stage(s), {summary.imported} item(s) imported, "
        f"{summary.signals} Signal(s), {summary.candidates} Candidate Topic(s), "
        f"{len(summary.reports)} report(s)",
        flush=True,
    )
    if summary.reports:
        print("  reports: " + ", ".join(summary.reports), flush=True)
    return 0


def _report_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a YYYY-MM-DD date") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a dated corpus in chronological stages")
    parser.add_argument("corpus", type=Path, help="Corpus file in JSON Lines format")
    parser.add_argument("--topic-id", required=True, help="Topic the items are imported into")
    parser.add_argument(
        "--org-id",
        default=os.getenv("SEED_ORG_ID", ""),
        help="Organisation that owns the Topic. Defaults to SEED_ORG_ID.",
    )
    parser.add_argument(
        "--stage-days",
        type=int,
        default=DEFAULT_STAGE_DAYS,
        help=f"Length of one stage in days (default: {DEFAULT_STAGE_DAYS}).",
    )
    parser.add_argument(
        "--report-date",
        dest="report_dates",
        action="append",
        default=[],
        type=_report_date,
        help="Generate a report at the stage covering this date. Repeatable.",
    )
    parser.add_argument(
        "--report-type",
        dest="report_types",
        action="append",
        default=[],
        choices=REPORT_TYPES,
        help=(
            "Report format to generate at every report date. Repeatable, so one "
            f"run produces a report point in each format (default: {DEFAULT_REPORT_TYPE})."
        ),
    )
    parser.add_argument(
        "--allow-shared-host",
        action="store_true",
        help=(
            "Run even though another organisation has an active Topic here. "
            "Detection is deployment-wide, so their Topics collect backdated "
            "Signals this run will not clean up."
        ),
    )
    args = parser.parse_args()

    if not args.org_id:
        print("Set SEED_ORG_ID or pass --org-id.", file=sys.stderr)
        return 1
    # Read from the environment and never from a flag, as the importer does: a
    # DSN on argv is a password in `ps` output and in shell history.
    args.postgres_url = os.getenv("POSTGRES_URL", "")
    args.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if not args.postgres_url:
        print(
            "Set POSTGRES_URL. This script takes no database URL on the command line.",
            file=sys.stderr,
        )
        return 1

    # The clock guard describes the host, not the database POSTGRES_URL points
    # at, and a development shell pointed at a production DSN passes it. This
    # is the second half of the answer, and it is deliberately a thing an
    # operator has to type: the same shape scripts/seed_demo uses for a live
    # run. It cannot be satisfied by a .env that was copied somewhere.
    if os.getenv("ANVESHAK_ALLOW_REPLAY_RESET") != "1":
        print(
            "A Replay deletes every content item and every detection row the "
            f"organisation {args.org_id} has, in the database POSTGRES_URL "
            "points at. Set ANVESHAK_ALLOW_REPLAY_RESET=1 to confirm that is "
            "the database you mean.",
            file=sys.stderr,
        )
        return 2

    print(
        "  A Replay deletes every content item and every detection row this "
        f"organisation has ({args.org_id}) before the first stage runs.",
        flush=True,
    )

    try:
        return asyncio.run(_run(args))
    except ReplayRefusedError as exc:
        print(f"Replay refused: {exc}", file=sys.stderr)
        return 2
    except CorpusFormatError as exc:
        print(f"Corpus rejected: {exc}", file=sys.stderr)
        return 1
    except TopicAccessError as exc:
        print(f"{exc}. Nothing imported, nothing reset.", file=sys.stderr)
        return 1
    except SourceStateError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
