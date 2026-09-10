"""Publication Time extraction from an article document - issue #42.

Backfilled content has no reliable Publication Time unless the document asserts
one, and the signals available differ by outlet. This module is the single
extraction path: one pure function, a documented precedence order, and a
per-source timezone policy. Adding an outlet is configuration, not a parser.

Precedence, highest first:

1. JSON-LD ``datePublished`` on an article node
2. the article published time meta tag, on either ``name`` or ``property``
3. any other date meta tag from ``_DATE_META_NAMES``
4. a ``time`` element, or an epoch in a data attribute
5. a date encoded in the URL path

A candidate that cannot be resolved to an instant is no candidate, so a naive
JSON-LD value defers to a lower signal that carries an explicit offset. That is
strictly better data than returning nothing.

Naive values are refused unless the source configuration declares what zone the
outlet means. The registry denies by default, in the shape ``EXEMPT_MODELS`` in
``scripts/verify_labels.py`` uses: a declaration carries a reason, and silence
is a configuration gap that gets logged rather than guessed at. The failure this
prevents is a five and a half hour shift, which moves roughly a quarter of items
into the wrong day bucket and depresses the per-day independent source count
that Signal thresholds fire on.

Visible date text is never a signal. At least one outlet formats an epoch in UTC
and labels the result IST, so its rendered date is wrong by a fixed offset while
its machine-readable value is correct.

Wayback capture time is not a date signal either. It is admissible only as an
impossibility check, because an archive cannot capture a page before it exists.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Signal names - recorded alongside the date so an analyst can weigh it
# ---------------------------------------------------------------------------

SIGNAL_JSONLD_DATE_PUBLISHED = "jsonld_date_published"
SIGNAL_META_ARTICLE_PUBLISHED_TIME = "meta_article_published_time"
SIGNAL_META_DATE = "meta_date"
SIGNAL_TIME_ELEMENT_DATETIME = "time_element_datetime"
SIGNAL_TIME_ELEMENT_EPOCH = "time_element_epoch"
SIGNAL_URL_PATH_DATE = "url_path_date"

# Key under which the signal name is written into the content labels structure,
# alongside the other derived metadata that lives there.
PUBLICATION_TIME_SIGNAL_LABEL = "publication_time_signal"


# ---------------------------------------------------------------------------
# Per-source timezone policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceTimezonePolicy:
    """What a naive timestamp from one outlet actually means.

    zone is an IANA name. reason records why the outlet needs a declaration,
    because a declaration without one cannot be reviewed later.
    """

    zone: str
    reason: str


# Deny by default. An outlet absent from here has its naive timestamps refused,
# which surfaces the gap instead of shifting its content by the offset of
# whichever assumption was baked in. Entries are added as outlets enter the
# corpus, each recording the observation that justifies it.
NAIVE_TIMESTAMP_ZONES: dict[str, SourceTimezonePolicy] = {}


@dataclass(frozen=True)
class SourceConfig:
    """Everything extraction needs about the outlet that served the document.

    url is the document's own URL, which is both the registry key and the last
    date signal. naive_timezone is the IANA zone a naive timestamp means, or
    None when the outlet has declared nothing.
    """

    url: str
    naive_timezone: Optional[str] = None


@dataclass(frozen=True)
class ExtractedPublicationTime:
    """A publication instant in UTC, and the name of the signal that produced it."""

    instant: datetime
    signal: str


def source_config_for(
    url: str,
    registry: Optional[Mapping[str, SourceTimezonePolicy]] = None,
) -> SourceConfig:
    """Build the extraction configuration for a document URL.

    Lookup is by host, lowercased and with a leading ``www.`` removed, because
    an outlet serves the same markup under both.
    """
    policies = NAIVE_TIMESTAMP_ZONES if registry is None else registry
    host = urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")
    policy = policies.get(host)
    return SourceConfig(url=url, naive_timezone=policy.zone if policy else None)


def publication_time_labels(
    extracted: Optional[ExtractedPublicationTime],
) -> dict[str, str]:
    """Return the labels fragment recording which signal produced the date.

    Empty when there is no date, so a caller merges it unconditionally and an
    item with no recoverable date carries no claim about one.
    """
    if extracted is None:
        return {}
    return {PUBLICATION_TIME_SIGNAL_LABEL: extracted.signal}


# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

# schema.org article types seen carrying datePublished. Not only NewsArticle:
# at least one major outlet publishes ReportageNewsArticle, and opinion desks
# use BlogPosting. WebPage is deliberately absent, because outlets attach a
# site-wide or template date to it.
_ARTICLE_TYPES = frozenset(
    {
        "newsarticle",
        "article",
        "reportagenewsarticle",
        "analysisnewsarticle",
        "backgroundnewsarticle",
        "opinionnewsarticle",
        "reviewnewsarticle",
        "blogposting",
        "liveblogposting",
    }
)

_ARTICLE_PUBLISHED_META = ("article:published_time", "article:published")

# Tried in this order, so the answer does not depend on where an outlet happens
# to put its tags in the head.
_DATE_META_NAMES = (
    "publish-date",
    "publish_date",
    "published-date",
    "publishdate",
    "pubdate",
    "og:published_time",
    "datepublished",
    "dc.date.issued",
    "dcterms.date",
    "dc.date",
    "parsely-pub-date",
    "sailthru.date",
    "cxenseparse:recs:publishtime",
    "article.published",
    "article_date_original",
    "date",
    "timestamp",
)

_DATETIME_ATTRS = ("datetime", "data-datetime", "data-date-published")
_EPOCH_ATTRS = ("data-epoch", "data-timestamp", "data-time", "data-ts", "data-published-epoch")

# Named zones outlets append in place of a numeric offset. Anything outside this
# map is a parse failure rather than a token to drop, because dropping it would
# leave a naive value that looks successfully parsed.
#
# This map is India-scoped: IST here is Asia/Kolkata, not Israel or Ireland,
# which share the abbreviation. The corpus is Indian outlets, and an abbreviation
# is ambiguous by nature, so an outlet outside that set that emits a pseudo-zone
# needs its token resolved through its own declaration rather than through here.
_NAMED_ZONES = {
    "IST": timedelta(hours=5, minutes=30),
    "UTC": timedelta(0),
    "GMT": timedelta(0),
    "Z": timedelta(0),
}

_SINGLE_DIGIT_OFFSET_RE = re.compile(r"([+-])(\d):(\d{2})$")
_URL_PATH_DATE_RES = (
    re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$|[^\d])"),
    re.compile(r"/(\d{4})-(\d{2})-(\d{2})(?:/|$|[^\d])"),
)

# Epochs outside this range are counters, identifiers or truncated values rather
# than timestamps.
_EPOCH_MIN = datetime(2000, 1, 1, tzinfo=UTC).timestamp()
_EPOCH_MAX = datetime(2100, 1, 1, tzinfo=UTC).timestamp()

# An outlet's clock and an archive crawler's clock disagree by seconds, and an
# outlet may touch datePublished as it republishes. Only a claim beyond this
# tolerance is impossible rather than merely imprecise.
_ARCHIVE_SKEW_GRACE = timedelta(minutes=15)

# Every input here is adversarial scraped markup, so each reader is bounded.
#
# A timestamp is about 35 characters in either grammar, so anything longer is
# not one. Without this bound a multi-kilobyte attribute value reaches the
# string parsers, which is the cheapest denial of service the module offers.
_MAX_TIMESTAMP_CHARS = 64
# Article nodes in one document. A page with more than this is not a page.
_MAX_JSONLD_CANDIDATES = 32
# json.loads recurses in C and raises RecursionError before _walk_jsonld's own
# depth cap can apply, so bound the payload before parsing it.
_MAX_JSONLD_PAYLOAD_BYTES = 512 * 1024
_MAX_JSONLD_NESTING = 12
# Default ceiling on the whole document. Overridable per call, because the
# fetcher that produced the document knows its own limit.
_MAX_DOCUMENT_CHARS = 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def _parse_raw(raw: str) -> Optional[tuple[datetime, bool]]:
    """Parse one raw timestamp string.

    Returns the parsed value and whether it carried an explicit zone, or None
    when the string is not a timestamp at all. The parsed value may be naive;
    resolving that is the caller's decision, because it needs the source
    configuration.
    """
    text = raw.strip()
    if not text or len(text) > _MAX_TIMESTAMP_CHARS:
        return None

    # A single-digit offset hour, such as "+5:30", which ISO parsing rejects.
    text = _SINGLE_DIGIT_OFFSET_RE.sub(r"\g<1>0\g<2>:\g<3>", text)

    parsed = _parse_datetime_string(text)
    if parsed is not None:
        return parsed, parsed.tzinfo is not None

    # A trailing pseudo-zone, such as "2026-07-20 15:04:05 IST", which is not
    # valid in either grammar. An unrecognised token is a parse failure rather
    # than a token to drop, because dropping it leaves a naive value that looks
    # successfully parsed. Split rather than match, because a regex anchored on
    # a trailing whitespace run backtracks quadratically over an adversarial one.
    parts = text.rsplit(maxsplit=1)
    if len(parts) != 2:
        return None
    head, token = parts
    if not token.isalpha() or len(token) > 5:
        return None
    offset = _NAMED_ZONES.get(token.upper())
    if offset is None:
        return None
    without_zone = _parse_datetime_string(head.strip())
    if without_zone is None:
        return None
    if without_zone.tzinfo is not None:
        return without_zone, True
    return without_zone.replace(tzinfo=UTC) - offset, True


def _parse_datetime_string(text: str) -> Optional[datetime]:
    """Parse a timestamp in either grammar outlets use, ISO 8601 or RFC 2822."""
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    # Some outlets put an RFC 2822 date in a meta tag, the same shape an RSS
    # pubDate carries. Its zone token is part of that grammar.
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None


def _resolve(
    parsed: tuple[datetime, bool],
    source: SourceConfig,
    signal: str,
) -> Optional[datetime]:
    """Turn a parsed value into a UTC instant, or refuse it.

    A value carrying an offset converts. A naive value converts only when the
    outlet has declared what it means.
    """
    value, has_offset = parsed
    if has_offset:
        return value.astimezone(UTC)

    if not source.naive_timezone:
        log.info(
            "publication_time.naive_without_declared_timezone",
            url=source.url,
            signal=signal,
            reason="outlet has no entry in NAIVE_TIMESTAMP_ZONES",
        )
        return None

    try:
        zone = ZoneInfo(source.naive_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning(
            "publication_time.unknown_declared_timezone",
            url=source.url,
            signal=signal,
            zone=source.naive_timezone,
        )
        return None

    return value.replace(tzinfo=zone).astimezone(UTC)


def _candidate(raw: str, source: SourceConfig, signal: str) -> Optional[datetime]:
    """Parse and resolve one raw value, logging a failure rather than swallowing it."""
    parsed = _parse_raw(raw)
    if parsed is None:
        log.warning(
            "publication_time.unparseable_value",
            url=source.url,
            signal=signal,
            raw=raw[:64],
        )
        return None
    return _resolve(parsed, source, signal)


def _epoch_to_instant(raw: str) -> Optional[datetime]:
    """Read an epoch in seconds or milliseconds. Always UTC, so never naive."""
    digits = raw.strip()
    # isdecimal rather than isdigit: superscripts and other Unicode digits pass
    # isdigit and then raise in float(), which would take the whole extraction
    # down over a four-byte attribute value.
    if not digits.isdecimal() or len(digits) > _MAX_TIMESTAMP_CHARS:
        return None
    try:
        value = float(digits)
    except ValueError:
        return None
    if len(digits) >= 13:
        value /= 1000.0
    if not _EPOCH_MIN <= value <= _EPOCH_MAX:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


# ---------------------------------------------------------------------------
# Signal readers, in precedence order
# ---------------------------------------------------------------------------


def _walk_jsonld(node: Any, found: list[str], url: str, depth: int = 0) -> None:
    """Collect datePublished from every article node, including inside @graph.

    Both bounds report themselves. A truncated walk that returned silently
    would read downstream as "this outlet publishes no date" rather than as
    "the parser gave up", which is the wrong thing to go and investigate.
    """
    if len(found) >= _MAX_JSONLD_CANDIDATES:
        return
    if depth > _MAX_JSONLD_NESTING:
        log.info(
            "publication_time.jsonld_too_deep",
            url=url,
            limit=_MAX_JSONLD_NESTING,
        )
        return
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, found, url, depth + 1)
        return
    if not isinstance(node, dict):
        return

    declared = node.get("@type")
    types = declared if isinstance(declared, list) else [declared]
    is_article = any(isinstance(t, str) and t.lower() in _ARTICLE_TYPES for t in types)
    published = node.get("datePublished")
    if is_article and isinstance(published, str):
        found.append(published)
        if len(found) >= _MAX_JSONLD_CANDIDATES:
            log.info(
                "publication_time.jsonld_candidate_cap_reached",
                url=url,
                limit=_MAX_JSONLD_CANDIDATES,
            )
            return

    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_jsonld(value, found, url, depth + 1)


def _from_jsonld(soup: BeautifulSoup, source: SourceConfig) -> Optional[datetime]:
    raws: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        payload = (script.string or script.get_text() or "").strip()
        payload = payload.removeprefix("<!--").removesuffix("-->").strip()
        if not payload:
            continue
        if len(payload) > _MAX_JSONLD_PAYLOAD_BYTES:
            log.warning(
                "publication_time.jsonld_oversize",
                url=source.url,
                size=len(payload),
                limit=_MAX_JSONLD_PAYLOAD_BYTES,
            )
            continue
        try:
            document = json.loads(payload)
        # RecursionError is a RuntimeError, so nesting deep enough to exhaust
        # the C scanner's stack escapes a ValueError-only guard.
        except (json.JSONDecodeError, ValueError, RecursionError):
            log.warning("publication_time.jsonld_unparseable", url=source.url)
            continue
        _walk_jsonld(document, raws, source.url)
        if len(raws) >= _MAX_JSONLD_CANDIDATES:
            break

    # Blocks disagree in practice. The one carrying an explicit offset is the
    # one the outlet's own templating produced from a real instant. Parse once
    # and keep the result, rather than parsing again to resolve it.
    with_offset: list[tuple[datetime, bool]] = []
    without_offset: list[tuple[datetime, bool]] = []
    unparseable = 0
    for raw in raws:
        parsed = _parse_raw(raw)
        if parsed is None:
            unparseable += 1
            continue
        (with_offset if parsed[1] else without_offset).append(parsed)

    if unparseable:
        log.warning(
            "publication_time.unparseable_value",
            url=source.url,
            signal=SIGNAL_JSONLD_DATE_PUBLISHED,
            count=unparseable,
        )

    for parsed in with_offset + without_offset:
        instant = _resolve(parsed, source, SIGNAL_JSONLD_DATE_PUBLISHED)
        if instant is not None:
            return instant
    return None


def _meta_content(soup: BeautifulSoup, wanted: str) -> Optional[str]:
    """Read a meta tag by name or property, matched case-insensitively."""
    for tag in soup.find_all("meta"):
        for attr in ("name", "property", "itemprop", "http-equiv"):
            value = tag.get(attr)
            if isinstance(value, str) and value.strip().lower() == wanted:
                content = tag.get("content")
                if isinstance(content, str) and content.strip():
                    return content
    return None


def _from_article_meta(soup: BeautifulSoup, source: SourceConfig) -> Optional[datetime]:
    for name in _ARTICLE_PUBLISHED_META:
        raw = _meta_content(soup, name)
        if raw is None:
            continue
        instant = _candidate(raw, source, SIGNAL_META_ARTICLE_PUBLISHED_TIME)
        if instant is not None:
            return instant
    return None


def _from_date_meta(soup: BeautifulSoup, source: SourceConfig) -> Optional[datetime]:
    for name in _DATE_META_NAMES:
        raw = _meta_content(soup, name)
        if raw is None:
            continue
        # A few outlets put an epoch in a meta tag. The signal stays meta_date,
        # because a meta tag is the article's own head either way, and it is the
        # location rather than the encoding that tells an analyst how much to
        # trust the value.
        epoch = _epoch_to_instant(raw)
        if epoch is not None:
            return epoch
        instant = _candidate(raw, source, SIGNAL_META_DATE)
        if instant is not None:
            return instant
    return None


def _attr_case_insensitive(tag: Any, wanted: str) -> Optional[str]:
    """Read an attribute whatever its case, since outlets write camel case."""
    for key, value in tag.attrs.items():
        if key.lower() == wanted and isinstance(value, str) and value.strip():
            return value
    return None


def _from_time_element(soup: BeautifulSoup, source: SourceConfig) -> Optional[tuple[datetime, str]]:
    """Read a time element's machine-readable value, never its rendered text.

    Only ``time`` elements are read. The data attributes below also name comment
    timestamps, live-blog entries, related-article cards, video players and ad
    slots, so a document-wide sweep for them returns some other thing's date
    under a signal name that claims it is the article's. That is the invented
    history user story 3 exists to prevent, and it is worse than a timezone
    error, because a comment can be months away rather than hours.
    """
    elements = soup.find_all("time")

    for attr in _DATETIME_ATTRS:
        for tag in elements:
            raw = _attr_case_insensitive(tag, attr)
            if raw is None:
                continue
            epoch = _epoch_to_instant(raw)
            if epoch is not None:
                return epoch, SIGNAL_TIME_ELEMENT_EPOCH
            instant = _candidate(raw, source, SIGNAL_TIME_ELEMENT_DATETIME)
            if instant is not None:
                return instant, SIGNAL_TIME_ELEMENT_DATETIME

    # One outlet exposes only an epoch in a data attribute and no datetime
    # attribute, and renders a visible date that is wrong by a fixed offset.
    for attr in _EPOCH_ATTRS:
        for tag in elements:
            raw = _attr_case_insensitive(tag, attr)
            if raw is None:
                continue
            epoch = _epoch_to_instant(raw)
            if epoch is not None:
                return epoch, SIGNAL_TIME_ELEMENT_EPOCH
            # An ISO string in a data attribute is a datetime, not an epoch, so
            # it is reported under the signal that names what was read.
            instant = _candidate(raw, source, SIGNAL_TIME_ELEMENT_DATETIME)
            if instant is not None:
                return instant, SIGNAL_TIME_ELEMENT_DATETIME
    return None


def _from_url_path(source: SourceConfig) -> Optional[datetime]:
    """Read a date encoded in the URL path.

    A path date carries no time and no zone, so it is a naive value like any
    other and is refused unless the outlet has declared a zone.
    """
    path = urlparse(source.url).path
    for pattern in _URL_PATH_DATE_RES:
        match = pattern.search(path)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        try:
            midnight = datetime(year, month, day)
        except ValueError:
            continue
        instant = _resolve((midnight, False), source, SIGNAL_URL_PATH_DATE)
        if instant is not None:
            return instant
    return None


# ---------------------------------------------------------------------------
# The extraction function
# ---------------------------------------------------------------------------


def extract_publication_time(
    document: str,
    source: SourceConfig,
    *,
    first_archive_capture: Optional[datetime] = None,
    max_document_chars: int = _MAX_DOCUMENT_CHARS,
) -> Optional[ExtractedPublicationTime]:
    """Extract the Publication Time an article document asserts.

    Returns the instant in UTC with the name of the signal that produced it, or
    None when nothing is recoverable. None means unknown and stays unknown: the
    caller stores a null Publication Time rather than a guess.

    first_archive_capture, when given, is the first Wayback capture of this URL.
    It is not a date signal. It only rejects a claimed publication time later
    than the capture, which cannot have happened. The whole extraction is
    refused rather than annotated, because a value known to be impossible is
    not evidence, and unknown beats wrong on a timeline.

    max_document_chars bounds the markup this will parse at all. The document is
    adversarial scraped input, and the fetcher that produced it knows its own
    limit, so a caller reading one from settings passes it here.
    """
    if len(document) > max_document_chars:
        log.warning(
            "publication_time.document_too_large",
            url=source.url,
            size=len(document),
            limit=max_document_chars,
        )
        return None

    soup = BeautifulSoup(document or "", "lxml")

    instant = _from_jsonld(soup, source)
    signal = SIGNAL_JSONLD_DATE_PUBLISHED

    if instant is None:
        instant = _from_article_meta(soup, source)
        signal = SIGNAL_META_ARTICLE_PUBLISHED_TIME

    if instant is None:
        instant = _from_date_meta(soup, source)
        signal = SIGNAL_META_DATE

    if instant is None:
        from_time = _from_time_element(soup, source)
        if from_time is not None:
            instant, signal = from_time

    if instant is None:
        instant = _from_url_path(source)
        signal = SIGNAL_URL_PATH_DATE

    if instant is None:
        log.info("publication_time.not_found", url=source.url)
        return None

    if first_archive_capture is not None:
        if first_archive_capture.tzinfo is None:
            log.warning(
                "publication_time.archive_capture_naive",
                url=source.url,
                reason="impossibility check skipped, capture time carried no zone",
            )
        elif instant > first_archive_capture.astimezone(UTC) + _ARCHIVE_SKEW_GRACE:
            log.warning(
                "publication_time.later_than_first_archive_capture",
                url=source.url,
                signal=signal,
                claimed=instant.isoformat(),
                first_capture=first_archive_capture.isoformat(),
            )
            return None

    return ExtractedPublicationTime(instant=instant, signal=signal)
