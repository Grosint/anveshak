"""The corpus plan a demonstration run is built from and measured against - issue #54.

A demonstration corpus is only evidence of anything if what it was expected to
produce was written down before it produced it. The plan file is where that is
written: the arc and its phases, the report points, and the Signal each phase is
expected to fire with the reasoning behind the expectation.

Two programs read the same file. ``scripts/build_corpus.py`` collects against
it, and ``scripts/assert_demo_run.py`` asserts the Replay's output against it.
One file rather than two, because an expectation kept next to the assertion and
a target kept next to the collection drift apart silently, and the drift reads
as a demonstration that met its expectations.

The validation here is deliberately unforgiving, in the shape
``scripts/import_corpus.py`` uses for the corpus format itself: a key nobody
declared is refused, a phase gap is refused, and a Signal type the platform
never fires is refused. Each of those, read permissively, produces an
expectation that cannot fail - which is worse than no expectation, because it
looks like one that passed.

Nothing in the plan names a Watch Space keyword. Selecting a corpus by subject
is corpus construction; selecting a Watch Space by subject would stage the
result, and the Watch Space keyword constraint is asserted separately by
``tests/unit/test_watch_space.py``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anveshak.models.report import ReportType  # noqa: E402
from anveshak.models.signal import SignalType  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# The surfaces an assertion run knows how to count. Declared here rather than in
# the assertion script so the plan refuses a name nothing queries: an unknown
# surface would otherwise report PASS having queried nothing, which is an
# expectation that cannot fail.
KNOWN_EMPTY_SURFACES = frozenset({"vision_results", "media_assets"})

DEFAULT_PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "infra"
    / "configs"
    / "corpora"
    / "cockroach_janta_party.yaml"
)

PLAN_KEYS = frozenset(
    {
        "name",
        "issue",
        "epic",
        "start_date",
        "freeze_date",
        "languages",
        "phases",
        "report_dates",
        "report_types",
        "stage_days",
        "expected_signals",
        "empty_surfaces",
        "collection",
        "output",
    }
)

PHASE_KEYS = frozenset({"number", "name", "start", "end", "summary"})
EXPECTED_SIGNAL_KEYS = frozenset({"phase", "signal_type", "reasoning"})
LANGUAGE_KEYS = frozenset({"collected", "analysed"})
COLLECTION_KEYS = frozenset(
    {
        "canonical_domain",
        "impostor_domains",
        "keywords",
        "news",
        "social",
        "hand_placed_files",
        "not_collected",
    }
)
SOCIAL_KEYS = frozenset({"youtube", "telegram", "x", "instagram", "counter_narrative"})
OUTPUT_KEYS = frozenset({"corpus_file", "dump_file"})

SIGNAL_TYPES = frozenset(member.value for member in SignalType)
REPORT_TYPES = frozenset(member.value for member in ReportType)


class PlanError(ValueError):
    """The plan file cannot be read as a plan.

    Every message names the value that failed, because a plan refused without
    naming its bad field is a file an operator has to bisect by hand.
    """


@dataclass(frozen=True)
class Phase:
    """One named stretch of the arc, both ends inclusive."""

    number: int
    name: str
    start: date
    end: date
    summary: str

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class ExpectedSignal:
    """A Signal a phase is expected to produce, and why.

    The reasoning is not decoration. It is what a reader uses after the run to
    decide whether a Signal that did not fire is a defect in the detector or a
    corpus that never contained the evidence the expectation assumed.
    """

    phase: int
    signal_type: str
    reasoning: str


@dataclass(frozen=True)
class NewsOutlet:
    """One outlet whose history the corpus collects.

    host is what the scraper's OUTLET_BACKFILL registry is keyed by, and handle
    is what ``sources.url_or_handle`` holds, because the ingest path looks a
    Source up by handle and skips an item whose Source it cannot find. They are
    usually different strings for the same outlet, and conflating them creates
    a Source nothing imports into.
    """

    host: str
    name: str
    handle: str
    platform: str = "web"


@dataclass(frozen=True)
class YouTubeTarget:
    channel_id: Optional[str]
    backfill_count: int


@dataclass(frozen=True)
class CorpusPlan:
    """The demonstration plan, validated."""

    name: str
    issue: int
    epic: int
    start_date: date
    freeze_date: date
    collected_languages: tuple[str, ...]
    analysed_languages: tuple[str, ...]
    phases: tuple[Phase, ...]
    report_dates: tuple[date, ...]
    report_types: tuple[str, ...]
    stage_days: int
    expected_signals: tuple[ExpectedSignal, ...]
    empty_surfaces: tuple[str, ...]
    canonical_domain: Optional[str]
    impostor_domains: tuple[str, ...]
    keywords: tuple[str, ...]
    news_outlets: tuple[NewsOutlet, ...]
    youtube: YouTubeTarget
    telegram_channel: Optional[str]
    x_handle: Optional[str]
    counter_narrative_handles: tuple[str, ...]
    hand_placed_files: tuple[Path, ...]
    corpus_file: Path
    dump_file: Path

    def phase(self, number: int) -> Phase:
        for phase in self.phases:
            if phase.number == number:
                return phase
        raise PlanError(f"no phase {number} in the plan")

    def phase_on(self, day: date) -> Optional[Phase]:
        """The phase a date falls in, or None where it falls outside the arc."""
        for phase in self.phases:
            if phase.contains(day):
                return phase
        return None

    def expected_for(self, number: int) -> tuple[ExpectedSignal, ...]:
        return tuple(expected for expected in self.expected_signals if expected.phase == number)

    def unpinned(self) -> list[str]:
        """Every collection target still to be filled in from the verification pass.

        Reported rather than refused at load time, because the plan is read
        long before a collection run: a reviewer, the assertion harness and the
        tests all load a plan whose identifiers are not pinned yet.
        """
        return [*self.unpinned_for_build(), *self.unpinned_for_social()]

    def unpinned_for_build(self) -> list[str]:
        """The targets ``scripts/build_corpus.py`` itself consumes.

        These stop a build, because it would otherwise run: with no keywords it
        selects nothing, with no outlets it collects nothing, and with an empty
        impostor list it runs a squatter filter that matches nothing. An empty
        list is a list nobody filled in, not a finding that none exist.
        """
        missing: list[str] = []
        if not self.canonical_domain:
            missing.append("collection.canonical_domain")
        if not self.keywords:
            missing.append("collection.keywords")
        if not self.news_outlets:
            missing.append("collection.news.outlets")
        if not self.impostor_domains:
            missing.append("collection.impostor_domains")
        return missing

    def unpinned_for_social(self) -> list[str]:
        """The targets the social layers are collected with, outside this build.

        The adapters collect those layers, with their own credentials, and the
        hand-placed layer is transcribed. Reported rather than enforced here, so
        a news build is not blocked on an identifier it never reads, and the
        gap is still visible in one place.
        """
        missing: list[str] = []
        if not self.youtube.channel_id:
            missing.append("collection.social.youtube.channel_id")
        if not self.telegram_channel:
            missing.append("collection.social.telegram.channel")
        if not self.x_handle:
            missing.append("collection.social.x.handle")
        if not self.counter_narrative_handles:
            missing.append("collection.social.counter_narrative.handles")
        return missing


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PlanError(f"{field} must be a mapping, found {type(value).__name__}")
    return dict(value)


def _sequence(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise PlanError(f"{field} must be a list, found {type(value).__name__}")
    return list(value)


def _check_keys(value: Mapping[str, Any], allowed: frozenset[str], field: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PlanError(f"{field} has unknown key(s): {', '.join(unknown)}")


def _require(value: Mapping[str, Any], keys: Iterable[str], field: str) -> None:
    missing = sorted(key for key in keys if key not in value)
    if missing:
        raise PlanError(f"{field} is missing required key(s): {', '.join(missing)}")


def _date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    raise PlanError(f"{field} must be a date in YYYY-MM-DD form, found {value!r}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{field} must be a non-empty string, found {value!r}")
    return value


def _optional_text(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    return _text(value, field)


def _strings(value: Any, field: str) -> tuple[str, ...]:
    return tuple(
        _text(item, f"{field}[{index}]") for index, item in enumerate(_sequence(value, field))
    )


OUTLET_KEYS = frozenset({"host", "name", "handle", "platform"})


def _parse_outlets(raw: Any) -> tuple[NewsOutlet, ...]:
    outlets: list[NewsOutlet] = []
    for index, entry in enumerate(_sequence(raw, "collection.news.outlets")):
        field = f"collection.news.outlets[{index}]"
        mapping = _mapping(entry, field)
        _check_keys(mapping, OUTLET_KEYS, field)
        _require(mapping, {"host", "name", "handle"}, field)
        outlets.append(
            NewsOutlet(
                host=_text(mapping["host"], f"{field}.host").lower().removeprefix("www."),
                name=_text(mapping["name"], f"{field}.name"),
                handle=_text(mapping["handle"], f"{field}.handle"),
                platform=_text(mapping.get("platform") or "web", f"{field}.platform"),
            )
        )
    hosts = [outlet.host for outlet in outlets]
    duplicated = sorted({host for host in hosts if hosts.count(host) > 1})
    if duplicated:
        # Two entries for one host discover the same URLs twice and land the
        # same article under two Sources, which inflates the independent source
        # count that Signals fire on.
        raise PlanError(f"collection.news.outlets names {', '.join(duplicated)} more than once")
    return tuple(outlets)


def _parse_phases(raw: Any) -> tuple[Phase, ...]:
    entries = _sequence(raw, "phases")
    if not entries:
        raise PlanError("phases is empty, so the plan describes no arc")

    phases: list[Phase] = []
    for index, entry in enumerate(entries):
        field = f"phases[{index}]"
        mapping = _mapping(entry, field)
        _check_keys(mapping, PHASE_KEYS, field)
        _require(mapping, PHASE_KEYS, field)
        start = _date(mapping["start"], f"{field}.start")
        end = _date(mapping["end"], f"{field}.end")
        if end < start:
            raise PlanError(f"{field} ends before it starts: {start} to {end}")
        phases.append(
            Phase(
                number=int(mapping["number"]),
                name=_text(mapping["name"], f"{field}.name"),
                start=start,
                end=end,
                summary=_text(mapping["summary"], f"{field}.summary"),
            )
        )

    numbers = [phase.number for phase in phases]
    if numbers != sorted(set(numbers)) or numbers != list(range(1, len(numbers) + 1)):
        raise PlanError(f"phase numbers must run 1..{len(phases)} in order, found {numbers}")

    for earlier, later in zip(phases, phases[1:]):
        if later.start <= earlier.end:
            raise PlanError(
                f"phases {earlier.number} and {later.number} overlap: "
                f"{later.start} is on or before {earlier.end}"
            )
        # A gap is a stretch of the arc nothing claims, so a Signal landing in
        # it belongs to no phase and the run cannot be asked about that week.
        if (later.start - earlier.end).days != 1:
            first_missing = earlier.end + timedelta(days=1)
            raise PlanError(
                f"phases {earlier.number} and {later.number} leave a gap from "
                f"{first_missing.isoformat()}: the arc is contiguous by construction"
            )
    return tuple(phases)


def _parse_expected(raw: Any, phases: tuple[Phase, ...]) -> tuple[ExpectedSignal, ...]:
    entries = _sequence(raw, "expected_signals")
    if not entries:
        raise PlanError(
            "expected_signals is empty: a run with no recorded expectation "
            "cannot distinguish a Signal that failed to fire from one nobody "
            "expected"
        )

    known = {phase.number for phase in phases}
    expected: list[ExpectedSignal] = []
    for index, entry in enumerate(entries):
        field = f"expected_signals[{index}]"
        mapping = _mapping(entry, field)
        _check_keys(mapping, EXPECTED_SIGNAL_KEYS, field)
        _require(mapping, EXPECTED_SIGNAL_KEYS, field)
        signal_type = _text(mapping["signal_type"], f"{field}.signal_type")
        if signal_type not in SIGNAL_TYPES:
            raise PlanError(
                f"{field}.signal_type {signal_type!r} is not a Signal the "
                f"platform fires: {', '.join(sorted(SIGNAL_TYPES))}"
            )
        number = int(mapping["phase"])
        if number not in known:
            raise PlanError(f"{field} expects phase {number}, which the plan does not define")
        if not str(mapping["reasoning"] or "").strip():
            raise PlanError(
                f"{field}.reasoning is empty: without it a Signal that does not "
                f"fire cannot be read as a defect or as a corpus that never "
                f"held the evidence"
            )
        expected.append(
            ExpectedSignal(
                phase=number,
                signal_type=signal_type,
                reasoning=str(mapping["reasoning"]).strip(),
            )
        )
    return tuple(expected)


def _repo_path(value: Any, field: str) -> Path:
    """A path the plan declares, resolved and held inside the repository.

    The plan file is the one input these scripts treat as authoritative, and it
    names files that are read and a file that is written. A relative path with
    enough parent steps in it reads or writes outside the tree, so the same
    deny-by-default treatment the plan's keys already get applies to its paths.
    """
    raw = _text(value, field)
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else REPO_ROOT / candidate).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise PlanError(f"{field} {raw!r} resolves outside the repository, to {resolved}")
    return resolved


def _parse_languages(raw: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    mapping = _mapping(raw, "languages")
    _check_keys(mapping, LANGUAGE_KEYS, "languages")
    _require(mapping, LANGUAGE_KEYS, "languages")
    collected = _strings(mapping["collected"], "languages.collected")
    analysed = _strings(mapping["analysed"], "languages.analysed")
    if not collected or not analysed:
        raise PlanError("languages.collected and languages.analysed both need at least one entry")
    uncollected = sorted(set(analysed) - set(collected))
    if uncollected:
        # Analysis cannot read what collection never brought in, and the
        # mismatch otherwise shows up much later as a language with no content.
        raise PlanError(
            f"languages.analysed names {', '.join(uncollected)}, which "
            f"languages.collected does not collect"
        )
    return collected, analysed


def load_plan(path: Path = DEFAULT_PLAN_PATH) -> CorpusPlan:
    """Read and validate a corpus plan."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(f"no plan file at {path}") from exc
    except yaml.YAMLError as exc:
        raise PlanError(f"{path} is not valid YAML: {exc}") from exc

    plan = _mapping(raw, str(path))
    _check_keys(plan, PLAN_KEYS, "the plan")
    _require(plan, PLAN_KEYS, "the plan")

    start_date = _date(plan["start_date"], "start_date")
    freeze_date = _date(plan["freeze_date"], "freeze_date")
    if freeze_date < start_date:
        raise PlanError(f"freeze_date {freeze_date} is before start_date {start_date}")

    phases = _parse_phases(plan["phases"])
    if phases[0].start != start_date:
        raise PlanError(
            f"phase 1 starts {phases[0].start}, which is not the corpus start_date {start_date}"
        )
    if phases[-1].end != freeze_date:
        raise PlanError(
            f"the last phase ends {phases[-1].end}, which is not the freeze date {freeze_date}"
        )

    collected, analysed = _parse_languages(plan["languages"])

    report_dates = tuple(
        _date(value, f"report_dates[{index}]")
        for index, value in enumerate(_sequence(plan["report_dates"], "report_dates"))
    )
    if not report_dates:
        raise PlanError("report_dates is empty, so the run demonstrates no change over time")
    for reported in report_dates:
        if not any(phase.contains(reported) for phase in phases):
            # A Replay refuses a report date outside the corpus, so this is the
            # same refusal made before a run rather than hours into one.
            raise PlanError(
                f"report date {reported.isoformat()} falls outside the arc "
                f"{start_date.isoformat()} to {freeze_date.isoformat()}"
            )

    report_types = _strings(plan["report_types"], "report_types")
    if not report_types:
        raise PlanError("report_types is empty, so a report point produces nothing")
    for report_type in report_types:
        if report_type not in REPORT_TYPES:
            raise PlanError(
                f"report_types names {report_type!r}, which the reporter does "
                f"not produce: {', '.join(sorted(REPORT_TYPES))}"
            )

    stage_days = int(plan["stage_days"])
    if stage_days < 1:
        raise PlanError(f"stage_days must be at least 1 day, found {stage_days}")

    expected_signals = _parse_expected(plan["expected_signals"], phases)
    empty_surfaces = _strings(plan["empty_surfaces"], "empty_surfaces")
    unknown_surfaces = sorted(set(empty_surfaces) - KNOWN_EMPTY_SURFACES)
    if unknown_surfaces:
        raise PlanError(
            f"empty_surfaces names {', '.join(unknown_surfaces)}, which nothing "
            f"knows how to count: {', '.join(sorted(KNOWN_EMPTY_SURFACES))}. An "
            f"unknown surface reports as empty having queried nothing."
        )

    collection = _mapping(plan["collection"], "collection")
    _check_keys(collection, COLLECTION_KEYS, "collection")
    _require(collection, COLLECTION_KEYS, "collection")
    canonical_domain = _optional_text(collection["canonical_domain"], "collection.canonical_domain")
    impostor_domains = _strings(collection["impostor_domains"], "collection.impostor_domains")
    if canonical_domain and canonical_domain in impostor_domains:
        # The build drops an impostor domain's items, so a canonical domain
        # listed as one collects nothing from the movement's own site.
        raise PlanError(
            f"collection.canonical_domain {canonical_domain} is also listed as an impostor domain"
        )

    news = _mapping(collection["news"], "collection.news")
    _check_keys(news, frozenset({"outlets"}), "collection.news")
    _require(news, {"outlets"}, "collection.news")

    social = _mapping(collection["social"], "collection.social")
    _check_keys(social, SOCIAL_KEYS, "collection.social")
    _require(social, SOCIAL_KEYS, "collection.social")
    youtube = _mapping(social["youtube"], "collection.social.youtube")
    _check_keys(youtube, frozenset({"channel_id", "backfill_count"}), "collection.social.youtube")
    _require(youtube, {"channel_id", "backfill_count"}, "collection.social.youtube")
    telegram = _mapping(social["telegram"], "collection.social.telegram")
    _check_keys(telegram, frozenset({"channel"}), "collection.social.telegram")
    x_target = _mapping(social["x"], "collection.social.x")
    _check_keys(x_target, frozenset({"handle"}), "collection.social.x")
    counter = _mapping(social["counter_narrative"], "collection.social.counter_narrative")
    _check_keys(counter, frozenset({"handles"}), "collection.social.counter_narrative")

    output = _mapping(plan["output"], "output")
    _check_keys(output, OUTPUT_KEYS, "output")
    _require(output, OUTPUT_KEYS, "output")

    return CorpusPlan(
        name=_text(plan["name"], "name"),
        issue=int(plan["issue"]),
        epic=int(plan["epic"]),
        start_date=start_date,
        freeze_date=freeze_date,
        collected_languages=collected,
        analysed_languages=analysed,
        phases=phases,
        report_dates=report_dates,
        report_types=report_types,
        stage_days=stage_days,
        expected_signals=expected_signals,
        empty_surfaces=empty_surfaces,
        canonical_domain=canonical_domain,
        impostor_domains=impostor_domains,
        keywords=_strings(collection["keywords"], "collection.keywords"),
        news_outlets=_parse_outlets(news["outlets"]),
        youtube=YouTubeTarget(
            channel_id=_optional_text(
                youtube["channel_id"], "collection.social.youtube.channel_id"
            ),
            backfill_count=int(youtube["backfill_count"]),
        ),
        telegram_channel=_optional_text(
            telegram.get("channel"), "collection.social.telegram.channel"
        ),
        x_handle=_optional_text(x_target.get("handle"), "collection.social.x.handle"),
        counter_narrative_handles=_strings(
            counter.get("handles"), "collection.social.counter_narrative.handles"
        ),
        hand_placed_files=tuple(
            _repo_path(value, f"collection.hand_placed_files[{index}]")
            for index, value in enumerate(
                _sequence(collection["hand_placed_files"], "collection.hand_placed_files")
            )
        ),
        corpus_file=_repo_path(output["corpus_file"], "output.corpus_file"),
        dump_file=_repo_path(output["dump_file"], "output.dump_file"),
    )
