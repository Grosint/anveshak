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

import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from .settings import settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LexiconPattern:
    pattern_id: str
    language: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class Lexicon:
    version: int
    patterns: list[LexiconPattern]
    place_markers: dict[str, list[str]]


@dataclass(frozen=True)
class Match:
    """One lexicon hit, carrying the exact text that produced it."""

    pattern_id: str
    language: str
    phrase: str


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
        try:
            patterns.append(
                LexiconPattern(
                    pattern_id=entry["id"],
                    language=entry["language"],
                    regex=re.compile(entry["regex"], re.IGNORECASE | re.UNICODE),
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
    return Lexicon(
        version=int(raw.get("version", 0)),
        patterns=patterns,
        place_markers=raw.get("place_markers", {}),
    )


def find_calls_to_assemble(text: str, *, language: Optional[str]) -> list[Match]:
    """Return every lexicon hit in the text.

    An unknown language tries every pattern. Detection must not depend on
    language detection having been right, since a mislabelled item would
    otherwise be silently skipped.
    """
    if not text or not text.strip():
        return []

    lexicon = load_lexicon()
    candidates = [
        pattern
        for pattern in lexicon.patterns
        if language is None or pattern.language == language.lower()
    ]
    if not candidates:
        candidates = lexicon.patterns

    matches: list[Match] = []
    for pattern in candidates:
        found = pattern.regex.search(text)
        if found:
            matches.append(
                Match(
                    pattern_id=pattern.pattern_id,
                    language=pattern.language,
                    phrase=_surrounding_phrase(text, found.start(), found.end()),
                )
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
    """
    if not text:
        return None

    lexicon = load_lexicon()
    markers = lexicon.place_markers.get((language or "en").lower(), [])
    if not markers:
        markers = [m for group in lexicon.place_markers.values() for m in group]

    for marker in sorted(markers, key=len, reverse=True):
        pattern = re.compile(
            r"\b" + re.escape(marker) + r"\s+((?:[A-Z][\w'-]*\s?){1,4})"
            if marker.isascii()
            else re.escape(marker) + r"\s*([^\s।.,]+(?:\s+[^\s।.,]+)?)",
            re.UNICODE,
        )
        found = pattern.search(text)
        if found:
            place = found.group(1).strip(" .,।")
            if place:
                return place
    return None


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
    WHERE t.status = 'active'
      AND nc.archived_at IS NULL
      AND ci.captured_at >= NOW() - make_interval(days => $1)
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    ORDER BY nc.id, ci.captured_at DESC
    LIMIT $2
"""

_SIGNAL_TYPE_MOBILIZATION = "mobilization_call"


async def check_mobilization_calls(pool: Any, broadcast: Any) -> int:
    """One pass over recent clustered content. Returns count of signals fired.

    Groups hits by cluster and fires once per cluster, deduplicated by the
    same 24h window every other signal uses.
    """
    import json
    import uuid
    from collections import defaultdict
    from datetime import UTC, datetime

    from .metrics import analyst_signals_fired_total
    from .signal_engine import SQL_INSERT_SIGNAL, is_duplicate_signal

    lexicon = load_lexicon()
    if not lexicon.patterns:
        log.info(
            "mobilization.disabled",
            reason="lexicon is empty, so no call to assemble can be detected",
        )
        return 0

    fired = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SQL_UNCHECKED_CLUSTER_CONTENT,
            settings.mobilization_window_days,
            settings.mobilization_max_items_per_pass,
        )

        by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            matches = find_calls_to_assemble(row["work_text"], language=row["language"])
            if matches:
                by_cluster[row["cluster_id"]].append(
                    {
                        "row": dict(row),
                        "match": matches[0],
                    }
                )

        for cluster_id, hits in by_cluster.items():
            if len(hits) < settings.mobilization_min_items:
                continue
            if await is_duplicate_signal(conn, cluster_id, _SIGNAL_TYPE_MOBILIZATION):
                continue

            first = hits[0]
            phrase = first["match"].phrase
            work_text = first["row"]["work_text"]
            language = first["row"]["language"]

            when = extract_date(work_text)
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
            now = datetime.now(UTC)
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

            log.info(
                "mobilization.signal_fired",
                signal_id=signal_id,
                cluster_id=cluster_id,
                pattern_id=first["match"].pattern_id,
                item_count=len(hits),
                extracted_date=when.isoformat() if when else None,
            )
            fired += 1

    return fired
