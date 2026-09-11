# Corpus format

A corpus is a file of dated items that the importer loads into a Topic.
It is the committed source of truth for a dataset, and a database dump is only an artifact of a run over it.
See [`scripts/import_corpus.py`](../scripts/import_corpus.py) for the importer and [CONTEXT.md](../CONTEXT.md) for Backfill, Replay, Capture Time and Publication Time.

## File shape

JSON Lines, UTF-8, one item per line.

A blank line is skipped.
A line whose first non-space character is `#` is a comment, so a corpus can carry its own provenance notes next to the items they describe.

A single bad line rejects the whole file.
A partial import is a dataset nobody can reproduce from the file, which defeats the point of committing it.

## Item fields

| Field | Required | Meaning |
|-------|----------|---------|
| `url` | yes | Where the item was published. Stored on the row. |
| `text` | yes | The body as published. Becomes `raw_text`, and the normalised form of it becomes the dedup hash. |
| `source` | yes | The outlet, see below. |
| `published_at` | no | Publication Time, ISO 8601 with a UTC offset. Omit it when it is unknown. |
| `published_at_signal` | with `published_at` | What produced the date, for example `jsonld_date_published` or `url_path_date`. |
| `language` | no | ISO 639-1. Omitted means the analyst pipeline detects it. |
| `discovery` | no | How the item was found, for example `archive_sitemap`, `paginated_feed`, `topic_feed`. Stored in the content labels. |
| `body_source` | no | Where the body came from, `publisher` or `archive`. Stored in the content labels. |

The `source` object takes `handle`, `name` and `platform`, all required, and an optional `credibility_score`.
`handle` matches `sources.url_or_handle`, because that is what the ingest path looks a Source up by.

An unknown key at either level rejects the line.
A key nobody declared is a typo, and a typo read permissively is a field that silently never arrives: a misspelled `published_at` imports the whole corpus undated and reads downstream as an outlet that publishes no dates.

## What the format refuses

A `url` whose scheme is not `http` or `https`.
The workbench renders the URL as a live link, so a scheme that executes rather than fetches is a stored payload in an analyst's browser.

A control character in `url` or `text`.
Postgres `TEXT` refuses NUL outright, which would abort a run partway, and the rest are not article text.
Tab, newline and carriage return are left alone.

A `credibility_score` that is not a finite number between 0 and 100.
`NaN` and `Infinity` are valid JSON to most parsers and survive a type check, and a `NaN` score compares false against every threshold without erroring anywhere.
The column has no CHECK constraint to catch it later.

A file over 512 MB, a line over 4 MB, or more than 200,000 items.
Each bound names itself when it fires, so a refusal never reads as a corpus that simply had less in it.

## Dates

A naive `published_at` is refused.
The corpus mixes conventions, some Indian outlets emit naive UTC while displaying IST, and a guessed zone moves roughly a quarter of items into the wrong day.
That depresses the per-day independent source count that Signal thresholds fire on, and nothing about the result looks wrong.
Resolve the zone when the corpus is built, where the outlet is known, never at import.

`published_at` without `published_at_signal` is refused.
Where a date came from has to be answerable from the row, because a day-granular URL date and an outlet's own assertion are not the same claim.
The signal name is written into the content labels under `publication_time_signal`, the same key the scraper writes for collected content.

An item with no Publication Time is imported with a null value rather than a substitute.
It is excluded from the Sentiment Timeline and counted in that view's footnote, and it still contributes its Source to the independent source count.

## Trust model

A corpus is operator-supplied and its contents are not.
The items in it are scraped text from outlets, so every value is validated at parse time as described above, and none of it reaches a query as anything but a bound parameter.

What the format cannot check is the dataset itself.
Each distinct `source.handle` becomes a Source, and Signals fire on a count of independent Sources, so a file that invents outlets manufactures the evidence for a Signal.
Review a corpus the way a Source list is reviewed, and keep the file in review alongside the code that reads it.
That is the reason the corpus is committed rather than passed around.

## What an import does

Capture Time is the import run time, shared by every item in the run.
Publication Time is the corpus value.

Sources named by the corpus are created first, because the ingest path looks Sources up by handle and skips an item whose Source it cannot find.
A Source is global, so one another organisation already registered is reused rather than duplicated, and visibility runs through `org_sources`.
A `credibility_score` in the corpus applies only when the Source is created: changing an existing score is an audited event (architectural rule 8), and an import is not an assessment.

Omit it and the structural rubric decides instead, which is the ordinary case.
Stating one overrides the rubric, including when the value equals the neutral score, so a corpus that sets `credibility_score: 50` on every source disables the rubric for all of them.
The rubric scores an outlet on properties a reviewer can check on its own pages, and an outlet it does not declare is created at the neutral score with that fact logged.
See [ADR 0004](adr/0004-source-credibility-rubric.md).

Items are then ingested one at a time through `ingest_raw_item`, the function the social adapters call.
Content hashing, labelling, organisation scoping, deduplication and the `analyse_content` dispatch therefore behave exactly as they do for collected content.

Re-running an import inserts nothing, because the existing content hash rule refuses a duplicate (architectural rule 3).
A duplicate dispatches no analysis job either, so a Replay does not multiply work.
A run that stops partway is recovered by running it again, for the same reason.

The run counts what is in the Topic afterwards rather than trusting the insert path's return value.
An item that is neither new nor present is reported as missing rather than as a duplicate, because those are opposite facts for an operator: one means the content is already there, the other means it never arrived.
The dedup key is global, so an item another Topic already holds is missing here rather than duplicated.

A Source the corpus names that exists but is deactivated stops the run.
The ingest path skips a deactivated Source, so importing against one would report every item as already present and insert nothing.
Deactivation is an operator decision, so the importer says so rather than quietly reactivating it.

## Example

```json
{"url": "https://outlet.example/2026/05/16/movement-founded", "text": "The movement was founded today at a public meeting in the capital.", "language": "en", "published_at": "2026-05-16T09:30:00+05:30", "published_at_signal": "jsonld_date_published", "discovery": "archive_sitemap", "body_source": "publisher", "source": {"handle": "https://outlet.example/feed", "name": "Outlet", "platform": "web"}}
```

## Running an import

```bash
uv run python scripts/import_corpus.py corpus.jsonl \
    --topic-id <topic uuid> --org-id <organisation id>
```

`POSTGRES_URL` and `REDIS_URL` are read from the environment and cannot be passed on the command line, because a DSN on argv is a password in `ps` output and in shell history.
The script ships no credential default either, so it cannot silently target a database nobody named.
It refuses a Topic the named organisation does not own, before it imports anything.
