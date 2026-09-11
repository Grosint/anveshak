"""Import a corpus of dated items through the existing ingest path - issue #45.

There is otherwise no route into the platform for content that already exists
with a known Publication Time. The tipline endpoint stamps the current time and
has no publication date field, and the only bulk path is a demonstration SQL
seed, which writes rows the product did not produce.

This importer writes no SQL of its own for content. Every item goes through
``ingest_raw_item``, the same function the social adapters call, so content
hashing, labelling, organisation scoping, deduplication and the downstream
analysis job all behave exactly as they do for collected content. An importer
with its own INSERT would drift from that path the first time the path changed,
and the drift would only show up as content that behaves differently in the
product for no reason an analyst can see.

That function looks Sources up by handle and returns False when it finds none,
so the Sources a corpus names are created and linked before any item is
ingested. An item with no Publication Time is imported all the same, with a
null value rather than a substitute: it cannot sit on a timeline, but it still
contributes its Source to the independent source count.

Capture Time is the import run time, because that is when Anveshak saw the
item. Publication Time is the corpus value, because that is when the story
happened. Re-running an import inserts nothing new, because the existing
content hash rule already refuses a duplicate.

Corpus format
-------------

JSON Lines, one item per line, UTF-8. Blank lines are skipped, and a line whose
first non-space character is ``#`` is a comment, so a committed corpus can
carry its own provenance notes. See docs/corpus_format.md for the field
reference.

Usage::

    uv run python scripts/import_corpus.py corpus.jsonl --topic-id <uuid> --org-id org-demo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional, Sequence
from urllib.parse import urlparse

import asyncpg
import structlog
from anveshak.social.adapters.base import RawItem
from anveshak.social.ingest import ingest_raw_item
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

log = structlog.get_logger(__name__)

# Recorded in the content labels as the thing that produced the row, the way an
# adapter records itself. An analyst asking where an item came from reads this.
CORPUS_ADAPTER_ID = "corpus-import-v1"

# Deny by default, the shape EXEMPT_MODELS uses: a key nobody declared is a
# typo, and a typo'd key read permissively is a field that silently never
# arrives. The one that matters is a misspelled publication time, which would
# import the whole corpus undated and look like an outlet that publishes no
# dates.
ITEM_KEYS = frozenset(
    {
        "url",
        "text",
        "source",
        "language",
        "published_at",
        "published_at_signal",
        "discovery",
        "body_source",
    }
)
REQUIRED_ITEM_KEYS = frozenset({"url", "text", "source"})

SOURCE_KEYS = frozenset({"handle", "name", "platform", "credibility_score"})
REQUIRED_SOURCE_KEYS = frozenset({"handle", "name", "platform"})

# The credibility a Source is created with when the corpus states none. Matches
# the Watch Space seeder, and is only ever applied at creation: a Source that
# already exists keeps its score, because changing one is an audited event
# (architectural rule 8) and an import is not an assessment.
DEFAULT_CREDIBILITY = 50.0

# A credibility score is a percentage everywhere else in the system, and the
# column has no CHECK constraint to catch a value that is not. A score outside
# the range, or one that is not a real number, silently corrupts every ordering
# and every threshold comparison that reads it afterwards.
CREDIBILITY_RANGE = (0.0, 100.0)

# Only a fetchable web address becomes a row. The workbench renders the URL as a
# live link, so a scheme that executes rather than fetches is a stored payload
# in an analyst's browser.
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

# Control characters that no article body contains and that Postgres TEXT
# refuses outright (NUL), or that carry terminal escape sequences into an
# operator's console when an error quotes the line back. Tab, newline and
# carriage return are left alone, because real bodies contain them.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Every bound here reports itself, so a refusal never reads downstream as a
# corpus that simply had less in it. The figures are generous against a real
# dataset: a four month narrative across twenty outlets is a few thousand items
# and tens of megabytes, and one article line is far under a megabyte.
MAX_CORPUS_BYTES = 512 * 1024 * 1024
MAX_LINE_BYTES = 4 * 1024 * 1024
MAX_ITEMS = 200_000

# ---------------------------------------------------------------------------
# SQL - module-level constants (patterns.md convention)
# ---------------------------------------------------------------------------

SQL_FIND_SOURCE = "SELECT id, is_active FROM sources WHERE url_or_handle = $1 AND platform = $2"

SQL_INSERT_SOURCE = """
    INSERT INTO sources (
        id, name, url_or_handle, platform, credibility_score,
        auto_score_enabled, is_active, org_id, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, $6, $7, $7, $8::jsonb)
"""

SQL_LINK_ORG_SOURCE = """
    INSERT INTO org_sources (org_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

SQL_LINK_TOPIC_SOURCE = """
    INSERT INTO topic_sources (topic_id, source_id)
    VALUES ($1, $2)
    ON CONFLICT DO NOTHING
"""

SQL_VERIFY_TOPIC = "SELECT id FROM topics WHERE id = $1 AND org_id = $2"

SQL_COUNT_PRESENT = """
    SELECT COUNT(*) FROM content_items
    WHERE topic_id = $1 AND content_hash = ANY($2::text[])
"""


# ---------------------------------------------------------------------------
# Corpus format
# ---------------------------------------------------------------------------


class TopicAccessError(RuntimeError):
    """The Topic named does not belong to the organisation named."""


class SourceStateError(RuntimeError):
    """A Source the corpus names exists but is deactivated.

    The ingest path looks a Source up with ``is_active = TRUE`` and skips the
    item when it finds none, so importing against one would report every item
    as already present and insert nothing. Deactivation is an operator
    decision, so the run stops and says so rather than quietly reactivating it.
    """


class CorpusFormatError(ValueError):
    """A corpus line that cannot be read as an item.

    Always names the line it came from. A corpus is a committed artifact that
    a person edits, and an error that does not say where is an error that sends
    them through a few thousand lines by hand.
    """


@dataclass(frozen=True)
class CorpusSource:
    """The outlet an item came from, as the corpus states it."""

    handle: str
    name: str
    platform: str
    credibility_score: Optional[float] = None


@dataclass(frozen=True)
class CorpusItem:
    """One dated item, before it becomes a RawItem.

    published_at is timezone-aware and in UTC, or None. published_at_signal
    names what produced the date, so a provenance question is answerable from
    the row rather than from whoever built the corpus.
    """

    url: str
    text: str
    source: CorpusSource
    published_at: Optional[datetime] = None
    published_at_signal: Optional[str] = None
    language: Optional[str] = None
    discovery: Optional[str] = None
    body_source: Optional[str] = None


def _require_mapping(value: Any, field: str, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CorpusFormatError(f"line {line_number}: {field} must be an object")
    return value


def _check_keys(
    obj: dict[str, Any],
    allowed: frozenset[str],
    required: frozenset[str],
    where: str,
    line_number: int,
) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        # repr'd, because a key name comes from the file and a raw one can carry
        # terminal escape sequences into the operator's console.
        raise CorpusFormatError(
            f"line {line_number}: unknown {where} key(s) "
            f"{', '.join(repr(k) for k in unknown)}. "
            f"Known keys are {', '.join(sorted(allowed))}."
        )
    missing = sorted(required - set(obj))
    if missing:
        raise CorpusFormatError(f"line {line_number}: missing {where} key(s) {', '.join(missing)}")


def _parse_instant(raw: Any, line_number: int) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise CorpusFormatError(f"line {line_number}: published_at must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusFormatError(
            f"line {line_number}: published_at {raw!r} is not an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        # The extraction library refuses naive values for the same reason: the
        # corpus mixes conventions, some outlets emit naive UTC while displaying
        # IST, and a guessed zone moves roughly a quarter of items into the
        # wrong day. That depresses the per-day independent source count that
        # Signal thresholds fire on, and nothing about the result looks wrong.
        raise CorpusFormatError(
            f"line {line_number}: published_at {raw!r} carries no UTC offset. "
            "Resolve the zone when the corpus is built, never at import."
        )
    return parsed.astimezone(UTC)


def _parse_source(raw: Any, line_number: int) -> CorpusSource:
    obj = _require_mapping(raw, "source", line_number)
    _check_keys(obj, SOURCE_KEYS, REQUIRED_SOURCE_KEYS, "source", line_number)

    credibility = obj.get("credibility_score")
    if credibility is not None:
        # bool is a subclass of int, so `true` would otherwise become 1.0.
        if isinstance(credibility, bool) or not isinstance(credibility, (int, float)):
            raise CorpusFormatError(
                f"line {line_number}: source.credibility_score must be a number"
            )
        low, high = CREDIBILITY_RANGE
        if not math.isfinite(credibility) or not low <= credibility <= high:
            raise CorpusFormatError(
                f"line {line_number}: source.credibility_score {credibility!r} is outside "
                f"{low} to {high}"
            )

    for field in ("handle", "name", "platform"):
        if not isinstance(obj[field], str) or not obj[field].strip():
            raise CorpusFormatError(
                f"line {line_number}: source.{field} must be a non-empty string"
            )

    return CorpusSource(
        handle=obj["handle"].strip(),
        name=obj["name"].strip(),
        platform=obj["platform"].strip(),
        credibility_score=float(credibility) if credibility is not None else None,
    )


def parse_corpus_line(line: str, line_number: int) -> CorpusItem:
    """Parse one corpus line, or raise CorpusFormatError naming the line."""

    def _refuse_constant(name: str) -> float:
        # json.loads accepts Infinity and NaN by default. Both survive an
        # isinstance check and a float() call, and a NaN credibility score
        # compares false against every threshold without erroring anywhere.
        raise CorpusFormatError(f"line {line_number}: {name} is not a JSON value")

    try:
        raw = json.loads(line, parse_constant=_refuse_constant)
    except json.JSONDecodeError as exc:
        raise CorpusFormatError(f"line {line_number}: not valid JSON ({exc.msg})") from exc

    obj = _require_mapping(raw, "item", line_number)
    _check_keys(obj, ITEM_KEYS, REQUIRED_ITEM_KEYS, "item", line_number)

    for field in ("url", "text"):
        if not isinstance(obj[field], str) or not obj[field].strip():
            raise CorpusFormatError(f"line {line_number}: {field} must be a non-empty string")
        if _CONTROL_CHARACTERS.search(obj[field]):
            raise CorpusFormatError(
                f"line {line_number}: {field} contains a control character. "
                "Postgres refuses NUL outright, and the rest are not article text."
            )

    scheme = urlparse(obj["url"].strip()).scheme.lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise CorpusFormatError(
            f"line {line_number}: url scheme {scheme or 'none'!r} is not one of "
            f"{', '.join(sorted(ALLOWED_URL_SCHEMES))}"
        )

    published_raw = obj.get("published_at")
    signal = obj.get("published_at_signal")

    if published_raw is not None and signal is None:
        # Story 6: where a date came from has to be answerable from the row.
        # A date with no signal is a date nobody can defend later.
        raise CorpusFormatError(
            f"line {line_number}: published_at is set but published_at_signal is not. "
            "Record which signal produced the date."
        )
    if published_raw is None and signal is not None:
        raise CorpusFormatError(
            f"line {line_number}: published_at_signal is set but published_at is not"
        )

    for field in ("language", "discovery", "body_source"):
        value = obj.get(field)
        if value is not None and not isinstance(value, str):
            raise CorpusFormatError(f"line {line_number}: {field} must be a string")

    return CorpusItem(
        url=obj["url"].strip(),
        text=obj["text"],
        source=_parse_source(obj["source"], line_number),
        published_at=(
            _parse_instant(published_raw, line_number) if published_raw is not None else None
        ),
        published_at_signal=signal,
        language=obj.get("language"),
        discovery=obj.get("discovery"),
        body_source=obj.get("body_source"),
    )


def load_corpus(path: Path) -> list[CorpusItem]:
    """Read a corpus file into items, refusing the whole file on any bad line.

    Whole file rather than item by item: a corpus is the committed source of
    truth for a dataset, and a partial import is a dataset nobody can reproduce
    from the file.
    """
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CorpusFormatError(f"cannot read corpus {path}: {exc}") from exc

    if size > MAX_CORPUS_BYTES:
        raise CorpusFormatError(
            f"corpus {path} is {size} bytes, over the {MAX_CORPUS_BYTES} byte bound"
        )

    items: list[CorpusItem] = []
    try:
        # Streamed rather than read whole, so a corpus is bounded by the file
        # bound above rather than by twice its size in memory.
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                    raise CorpusFormatError(
                        f"line {line_number}: over the {MAX_LINE_BYTES} byte bound"
                    )
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if len(items) >= MAX_ITEMS:
                    raise CorpusFormatError(
                        f"corpus {path} has more than {MAX_ITEMS} items. Split it by period."
                    )
                items.append(parse_corpus_line(stripped, line_number))
    except OSError as exc:
        raise CorpusFormatError(f"cannot read corpus {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise CorpusFormatError(f"corpus {path} is not UTF-8: {exc}") from exc

    if not items:
        raise CorpusFormatError(f"corpus {path} contains no items")
    return items


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportSummary:
    """What a run did, for the operator and for the run sheet."""

    items: int
    imported: int
    duplicates: int
    undated: int
    sources_created: int
    # Items that are neither new nor present afterwards. Always zero unless the
    # ingest path dropped something, which is why it is counted separately from
    # duplicates rather than folded into them.
    missing: int = 0


def _source_labels(org_id: str) -> str:
    """Classification labels for a Source the import creates.

    owner_org is the organisation the row is written with, matching the Watch
    Space seeder: pinning it to a constant made the label disagree with the row
    for every organisation except the default.
    """
    return json.dumps({"classification": "OPEN", "domain": "osint", "owner_org": org_id})


async def ensure_sources(
    pool: asyncpg.Pool,
    items: Sequence[CorpusItem],
    *,
    topic_id: str,
    org_id: str,
) -> tuple[dict[str, str], int]:
    """Create and link every Source the corpus names. Returns ids by handle.

    Sources are global entities, so an outlet another organisation already
    registered is reused rather than duplicated, and visibility runs through
    org_sources. Idempotent on handle and platform, so a re-run links what is
    already there and creates nothing.
    """
    source_ids: dict[str, str] = {}
    created = 0

    by_handle: dict[str, CorpusSource] = {}
    for item in items:
        by_handle.setdefault(item.source.handle, item.source)

    async with pool.acquire() as conn, conn.transaction():
        # One transaction, so a failure partway leaves no Source created but
        # unlinked, which would read later as an outlet nobody can see.
        for handle, source in by_handle.items():
            existing = await conn.fetchrow(SQL_FIND_SOURCE, handle, source.platform)
            if existing is not None:
                if not existing["is_active"]:
                    raise SourceStateError(
                        f"Source {handle} on {source.platform} is deactivated. "
                        "The ingest path skips a deactivated Source, so every item "
                        "from it would report as already present. Reactivate it or "
                        "remove it from the corpus."
                    )
                source_id = existing["id"]
            else:
                source_id = str(uuid.uuid4())
                await conn.execute(
                    SQL_INSERT_SOURCE,
                    source_id,
                    source.name,
                    handle,
                    source.platform,
                    source.credibility_score
                    if source.credibility_score is not None
                    else DEFAULT_CREDIBILITY,
                    org_id,
                    datetime.now(UTC),
                    _source_labels(org_id),
                )
                created += 1

            await conn.execute(SQL_LINK_ORG_SOURCE, org_id, source_id)
            await conn.execute(SQL_LINK_TOPIC_SOURCE, topic_id, source_id)
            source_ids[handle] = source_id

    log.info(
        "corpus.sources_ready",
        topic_id=topic_id,
        org_id=org_id,
        sources=len(source_ids),
        created=created,
    )
    return source_ids, created


async def verify_topic_access(
    pool: asyncpg.Pool,
    *,
    topic_id: str,
    org_id: str,
) -> None:
    """Refuse to import into a Topic the organisation does not own.

    ingest_raw_item writes the org_id it is given without checking it against
    the Topic, so a wrong pair here would produce rows an analyst reads under
    one organisation that belong to another's Topic. The same check every route
    makes, made once per run rather than once per item.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(SQL_VERIFY_TOPIC, topic_id, org_id)
    if row is None:
        raise TopicAccessError(f"No topic {topic_id} in organisation {org_id}")


async def import_corpus(
    items: Sequence[CorpusItem],
    *,
    topic_id: str,
    org_id: str,
    pool: asyncpg.Pool,
    arq_pool: ArqRedis,
    captured_at: Optional[datetime] = None,
) -> ImportSummary:
    """Import corpus items into a Topic through the ingest path.

    org_id is keyword-only so it cannot be passed by position into the wrong
    slot: an import that lands in another organisation's Topic is a cross-org
    leak, and the row would carry no sign of it.

    captured_at defaults to the run time and is shared by every item in the
    run, which is what a Backfill's Capture Time means: all of them are the day
    it was loaded.
    """
    await verify_topic_access(pool, topic_id=topic_id, org_id=org_id)
    _, sources_created = await ensure_sources(pool, items, topic_id=topic_id, org_id=org_id)

    run_captured_at = captured_at or datetime.now(UTC)
    imported = 0
    undated = 0
    # A set, because two identical bodies in one corpus are one row by the
    # dedup rule and counting them twice would invent a missing item.
    hashes: set[str] = set()

    for item in items:
        if item.published_at is None:
            undated += 1

        # Discovery mechanism and body origin are evidence claims, not trivia: a
        # sitemap date is day-granular where a feed asserts an instant, and an
        # archived body is the article as published where a fetched one is the
        # article as it stands today. The columns have nowhere to put them, so
        # they ride in the labels next to the date signal.
        provenance = {
            key: value
            for key, value in (
                ("discovery", item.discovery),
                ("body_source", item.body_source),
            )
            if value is not None
        }

        raw = RawItem(
            raw_text=item.text,
            url=item.url,
            platform=item.source.platform,
            captured_at=run_captured_at,
            source_handle=item.source.handle,
            language=item.language,
            published_at=item.published_at,
            published_at_signal=item.published_at_signal,
            extra_labels=provenance or None,
        )

        hashes.add(raw.content_hash())

        if await ingest_raw_item(
            raw,
            topic_id,
            pool,
            arq_pool,
            CORPUS_ADAPTER_ID,
            org_id=org_id,
        ):
            imported += 1

    # ingest_raw_item returns False for a dedup hit and for every reason it
    # declined an item, and the two read identically from here. Counting what is
    # actually in the Topic afterwards separates them, so a dropped item cannot
    # report as "already present" and leave an operator looking for a Signal
    # that had no content behind it.
    async with pool.acquire() as conn:
        present = await conn.fetchval(SQL_COUNT_PRESENT, topic_id, sorted(hashes))

    summary = ImportSummary(
        items=len(items),
        imported=imported,
        duplicates=present - imported,
        undated=undated,
        sources_created=sources_created,
        missing=len(hashes) - present,
    )

    log.info(
        "corpus.imported",
        topic_id=topic_id,
        org_id=org_id,
        items=summary.items,
        imported=summary.imported,
        duplicates=summary.duplicates,
        undated=summary.undated,
    )
    if summary.missing:
        log.warning(
            "corpus.items_missing",
            topic_id=topic_id,
            missing=summary.missing,
            reason="ingest declined the item, see social.ingest warnings above",
        )
    if summary.undated:
        # Undated items are excluded from the Sentiment Timeline, which reports
        # them in its footnote count. Saying so here means an operator reading
        # that footnote already knows where the number came from.
        log.info(
            "corpus.undated_items",
            topic_id=topic_id,
            undated=summary.undated,
            reason="no Publication Time in the corpus, stored as NULL",
        )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> int:
    items = load_corpus(args.corpus)
    print(f"  [1/3] corpus read: {len(items)} items from {args.corpus}")

    pool = await asyncpg.create_pool(args.postgres_url, min_size=1, max_size=4)
    if pool is None:
        print("Could not open a database pool", file=sys.stderr)
        return 1
    arq_pool = await create_pool(RedisSettings.from_dsn(args.redis_url))
    try:
        print(f"  [2/3] importing into topic {args.topic_id} as organisation {args.org_id}")
        summary = await import_corpus(
            items,
            topic_id=args.topic_id,
            org_id=args.org_id,
            pool=pool,
            arq_pool=arq_pool,
        )
    except (TopicAccessError, SourceStateError):
        raise
    except Exception as exc:
        # A run that dies partway has already written the items it reached, and
        # the operator needs to know a re-run is the recovery rather than a
        # duplicate import. It is, by the content hash rule.
        print(f"  [3/3] import stopped: {exc}", file=sys.stderr)
        print(
            "        Items already written stay written. Re-running the same "
            "corpus imports only what is missing.",
            file=sys.stderr,
        )
        return 1
    finally:
        await arq_pool.aclose()
        await pool.close()

    print(
        f"  [3/3] imported {summary.imported}, "
        f"already present {summary.duplicates}, "
        f"no Publication Time {summary.undated}, "
        f"sources created {summary.sources_created}"
    )
    if summary.missing:
        print(
            f"        {summary.missing} item(s) are in neither state: the ingest "
            "path declined them. See the corpus.items_missing log line.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a dated corpus into a Topic")
    parser.add_argument("corpus", type=Path, help="Corpus file in JSON Lines format")
    parser.add_argument("--topic-id", required=True, help="Topic the items are imported into")
    parser.add_argument(
        "--org-id",
        default=os.getenv("SEED_ORG_ID", ""),
        help="Organisation that owns the Topic. Defaults to SEED_ORG_ID.",
    )
    args = parser.parse_args()

    if not args.org_id:
        print("Set SEED_ORG_ID or pass --org-id.", file=sys.stderr)
        return 1
    # Read from the environment and never from a flag, following the other
    # backfill scripts: a DSN on argv is a password in `ps` output and in shell
    # history. No default is built in either, so the script cannot silently
    # target a database nobody named.
    args.postgres_url = os.getenv("POSTGRES_URL", "")
    args.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if not args.postgres_url:
        print(
            "Set POSTGRES_URL. This script takes no database URL on the command line.",
            file=sys.stderr,
        )
        return 1

    try:
        return asyncio.run(_run(args))
    except CorpusFormatError as exc:
        print(f"Corpus rejected: {exc}", file=sys.stderr)
        return 1
    except TopicAccessError as exc:
        print(f"{exc}. Nothing imported.", file=sys.stderr)
        return 1
    except SourceStateError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
