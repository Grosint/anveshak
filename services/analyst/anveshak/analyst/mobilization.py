"""Mobilization lexicon detection — issue #33.

Public content calling for people to assemble surfaces as a signal, with the
date and place extracted and the exact matched phrase always displayed, so
an analyst can verify the extraction and correct it when it is wrong.

The signal reports what was publicly said. It never states that an event
will occur and carries no probability that one will. That is a defensibility
requirement rather than a stylistic one: a cited phrase survives scrutiny,
and a forecast about a political group does not.

Detection is lexicon-first. The patterns live in a versioned YAML file whose
path is a setting, so the customer owns the vocabulary and an analyst can
read exactly what fired a signal. A language model confirmation step is
issue #34 and ships disabled unless it clears its acceptance bar.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import asyncpg
import structlog
import yaml
from anveshak.clock import resolve_reference_time

from .metrics import analyst_signals_fired_total
from .settings import settings
from .signal_writer import SQL_INSERT_SIGNAL, BroadcastFn, is_duplicate_signal

log = structlog.get_logger(__name__)


SCRIPT_LATIN = "latin"
SCRIPT_DEVANAGARI = "devanagari"
# A pattern that is written in neither script, such as one made only of
# digits and punctuation. It is tried on every text, since there is no
# script it could be excluded by.
SCRIPT_ANY = "any"
_KNOWN_SCRIPTS = frozenset({SCRIPT_LATIN, SCRIPT_DEVANAGARI, SCRIPT_ANY})

_RE_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
# Latin letters, including the accented forms a transliteration uses.
_RE_LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]")
# A Devanagari codepoint written as an escape rather than as the character
# itself, which is how a range appears inside a pattern.
_RE_DEVANAGARI_ESCAPE = re.compile(r"\\u09[0-7][0-9A-Fa-f]")
# `\d`, `\s`, `\b` and `\u0041` are Latin characters describing something
# that is not Latin script. A pattern made of them belongs to no script and
# has to be tried on every text, so they are removed before the scan.
_RE_REGEX_ESCAPE = re.compile(r"\\(?:u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2}|[A-Za-z])")


@dataclass(frozen=True)
class LexiconPattern:
    pattern_id: str
    language: str
    # The script the pattern is written in, which is what decides whether it
    # is tried. `language` remains as documentation of which language the
    # phrase belongs to, and it selects nothing.
    script: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Lexicon:
    version: int
    patterns: list[LexiconPattern]
    # Keyed by script rather than by language, for the same reason the
    # patterns are.
    place_markers: dict[str, list[str]]


@dataclass(frozen=True)
class Match:
    """One lexicon hit, carrying the exact text that produced it."""

    pattern_id: str
    language: str
    script: str
    phrase: str


def script_of_source(source: str) -> str:
    """The script a pattern or a marker is written in.

    Used when the lexicon entry does not declare one, so a customer who
    edits the file and omits `script` still gets a pattern that is tried.
    """
    if _RE_DEVANAGARI.search(source):
        return SCRIPT_DEVANAGARI
    # A Latin pattern may carry a Devanagari exclusion written as an escape,
    # so the literal characters above decide before the escapes below do.
    if _RE_LATIN.search(_RE_REGEX_ESCAPE.sub("", source)):
        return SCRIPT_LATIN
    if _RE_DEVANAGARI_ESCAPE.search(source):
        return SCRIPT_DEVANAGARI
    return SCRIPT_ANY


def scripts_in_text(text: str) -> set[str]:
    """Every script the text is actually written in.

    A set, because code-mixed content is normal here: a Devanagari post
    that carries a transliterated slogan is the case this exists for.
    """
    present: set[str] = set()
    if _RE_DEVANAGARI.search(text):
        present.add(SCRIPT_DEVANAGARI)
    if _RE_LATIN.search(text):
        present.add(SCRIPT_LATIN)
    return present


def _resolve_lexicon_path() -> Optional[Path]:
    """Find the lexicon, in the container or in a host checkout.

    Same shape as the geocoder's custom-locations lookup: the configured
    path first, then the two container mount points, then the repository
    root located by its uv.lock marker. Without the last one the file is
    invisible to a test run on a developer machine.
    """
    configured = Path(settings.mobilization_lexicon_path)
    if configured.is_file():
        return configured

    project_root = Path(__file__).resolve().parent
    while project_root != project_root.parent:
        if (project_root / "uv.lock").exists():
            break
        project_root = project_root.parent

    relative = Path("infra/configs/lexicons/mobilization.yaml")
    for candidate in (
        Path("/app") / relative,
        Path("/workspace") / relative,
        project_root / relative,
    ):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_lexicon() -> Lexicon:
    """Read and compile the versioned lexicon file.

    Cached, since it is read once per worker and never changes at runtime.
    A missing or unreadable file logs the reason and yields an empty
    lexicon, so the feature is visibly off rather than quietly absent.
    """
    resolved = _resolve_lexicon_path()
    if resolved is None:
        path = Path(settings.mobilization_lexicon_path)
        log.warning(
            "mobilization.lexicon_missing",
            path=str(path),
            reason="MOBILIZATION_LEXICON_PATH does not exist, detection is disabled",
        )
        return Lexicon(version=0, patterns=[], place_markers={})

    path = resolved
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    patterns: list[LexiconPattern] = []
    for entry in raw.get("patterns", []):
        # Case-insensitive by default, since most content is written either
        # way. A pattern opts out with `case_sensitive: true`, which is how
        # a two-word slogan is told apart from the same two words used as
        # ordinary speech: the slogan is capitalised and the speech is not.
        flags = re.UNICODE if entry.get("case_sensitive") else re.IGNORECASE | re.UNICODE
        try:
            declared = str(entry.get("script", "")).lower()
            if declared not in _KNOWN_SCRIPTS:
                inferred = script_of_source(entry["regex"])
                # An unrecognised script is a value no text can carry, so
                # keeping it would drop the pattern on every item forever
                # with nothing in the logs. The regex decides instead, and
                # the entry says so.
                log.warning(
                    "mobilization.pattern_script_inferred",
                    pattern_id=entry.get("id"),
                    declared=declared or None,
                    script=inferred,
                    reason=(
                        "entry declares no usable script, so it was read off the regex; "
                        f"declare one of {sorted(_KNOWN_SCRIPTS)}"
                    ),
                )
                declared = inferred
            patterns.append(
                LexiconPattern(
                    pattern_id=entry["id"],
                    language=entry["language"],
                    script=declared,
                    regex=re.compile(entry["regex"], flags),
                )
            )
        except (KeyError, re.error) as exc:
            log.warning(
                "mobilization.pattern_invalid",
                pattern_id=entry.get("id"),
                error=str(exc),
            )

    log.info(
        "mobilization.lexicon_loaded",
        version=raw.get("version", 0),
        patterns=len(patterns),
        path=str(path),
    )
    # The file groups markers by language, which is how a person reads
    # them. They are regrouped by script here, since that is what selects
    # them, and two languages sharing a script share their markers.
    markers_by_script: dict[str, list[str]] = defaultdict(list)
    for language, group in (raw.get("place_markers", {}) or {}).items():
        if not isinstance(group, list):
            log.warning(
                "mobilization.place_markers_invalid",
                language=language,
                reason="a marker group must be a list, so this group was skipped",
            )
            continue
        for marker in group:
            markers_by_script[script_of_source(str(marker))].append(str(marker))

    return Lexicon(
        version=int(raw.get("version", 0)),
        patterns=patterns,
        place_markers=dict(markers_by_script),
    )


def find_calls_to_assemble(text: str, *, language: Optional[str]) -> list[Match]:
    """Return every lexicon hit in the text.

    Patterns are selected by the script the text is written in, never by
    the `language` label the detector produced (#56). Every transliterated
    pattern in the lexicon is tagged `en`, and Latin-script Hinglish is
    exactly the content a detector tends to label `hi`, so selecting on the
    label hid those patterns from the content they were written for.

    `language` is accepted and deliberately not used for selection. It is
    logged when it disagrees with what actually matched, so the disagreement
    is visible rather than assumed away.

    Text in no recognised script tries every pattern, which is the property
    #33 wrote for a mislabelled item and this change keeps.
    """
    if not text or not text.strip():
        return []

    # The patterns come from a file the design hands to the customer to edit.
    # An unbounded input turns one badly written pattern into a stalled
    # signal engine, since these run synchronously on its event loop.
    text = text[: settings.mobilization_max_text_chars]

    lexicon = load_lexicon()
    scripts = scripts_in_text(text)
    if scripts:
        candidates = [
            pattern
            for pattern in lexicon.patterns
            if pattern.script in scripts or pattern.script == SCRIPT_ANY
        ]
    else:
        # A script this file knows nothing about, Bengali or Tamil or an
        # item of digits alone. Every pattern is tried, which is the
        # property #33 wrote for content the labelling got wrong.
        log.info(
            "mobilization.unknown_script",
            reason="the text is in no script the lexicon covers, so every pattern was tried",
        )
        candidates = lexicon.patterns

    matches: list[Match] = []
    for pattern in candidates:
        found = pattern.regex.search(text)
        if found:
            matches.append(
                Match(
                    pattern_id=pattern.pattern_id,
                    language=pattern.language,
                    script=pattern.script,
                    phrase=_surrounding_phrase(text, found.start(), found.end()),
                )
            )

    unreachable_by_label = sorted(
        {match.pattern_id for match in matches if match.language != (language or "").lower()}
    )
    if language and unreachable_by_label:
        log.info(
            "mobilization.label_would_have_hidden_match",
            label=language.lower(),
            scripts=sorted(scripts),
            pattern_ids=unreachable_by_label,
            reason="selection is by script, so a pattern the label excludes was still tried",
        )
    return matches


def _surrounding_phrase(text: str, start: int, end: int) -> str:
    """The sentence containing the match, so an analyst reads it in context.

    The exact matched span alone is often two words, which is not something
    anyone can verify. The sentence is.
    """
    left = max(
        text.rfind(".", 0, start),
        text.rfind("।", 0, start),
        text.rfind("\n", 0, start),
    )
    right_candidates = [
        pos for pos in (text.find(".", end), text.find("।", end), text.find("\n", end)) if pos != -1
    ]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right].strip()


# ---------------------------------------------------------------------------
# Date and place extraction
# ---------------------------------------------------------------------------

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_RE_MONTH_DAY = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b", re.IGNORECASE)
_RE_DAY_MONTH = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)
_RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# Relative expressions, in both languages. These are the hard part, and they
# are handled explicitly rather than by a general parser so that an
# unrecognised expression yields None rather than a wrong date.
_RELATIVE_DAYS = {
    "today": 0,
    "tonight": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
    "आज": 0,
    "कल": 1,
    "परसों": 2,
}


def extract_date(text: str, *, today: Optional[date] = None) -> Optional[date]:
    """Return the date the content names, or None.

    None rather than a guess. A wrong date on a mobilization signal is worse
    than no date, because the card always shows the phrase and an analyst
    can read the date out of it themselves.
    """
    if not text:
        return None
    # The same bound the detection path applies, for the same reason: the
    # item is untrusted scraped text and this runs on the signal engine's
    # event loop.
    text = text[: settings.mobilization_max_text_chars]
    reference = today or date.today()
    lowered = text.lower()

    iso = _RE_ISO.search(text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    month_day = _RE_MONTH_DAY.search(lowered)
    if month_day:
        return _safe_date(reference.year, _MONTHS[month_day.group(1)], int(month_day.group(2)))

    day_month = _RE_DAY_MONTH.search(lowered)
    if day_month:
        return _safe_date(reference.year, _MONTHS[day_month.group(2)], int(day_month.group(1)))

    # Longest first, so "day after tomorrow" is not read as "tomorrow".
    for expression in sorted(_RELATIVE_DAYS, key=len, reverse=True):
        if expression in lowered or expression in text:
            return reference + timedelta(days=_RELATIVE_DAYS[expression])

    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_place(text: str, *, language: Optional[str]) -> Optional[str]:
    """Return the place named after a location marker, or None.

    Deliberately shallow. It locates the words following a marker so the
    card has something to show; the matched phrase remains the evidence, and
    an analyst corrects the place when this gets it wrong.

    Markers are selected by script, for the reason detection is (#56): an
    item whose label contradicts its script would otherwise be read with
    the wrong marker set and lose its place.
    """
    if not text:
        return None

    text = text[: settings.mobilization_max_text_chars]
    lexicon = load_lexicon()
    scripts = scripts_in_text(text)

    # Code-mixed text carries markers from both scripts, and the English
    # ones are the longer strings, so a length-ordered sweep would let the
    # Latin footer of a Devanagari post name the place. The script the item
    # is mostly written in goes first, and length orders within a script.
    ordered_scripts = sorted(
        scripts or set(lexicon.place_markers), key=lambda s: _script_weight(text, s), reverse=True
    )
    markers: list[str] = []
    for script in [*ordered_scripts, SCRIPT_ANY]:
        markers.extend(sorted(lexicon.place_markers.get(script, []), key=len, reverse=True))

    for marker in markers:
        found = _place_pattern(marker).search(text)
        if found:
            place = found.group(1).strip(" .,।")
            if place:
                return place
    return None


def _script_weight(text: str, script: str) -> int:
    """How much of the text is written in this script."""
    if script == SCRIPT_DEVANAGARI:
        return len(_RE_DEVANAGARI.findall(text))
    if script == SCRIPT_LATIN:
        return len(_RE_LATIN.findall(text))
    return 0


# Unbounded rather than a literal, since the number of markers is whatever the
# customer's file has. A bound smaller than that recompiles every marker on
# every content item.
@lru_cache(maxsize=None)
def _place_pattern(marker: str) -> re.Pattern[str]:
    """Compile a place marker once rather than on every call."""
    if marker.isascii():
        return re.compile(r"\b" + re.escape(marker) + r"\s+((?:[A-Z][\w'-]*\s?){1,4})", re.UNICODE)
    return re.compile(re.escape(marker) + r"\s*([^\s।.,]+(?:\s+[^\s।.,]+)?)", re.UNICODE)


def build_description(
    *,
    phrase: str,
    when: Optional[date],
    place: Optional[str],
    item_count: int,
) -> str:
    """State what was publicly said.

    The phrase always appears, whether or not a date and place were
    extracted, because the phrase is the evidence and the extractions are
    conveniences an analyst may need to correct.

    Nothing here says an event will occur.
    """
    parts = [f"Public call to assemble in {item_count} item{'s' if item_count != 1 else ''}."]
    if when is not None:
        parts.append(f"Date stated: {when.isoformat()}.")
    if place:
        parts.append(f"Place stated: {place}.")
    parts.append(f'Matched phrase: "{phrase}"')
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Signal check
# ---------------------------------------------------------------------------

SQL_ACTIVE_TOPIC_IDS = """
    SELECT id FROM topics WHERE status = 'active' ORDER BY id
"""

# Scanned per topic rather than globally.
#
# A single global LIMIT ordered by cluster UUID cut the corpus at an
# arbitrary but stable point: once one organisation's volume filled the
# window, organisations whose cluster UUIDs sorted later never had their
# content examined, on every pass, with no log. That is a cross-tenant
# denial of detection rather than a leak, and it is exactly the silent
# failure class this codebase is written against.
SQL_UNCHECKED_CLUSTER_CONTENT = """
    SELECT nc.id                       AS cluster_id,
           nc.topic_id,
           nc.label,
           ci.id                       AS content_item_id,
           ci.language,
           COALESCE(NULLIF(ci.clean_text, ''), ci.raw_text) AS work_text
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    JOIN content_items ci ON ci.narrative_cluster_id = nc.id
    WHERE nc.topic_id = $1
      AND t.status = 'active'
      AND nc.archived_at IS NULL
      AND ci.org_id = t.org_id
      AND ci.captured_at >= $4::timestamptz - make_interval(days => $2)
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    ORDER BY ci.captured_at DESC
    LIMIT $3
"""

_SIGNAL_TYPE_MOBILIZATION = "mobilization_call"


async def check_mobilization_calls(
    pool: asyncpg.Pool,
    broadcast: BroadcastFn,
    reference_time: datetime | None = None,
) -> int:
    """One pass over recent clustered content. Returns count of signals fired.

    Groups hits by cluster and fires once per cluster, deduplicated by the
    same 24h window every other signal uses.

    reference_time is the time this pass treats as now. It bounds the content
    window, anchors dedup, stamps the Signal, and resolves a relative date in
    the matched text such as "kal", so a Replay reads the date the content
    meant. Defaults to the current time. See ADR 0003.
    """
    lexicon = load_lexicon()
    if not lexicon.patterns:
        log.info(
            "mobilization.disabled",
            reason="lexicon is empty, so no call to assemble can be detected",
        )
        return 0

    fired = 0
    now = resolve_reference_time(reference_time)
    async with pool.acquire() as conn:
        topic_ids = [r["id"] for r in await conn.fetch(SQL_ACTIVE_TOPIC_IDS)]

        by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for topic_id in topic_ids:
            rows = await conn.fetch(
                SQL_UNCHECKED_CLUSTER_CONTENT,
                topic_id,
                settings.mobilization_window_days,
                settings.mobilization_max_items_per_topic,
                now,
            )
            if len(rows) == settings.mobilization_max_items_per_topic:
                log.warning(
                    "mobilization.topic_scan_truncated",
                    topic_id=topic_id,
                    limit=settings.mobilization_max_items_per_topic,
                    reason="more recent content than one pass examines",
                )
            for row in rows:
                matches = find_calls_to_assemble(row["work_text"], language=row["language"])
                if matches:
                    by_cluster[row["cluster_id"]].append({"row": dict(row), "match": matches[0]})

        # One ARQ pool for the whole pass. Opening one per fired signal and
        # never closing it leaked a pool for the lifetime of the process.
        confirm_redis = None
        if settings.mobilization_confirm_enabled and by_cluster:
            try:
                from arq import create_pool

                from .jobs import WorkerSettings

                confirm_redis = await create_pool(WorkerSettings.redis_settings)
            except Exception as exc:
                log.warning("mobilization.confirm_pool_failed", error=str(exc))

        for cluster_id, hits in by_cluster.items():
            if len(hits) < settings.mobilization_min_items:
                continue
            if await is_duplicate_signal(conn, cluster_id, _SIGNAL_TYPE_MOBILIZATION, now):
                continue

            first = hits[0]
            phrase = first["match"].phrase
            work_text = first["row"]["work_text"]
            language = first["row"]["language"]

            when = extract_date(work_text, today=now.date())
            place = extract_place(work_text, language=language)

            description = build_description(
                phrase=phrase, when=when, place=place, item_count=len(hits)
            )
            evidence = {
                "cluster_id": cluster_id,
                "matched_phrase": phrase,
                "pattern_id": first["match"].pattern_id,
                "lexicon_version": lexicon.version,
                "extracted_date": when.isoformat() if when else None,
                "extracted_place": place,
                "item_count": len(hits),
                "content_item_ids": [h["row"]["content_item_id"] for h in hits],
                # Nothing here forecasts. The date and place are what the
                # content stated, and the phrase is there so an analyst can
                # check both and correct them.
                "reports": "what was publicly said",
            }

            signal_id = str(uuid.uuid4())
            await conn.execute(
                SQL_INSERT_SIGNAL,
                signal_id,
                first["row"]["topic_id"],
                cluster_id,
                _SIGNAL_TYPE_MOBILIZATION,
                description,
                json.dumps(evidence),
                now,
            )
            analyst_signals_fired_total.labels(severity="MEDIUM").inc()

            try:
                await broadcast(
                    {
                        "type": "signal",
                        "signal_id": signal_id,
                        "topic_id": first["row"]["topic_id"],
                        "cluster_id": cluster_id,
                        "cluster_label": first["row"]["label"],
                        "severity": "MEDIUM",
                        "signal_type": _SIGNAL_TYPE_MOBILIZATION,
                        "description": description,
                    }
                )
            except Exception as exc:
                log.warning("mobilization.broadcast_failed", signal_id=signal_id, error=str(exc))

            # Confirmation runs only on the ids the lexicon flagged, as a
            # background job. A no-op while the flag is off (#34).
            #
            # It carries no reference time, and that is deliberate: it writes
            # no detection output row, only a label onto a content item that
            # already exists. The Signal above is what carries the date the
            # evidence existed. See ADR 0003.
            if confirm_redis is not None:
                try:
                    await confirm_redis.enqueue_job(
                        "confirm_mobilization_job",
                        [h["row"]["content_item_id"] for h in hits],
                        _queue_name="arq:analyst",
                    )
                except Exception as exc:
                    log.warning(
                        "mobilization.confirm_enqueue_failed",
                        cluster_id=cluster_id,
                        error=str(exc),
                    )

            log.info(
                "mobilization.signal_fired",
                signal_id=signal_id,
                cluster_id=cluster_id,
                pattern_id=first["match"].pattern_id,
                item_count=len(hits),
                extracted_date=when.isoformat() if when else None,
            )
            fired += 1

        if confirm_redis is not None:
            await confirm_redis.close()

    return fired
