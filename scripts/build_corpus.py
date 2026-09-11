"""Build a demonstration corpus from the plan that describes it - issue #54.

The corpus is the committed source of truth for a demonstration, and the
database dump afterwards is only an artifact of a run over it. So this script
has one job: turn the targets in ``infra/configs/corpora/*.yaml`` into a file in
the format ``scripts/import_corpus.py`` reads, and refuse rather than guess.

News is collected through the archive Backfill route the scraper already has,
so a historic article arrives with the Publication Time the outlet published it
with and the name of the evidence that produced that time. Social material that
has no historic route is hand-placed, each item carrying the reporting it came
from.

What it refuses, and why each refusal is worth a stopped build:

- A collection target that is not pinned. A guessed channel identifier collects
  a copycat channel's uploads and attributes them to the movement, and a
  corpus that invents its own sources manufactures the evidence for a Signal.
- An outlet with no ``OUTLET_BACKFILL`` entry. That registry is deny by
  default, so an unconfigured outlet discovers nothing and reads as an outlet
  that published nothing in the window, which is indistinguishable from a quiet
  one.
- A hand-placed item with no citation. A hand-placed item without the reporting
  it came from is a fabricated timestamp inside a corpus whose whole claim is
  that it fabricates none.
- An item from one of the squatter domains imitating the official site. An
  impostor item entering the corpus is a correctness problem rather than a
  tidiness one: it lands as the movement's own words.

Usage::

    uv run python scripts/build_corpus.py --plan infra/configs/corpora/cockroach_janta_party.yaml

Collection reaches the public internet, so it runs where that is intended and
where the collector account's OPSEC posture has been agreed, not on a demo host.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlparse

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anveshak.scraper.archive_backfill import (  # noqa: E402
    OUTLET_BACKFILL,
    DateWindow,
    belongs_to_outlet,
    discover_urls,
    fetch_backfill_item,
)
from anveshak.scraper.rate_limiter import DomainRateLimiter  # noqa: E402

from scripts.corpus_plan import (  # noqa: E402
    DEFAULT_PLAN_PATH,
    CorpusPlan,
    NewsOutlet,
    PlanError,
    load_plan,
)
from scripts.import_corpus import (  # noqa: E402
    CorpusFormatError,
    CorpusItem,
    parse_corpus_line,
)

log = structlog.get_logger(__name__)


class BuildError(RuntimeError):
    """The build cannot proceed, and says which target or line stopped it."""


@dataclass(frozen=True)
class CollectedItem:
    """One item on its way into the corpus file.

    Deliberately flat rather than reusing ``CorpusItem``: this is the build's
    own intermediate, and the corpus record it becomes is validated back
    through ``parse_corpus_line`` before it is written, so the file the
    importer reads is the file the format tests describe.
    """

    url: str
    text: str
    source_handle: str
    source_name: str
    source_platform: str
    published_at: Optional[datetime] = None
    published_at_signal: Optional[str] = None
    language: Optional[str] = None
    discovery: Optional[str] = None
    body_source: Optional[str] = None


@dataclass(frozen=True)
class HandPlaced:
    """A hand-placed item and the reporting it came from."""

    item: CorpusItem
    citation: str
    line_number: int


@dataclass(frozen=True)
class BuildSummary:
    """What the corpus covers, for the freeze record in the plan document."""

    total: int
    per_phase: dict[int, int]
    empty_phases: list[int]
    undated: int
    outside_arc: int
    by_language: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Refusals before anything is fetched
# ---------------------------------------------------------------------------


def verify_pinned(plan: CorpusPlan) -> None:
    """Refuse a build whose own collection targets are not filled in.

    Only the targets this build reads. The social layers are collected by the
    adapters with their own credentials, and the hand-placed layer is
    transcribed, so blocking a news build on a channel identifier it never
    reads would be a refusal nobody can act on from here. Those are reported
    instead, by the caller.
    """
    unpinned = plan.unpinned_for_build()
    if unpinned:
        raise BuildError(
            "the plan's collection targets are not pinned yet: "
            + ", ".join(unpinned)
            + ". Fill them from the verification pass against the movement's "
            "own site; a guessed identifier collects somebody else's content."
        )


def verify_outlets_configured(
    plan: CorpusPlan,
    *,
    registry: Optional[Mapping[str, Any]] = None,
) -> None:
    """Refuse an outlet the scraper has no historic route for."""
    outlets = OUTLET_BACKFILL if registry is None else registry
    missing = [outlet.host for outlet in plan.news_outlets if outlet.host not in outlets]
    if missing:
        raise BuildError(
            "no OUTLET_BACKFILL entry for "
            + ", ".join(sorted(missing))
            + ". Survey the outlet's history and add its entry, because an "
            "unconfigured outlet discovers nothing and reports as an outlet "
            "that published nothing."
        )


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def matches_keywords(text: str, keywords: Sequence[str]) -> bool:
    """True where the text names the subject.

    Casefolded substring matching, which covers Devanagari as well: the corpus
    keywords are phrases rather than tokens, and a tokeniser here would have to
    agree with the analyst's, which it would not.
    """
    folded = text.casefold()
    return any(keyword.casefold() in folded for keyword in keywords)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_impostor(url: str, plan: CorpusPlan) -> bool:
    """True where the URL belongs to a domain imitating the official site.

    A subdomain of a squatter is the same squatter, matching how the Backfill
    treats an outlet's own subdomains.
    """
    host = _host(url)
    for domain in plan.impostor_domains:
        squatter = domain.lower().removeprefix("www.")
        if host == squatter or host.endswith(f".{squatter}"):
            return True
    return False


def in_arc(published_at: Optional[datetime], plan: CorpusPlan) -> bool:
    """True where the item is dated inside the arc, or carries no date at all.

    An undated item is kept: it cannot sit on a timeline, but it still carries
    its Source into the independent source count.
    """
    if published_at is None:
        return True
    return plan.start_date <= published_at.date() <= plan.freeze_date


# ---------------------------------------------------------------------------
# The record written to the corpus
# ---------------------------------------------------------------------------


def corpus_record(item: CollectedItem) -> dict[str, Any]:
    """One corpus line, in the format documented in docs/corpus_format.md.

    A key whose value is unknown is omitted rather than written null. The format
    refuses a Publication Time without the signal that produced it, and a null
    written for either would be an assertion the item does not support.
    """
    record: dict[str, Any] = {
        "url": item.url,
        "text": item.text,
        "source": {
            "handle": item.source_handle,
            "name": item.source_name,
            "platform": item.source_platform,
        },
    }
    if item.language:
        record["language"] = item.language
    if item.published_at is not None and item.published_at_signal:
        record["published_at"] = item.published_at.isoformat()
        record["published_at_signal"] = item.published_at_signal
    if item.discovery:
        record["discovery"] = item.discovery
    if item.body_source:
        record["body_source"] = item.body_source
    return record


# ---------------------------------------------------------------------------
# Hand-placed items
# ---------------------------------------------------------------------------


def read_hand_placed(path: Path, plan: Optional[CorpusPlan] = None) -> list[HandPlaced]:
    """Read a hand-placed file, requiring a citation comment above each item.

    The corpus format already treats a ``#`` line as a provenance note, so the
    citation lives next to the item it describes rather than in a second file
    that can drift from it. A citation is consumed by the item below it and
    does not carry to the next one, because one source note standing for two
    items is a claim about an item nobody checked.
    """
    placed: list[HandPlaced] = []
    citation: list[str] = []

    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            citation.clear()
            continue
        if stripped.startswith("#"):
            citation.append(stripped.lstrip("#").strip())
            continue
        if not citation:
            raise BuildError(
                f"{path}: line {line_number} is a hand-placed item with no "
                f"citation comment above it. An item without the reporting or "
                f"archive it came from is a fabricated timestamp."
            )
        try:
            item = parse_corpus_line(raw, line_number)
        except CorpusFormatError as exc:
            raise BuildError(f"{path}: {exc}") from exc
        if plan is not None and not in_arc(item.published_at, plan):
            # The Replay stages by Publication Time and refuses an item outside
            # the corpus it plans over, hours into a run. Refusing here means
            # the operator fixes a date rather than a stage.
            raise BuildError(
                f"{path}: line {line_number} is dated "
                f"{item.published_at.isoformat() if item.published_at else 'never'}, "
                f"outside the arc {plan.start_date.isoformat()} to "
                f"{plan.freeze_date.isoformat()}."
            )
        if plan is not None and is_impostor(item.url, plan):
            # The hand-placed layer is where a squatter URL is most plausible,
            # because it is transcribed by hand from coverage rather than
            # discovered from an outlet the plan named.
            raise BuildError(
                f"{path}: line {line_number} is from {item.url}, one of the "
                f"domains imitating the official site. An impostor item lands "
                f"in the corpus as the movement's own words."
            )
        placed.append(HandPlaced(item=item, citation=" ".join(citation), line_number=line_number))
        citation.clear()

    return placed


# ---------------------------------------------------------------------------
# News collection
# ---------------------------------------------------------------------------

DiscoverFn = Callable[..., Awaitable[Sequence[Any]]]
FetchFn = Callable[..., Awaitable[Optional[Any]]]


async def collect_news(
    plan: CorpusPlan,
    *,
    discover: DiscoverFn = discover_urls,
    fetch: FetchFn = fetch_backfill_item,
    registry: Optional[Mapping[str, Any]] = None,
) -> list[CollectedItem]:
    """Collect every configured outlet's history of the subject.

    Discovery returns whatever the outlet published in the window, so selection
    happens on the body: an article is in the corpus because it is about the
    subject, not because it is from an outlet that covers it.
    """
    outlets = OUTLET_BACKFILL if registry is None else registry
    verify_outlets_configured(plan, registry=outlets)

    window = DateWindow(start=plan.start_date, end=plan.freeze_date)
    collected: dict[str, CollectedItem] = {}
    # Every URL this run has already decided about, accepted or not. Without it
    # a URL one outlet's feed carries and another syndicates is fetched again in
    # full, which costs the publisher a request and the run its time budget.
    seen: set[str] = set()
    # One limiter across the whole build, so the per-domain gap actually
    # applies. A limiter per call is no limiter: the run fetches an outlet's
    # entire history at full speed from the collector's address, which is a
    # blocking risk and an OPSEC one on a run that reaches the public internet.
    limiter = DomainRateLimiter()

    for outlet in plan.news_outlets:
        backfill = outlets[outlet.host]
        for discovered in await discover(backfill, window, limiter=limiter):
            if discovered.url in seen:
                continue
            seen.add(discovered.url)
            if is_impostor(discovered.url, plan):
                continue
            if not belongs_to_outlet(discovered.url, backfill):
                # A sitemap or feed lists whatever its publisher put in it, and
                # everything collected here is attributed to this outlet's
                # Source. A third-party URL landing under a trusted outlet
                # inflates the independent source count Signals fire on.
                log.info(
                    "corpus.off_host_url_skipped",
                    url=discovered.url,
                    outlet=outlet.host,
                    reason="discovered URL is not the outlet's own",
                )
                continue
            article = await fetch(discovered, backfill, limiter=limiter)
            if article is None or not article.raw_text:
                # A Backfilled item with no body is not evidence of anything.
                continue
            if not matches_keywords(article.raw_text, plan.keywords):
                continue
            if not in_arc(article.published_at, plan):
                continue
            item = _from_article(article, outlet)
            if not _writable(item):
                continue
            collected[discovered.url] = item

    return list(collected.values())


def _writable(item: CollectedItem) -> bool:
    """True where the item survives the corpus format it will be written in.

    Checked at collection rather than at write time. Scraped text is untrusted,
    the format refuses a control character in it, and an unhandled refusal at
    the end of a run that has already fetched the whole arc discards every item
    collected. One unusable article is dropped and logged instead.
    """
    try:
        parse_corpus_line(json.dumps(corpus_record(item), ensure_ascii=False), 0)
    except CorpusFormatError as exc:
        log.warning("corpus.item_rejected", url=item.url, error=str(exc))
        return False
    return True


def _from_article(article: Any, outlet: NewsOutlet) -> CollectedItem:
    title = getattr(article, "title", "") or ""
    body = article.raw_text
    return CollectedItem(
        url=article.url,
        # The title carries the framing, which is half of what a stance measure
        # reads, and the Backfill returns it separately from the body.
        text=f"{title}\n\n{body}".strip() if title else body,
        source_handle=outlet.handle,
        source_name=outlet.name,
        source_platform=outlet.platform,
        published_at=article.published_at,
        published_at_signal=article.published_at_signal,
        discovery=article.discovery,
        body_source=article.body_source,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarise(items: Iterable[CollectedItem], plan: CorpusPlan) -> BuildSummary:
    """Count what the corpus covers, phase by phase.

    An empty phase is named rather than counted, because it is a stage of the
    Replay that imports nothing: the arc then shows a quiet week the story did
    not have, and no detection runs against evidence that was never collected.
    """
    per_phase = {phase.number: 0 for phase in plan.phases}
    by_language: dict[str, int] = {}
    total = undated = outside = 0

    for item in items:
        total += 1
        if item.language:
            by_language[item.language] = by_language.get(item.language, 0) + 1
        if item.published_at is None:
            undated += 1
            continue
        phase = plan.phase_on(item.published_at.date())
        if phase is None:
            outside += 1
            continue
        per_phase[phase.number] += 1

    return BuildSummary(
        total=total,
        per_phase=per_phase,
        empty_phases=[number for number, count in per_phase.items() if count == 0],
        undated=undated,
        outside_arc=outside,
        by_language=by_language,
    )


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write_corpus(
    path: Path,
    items: Sequence[CollectedItem],
    hand_placed: Sequence[HandPlaced],
    plan: CorpusPlan,
) -> int:
    """Write the corpus file, collected and hand-placed items in one sequence.

    Ordered by Publication Time, so the file reads in the order the story
    happened and a reviewer can follow it. Both layers are merged into that one
    order rather than appended in turn: the hand-placed layer covers the period
    the movement's own account was blocked, and a file that puts it at the end
    reads as though it happened after the split.

    A hand-placed item keeps its citation comment on the line above it, which is
    where the format expects a provenance note and where a reviewer reads it.
    Undated items go last, since they belong nowhere on the timeline.
    """
    lines: list[str] = [
        f"# {plan.name} corpus. Issue #{plan.issue}, epic #{plan.epic}.",
        f"# Arc {plan.start_date.isoformat()} to {plan.freeze_date.isoformat()}, "
        f"frozen for the demonstration Replay.",
        "# Built by scripts/build_corpus.py from "
        f"{DEFAULT_PLAN_PATH.name}. Review it the way a Source list is reviewed.",
    ]

    # (item, citation) pairs, so the merge does not have to ask which layer an
    # item came from twice.
    merged: list[tuple[CollectedItem, Optional[str]]] = [(item, None) for item in items]
    merged.extend((collected_of(placed.item), placed.citation) for placed in hand_placed)

    dated = sorted(
        (pair for pair in merged if pair[0].published_at is not None),
        key=lambda pair: pair[0].published_at,  # type: ignore[arg-type,return-value]
    )
    undated = [pair for pair in merged if pair[0].published_at is None]

    for item, citation in [*dated, *undated]:
        if citation:
            lines.append(f"# Cited: {citation}")
        line = json.dumps(corpus_record(item), ensure_ascii=False)
        # Validated as it is written, so a build never produces a file the
        # importer will reject halfway through a Replay. The line number is the
        # one the file will have, because a refusal reporting line 0 sends a
        # reader to the top of a file the problem is not at.
        parse_corpus_line(line, len(lines) + 1)
        lines.append(line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(merged)


def _record_of(item: CorpusItem) -> dict[str, Any]:
    return corpus_record(collected_of(item))


def collected_of(item: CorpusItem) -> CollectedItem:
    """A parsed corpus item as the build's own intermediate.

    Hand-placed items go through this so they are counted in the same summary
    the collected items are: a phase covered only by hand-placed material would
    otherwise report as empty and stop the build.
    """
    return CollectedItem(
        url=item.url,
        text=item.text,
        source_handle=item.source.handle,
        source_name=item.source.name,
        source_platform=item.source.platform,
        published_at=item.published_at,
        published_at_signal=item.published_at_signal,
        language=item.language,
        discovery=item.discovery,
        body_source=item.body_source,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _report(summary: BuildSummary, plan: CorpusPlan) -> None:
    print(f"  items: {summary.total}")
    for phase in plan.phases:
        print(
            f"    phase {phase.number} {phase.start.isoformat()} to "
            f"{phase.end.isoformat()}: {summary.per_phase[phase.number]}"
        )
    print(f"  no Publication Time: {summary.undated}")
    if summary.outside_arc:
        print(f"  outside the arc: {summary.outside_arc}")
    # Only what the corpus itself declares. The news route leaves language
    # unset on purpose, because the analyst pipeline detects it on ingest, and
    # a language this build guessed would be read downstream as a fact.
    for language, count in sorted(summary.by_language.items()):
        print(f"  language declared in the corpus, {language}: {count}")


async def _run(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    print(f"  plan: {plan.name}, {plan.start_date} to {plan.freeze_date}")

    if args.dry_run:
        unpinned = plan.unpinned()
        print("  collection targets still to pin:" if unpinned else "  every target pinned")
        for target in unpinned:
            print(f"    {target}")
        return 0

    verify_pinned(plan)

    # Stated rather than silently skipped: these layers are real parts of the
    # corpus that this build does not collect, and an operator reading only
    # "collected N news items" would not know they are still outstanding.
    for target in plan.unpinned_for_social():
        print(f"  not collected here, still to pin: {target}")

    hand_placed: list[HandPlaced] = []
    for path in plan.hand_placed_files:
        if not path.exists():
            raise BuildError(
                f"{path} is named in the plan but does not exist. A hand-placed "
                f"file the plan declares and the build cannot find is a layer of "
                f"the corpus silently missing."
            )
        hand_placed.extend(read_hand_placed(path, plan))
    print(f"  hand-placed: {len(hand_placed)} item(s), each with a citation")

    items = await collect_news(plan)
    print(f"  collected: {len(items)} news item(s)")

    # Both layers, because a phase the news route missed and the hand-placed
    # layer covers is a covered phase.
    summary = summarise([*items, *(collected_of(placed.item) for placed in hand_placed)], plan)
    _report(summary, plan)

    if summary.empty_phases and not args.allow_empty_phase:
        phases = ", ".join(str(number) for number in summary.empty_phases)
        print(
            f"Phase(s) {phases} have no item in either layer, so the Replay would "
            f"import nothing for them. Pass --allow-empty-phase to write the "
            f"corpus anyway.",
            file=sys.stderr,
        )
        return 1

    output = args.out or Path(plan.corpus_file)
    written = write_corpus(output, items, hand_placed, plan)
    print(f"  written: {written} item(s) to {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a demonstration corpus from its plan")
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help=f"Corpus plan (default: {DEFAULT_PLAN_PATH}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Where to write the corpus. Defaults to the plan's output.corpus_file.",
    )
    parser.add_argument(
        "--allow-empty-phase",
        action="store_true",
        help="Write the corpus even where a phase collected nothing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report which collection targets are still unpinned, and collect nothing.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except BuildError as exc:
        print(f"Build refused: {exc}", file=sys.stderr)
        return 2
    except PlanError as exc:
        # The message names the field that failed, which is the whole reason
        # PlanError exists. A traceback here hides it.
        print(f"Plan refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
