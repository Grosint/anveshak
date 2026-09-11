# Historic Backfill and Replay implementation plan

Epic #39.
Capability sub-issues #41 to #51, and the two defects the work surfaced, #55 and #56.
Issue #40, the honesty fix to the existing demonstration seed, belongs to the dataset plan rather than here.

This document is written once and read at the start of every session that works on the capability half of this epic.
A session needs three lines: read this plan, state the step, run TDD.

The dataset half lives in [demonstration_dataset_plan.md](demonstration_dataset_plan.md), and nothing in this document depends on it.
The split is deliberate.
Roughly half of this epic is product capability that outlives the demonstration it was built for, and a reader looking for the Backfill design should not have to read a run sheet to find it.
Everything here ships whether or not the demonstration ever happens.

Vocabulary is in [CONTEXT.md](../CONTEXT.md).
Decisions are in [ADR 0003](adr/0003-virtual-clock.md) and [ADR 0004](adr/0004-source-credibility-rubric.md).
Operator documentation is in [replay.md](replay.md) and [corpus_format.md](corpus_format.md).
Excluded work is in [deferred_scope.md](deferred_scope.md).

---

## The problem this capability solves

Every adapter was recency-only.
X caps a search at a seven day platform window, and no adapter accepted a date range, so a narrative older than about a week could not be collected at all.
For an intelligence tool that is most narratives.

`captured_at` also conflated collection with publication, so even collected history read as though it had happened on the day of the load.

The capability is therefore three things that have to hold together: reaching back past what a feed carries, carrying the real Publication Time through ingest, and running detection at a time other than now.
Any one of them alone produces a dishonest result.
Collection without Publication Time dates the whole history to the import minute.
Publication Time without a reference time means detection windows exclude everything.
A reference time without collection has nothing to run against.

---

## Architecture

### Publication Time is what an analyst reads

`published_at` landed in #24 as a nullable column, populated only when a platform genuinely supplies a publication time.
This epic makes it the field every analyst-facing date reads: the timeline, the content feed filter, the Report window.
Where it is NULL the item is excluded with a stated count, never stacked at today and never inferred from Capture Time.

### Publication Time extraction is one pure function with a documented precedence

`services/scraper/anveshak/scraper/publication_time.py` is the single extraction path.
Precedence is JSON-LD `datePublished`, then the article published time meta tag, then other date meta, then a `time` element carrying an explicit offset, then a date encoded in the URL path.
A new outlet is therefore a configuration change rather than a new parser.

Naive timestamps are refused by default with a per-source timezone override, because the corpus mixes conventions: some Indian outlets emit naive UTC while displaying IST, and guessing between those two is a five and a half hour error in a timeline.
Where nothing is recoverable the item carries a NULL Publication Time.

Each extracted value carries the name of the signal that produced it, so a date is defensible from the row rather than from whoever collected it.

### Historic discovery is three routes, not one

Zero of the 22 target outlet feeds reach back to the start of the arc, so live collection and historic discovery are separate mechanisms.

| Route | What it reads | Function |
|-------|---------------|----------|
| Monthly archive sitemap | the outlet's own sitemap index | `discover_archive_sitemap` |
| Paginated feed walk | `?paged=N` on a WordPress feed | `discover_paginated_feed` |
| Topic feed | a category or tag feed | `discover_topic_feeds` |

Per-outlet configuration lives in the `OUTLET_BACKFILL` registry in `archive_backfill.py`, keyed by host with `www.` stripped, because an outlet serves the same history under both.
The registry ships empty and denies by default.
An outlet is added when it enters a corpus, each entry recording the survey observation that justifies its route, so populating it is dataset work under #54 rather than capability work here.
An unconfigured host logs `backfill.outlet_not_configured` with the reason rather than returning silently empty, which is what makes an empty registry a visible gap instead of a discovery that finds nothing.

Article bodies are fetched from the publisher, with Wayback Machine CDX rehydration on a 4xx.
Rehydration is a setting and not a default assumption, because it discloses the URLs being collected to an operator outside the deployment boundary.

Google News RSS is rejected as a discovery layer despite its working date operators, because its links are opaque and require an undocumented Google-internal resolution step.

### The corpus is the import boundary

A Backfill produces a committed JSONL corpus, and the importer loads it through the existing ingest path rather than a second write path.
Format, refusals and trust model are in [corpus_format.md](corpus_format.md).
The property that matters: an item is new, already present, or missing, and those are three distinct operator facts rather than two.

### The reference time is a parameter, never a clock

ADR 0003.
Detection SQL takes the reference time as a bind parameter, `resolve_reference_time()` in `sdk/anveshak/clock.py` is the single resolution point, and one pass resolves it once at its entry point and threads that value through every query and write it performs.
It defaults to the current time, so the live path is unchanged and needs no flag.

An override is gated twice, by `VIRTUAL_CLOCK_ENABLED` and by an environment allowlist, and a reference time in the future is refused.
Supplying a reference time while the flag is off raises `ClockOverrideRefusedError` rather than falling back to the wall clock.

### A Replay is staged, and live passes are suspended while it runs

Chronological weekly stages with detection between them, so promotion gates receive multiple runs and a hostility shift is measured against a real prior baseline rather than against a single load.
On a Replay host the passes that measure Capture Time against the wall clock are suspended, content retention first, since its first tick would otherwise archive and delete the corpus the Replay was run to produce.

### Credibility baselines are structural

ADR 0004.
A Source is created at a baseline summed from verifiable structural properties of the outlet, held in a versioned rubric file the customer owns, and never from an editorial view of its politics.
Movement after creation stays behavioural and audited, which is architectural rule 8.

### Date range surfaces filter server side

Both analyst gaps, the Report builder range and the content feed filter, filter on Publication Time in SQL rather than in the client, because a client-side filter over a paginated feed filters the page rather than the feed.

---

## Steps

All of the following have landed on `feature/narrative_signal`, each written test-first at the seam the test matrix names.
The GitHub issues are still open; the code is on the branch.

| Issue | Step | Where | Commit |
|-------|------|-------|--------|
| #41 | Super-admin role, demonstration organisation and accounts from the environment | `scripts/seed_demo_org.py` | `f7d5fce` |
| #42 | Publication Time extraction library with per-source timezone policy | `services/scraper/.../publication_time.py` | `08d2070` |
| #43 | News adapter collecting RSS and Atom with real Publication Time | `services/scraper/.../rss.py`, `fetch.py` | `e7d576e` |
| #44 | Archive Backfill discovery and article body fetch | `services/scraper/.../archive_backfill.py` | `6a66ada`, `806fa15` |
| #45 | Dated corpus importer and the corpus format | `scripts/import_corpus.py` | `78fe8fe` |
| #46 | Reference time on detection queries and output | `sdk/anveshak/clock.py`, `services/analyst/` | `ab8a7d9` |
| #47 | Replay driver with reset and environment guard | `scripts/replay_corpus.py` | `54d02aa` |
| #48 | Absolute date range in the Report builder | `frontend/src/pages/ReportBuilder.tsx` | `ad1a27a` |
| #49 | Content feed date filter on Publication Time, server side | `services/api/.../topics.py`, migration 008 | `ce544fd` |
| #50 | Mobilization lexicon version 2, Indian mobilization idiom | `infra/configs/lexicons/mobilization.yaml` | `30fd628` |
| #51 | Per-outlet Source credibility rubric | `sdk/anveshak/source_rubric.py`, `infra/configs/credibility/source_rubric.yaml` | `e172db5` |
| #53 | Intelligence Bureau persona, ADRs 0003 and 0004, these plan documents | `.agents/personas/persona-ib.md`, `docs/` | this step |

Open, and not required by the demonstration:

| Issue | Step | Why it is open |
|-------|------|----------------|
| #55 | Validate the outbound fetch destination at every hop | Redirects, the browser and DNS rebinding each get past a first-hop check. Shape depends on whether egress policy is available in k3s and Compose alike, so it is a design question before it is a code change |
| #56 | Select mobilization patterns by script rather than by language label | Latin-script Hinglish labelled `hi` never reaches the transliterated patterns. #50 made it materially worse, and no current test or benchmark row can observe it, because every one carries a hand-written label |

---

## Phases

Each phase ends green: `make lint`, `make typecheck`, `make test-unit`, and the review agents named in CLAUDE.md.

### Phase 1 - Multi-tenancy for the run
Issue #41.
Exit criteria: a super-admin role exists with its CHECK constraint updated in the same migration that uses it, the demonstration organisation and its analyst user are seeded from the environment, no password or password hash is committed, and the seeder refuses to run under `ENVIRONMENT=production` without an explicit opt-in.
The matching honesty fix to the existing seed, #40, is Phase 1 of the dataset plan.

### Phase 2 - Collection
Issues #42, #43, #44.
Exit criteria: Publication Time extraction is table driven over the 20 saved markup-shape fixtures, which cover every rule in the precedence order rather than one file per real outlet; the news adapter carries a real Publication Time or NULL and never `now()`; and each of the three discovery routes reaches an arbitrary past window against fixtures, with an unconfigured host logging its reason.
Whether a given outlet reaches 16 May 2026 is a property of that outlet's archive, measured per outlet as it is added to the registry in #54, not of this code.

### Phase 3 - Time model
Issues #45, #46, #47.
Exit criteria: a corpus imports through the existing ingest seam against a real database, detection accepts an explicit reference time with the live default unchanged, and a reset plus re-run reproduces the first run's counts.
This is the phase that carries ADR 0003.

### Phase 4 - Analyst surfaces
Issues #48, #49.
Exit criteria: a Report can be generated for an arbitrary historic range, the content feed filters on Publication Time server side, and the excluded NULL count is visible rather than silent.

### Phase 5 - Signal and Source quality
Issues #50, #51.
Exit criteria: the lexicon fires on destination idiom in both scripts with the matched phrase cited, and a Source is created at a rubric baseline with the criteria that produced it readable.
This is the phase that carries ADR 0004.

### Phase 6 - Decisions of record
Issue #53.
Exit criteria: ADRs 0003 and 0004 written, the Intelligence Bureau persona discoverable by the same mechanism as the other personas, and both plan documents carrying numbered phases, exit criteria and a risk register.

### Phase 7 - Follow-up defects
Issues #55, #56.
Neither blocks the demonstration.
#55 is a security boundary question and #56 is a recall gap that the benchmark cannot currently see.

---

## Settings inventory

Every setting in the first table is read from the environment, appears in the compose `environment:` block, and appears in `.env.example`.
`scripts/verify_env_forwarding.py` enforces that, denying by default.

| Setting | Default | Issue |
|---------|---------|-------|
| `RSS_MAX_ITEMS_PER_FETCH` | `20` | #43 |
| `RSS_FULL_TEXT_MIN_CHARS` | `200` | #43 |
| `ARCHIVE_BACKFILL_ENABLED` | `true` | #44 |
| `ARCHIVE_BACKFILL_MAX_FEED_PAGES` | `40` | #44 |
| `ARCHIVE_BACKFILL_MAX_ITEMS_PER_PAGE` | `100` | #44 |
| `ARCHIVE_BACKFILL_MAX_URLS_PER_OUTLET` | `5000` | #44 |
| `ARCHIVE_BACKFILL_BODY_MIN_CHARS` | `200` | #44 |
| `ARCHIVE_BACKFILL_CDX_URL` | `https://web.archive.org/cdx/search/cdx` | #44 |
| `ARCHIVE_BACKFILL_BASE_URL` | `https://web.archive.org/web` | #44 |
| `ARCHIVE_BACKFILL_FEED_DEPTH_MAX_GAP_DAYS` | `30` | #44 |
| `VIRTUAL_CLOCK_ENABLED` | `false` | #46 |
| `VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS` | `["development","test","local","replay"]` | #46 |
| `SOURCE_RUBRIC_PATH` | `/workspace/infra/configs/credibility/source_rubric.yaml` | #51 |

The next three are deliberately host-only.
They are read on the host before any container is involved, and are listed with a reason in the `EXEMPT_VARS` allowlist in `scripts/verify_env_forwarding.py`.
Forwarding them would imply a service reads them, and a service that could seed accounts or reset a Replay is a worse thing to have than an unforwarded variable.

| Setting | Default | Issue |
|---------|---------|-------|
| `ANVESHAK_DEMO_ANALYST_USERNAME` and the other five `ANVESHAK_DEMO_*` credentials | placeholder, seed refuses a missing password | #41 |
| `ANVESHAK_ALLOW_DEMO_SEED` | unset, required under `ENVIRONMENT=production` | #41 |
| `ANVESHAK_ALLOW_REPLAY_RESET` | unset, required before a destructive reset | #47 |

Three of these are guards rather than tuning knobs, and they are the ones that must never acquire a permissive default: `VIRTUAL_CLOCK_ENABLED`, `ANVESHAK_ALLOW_DEMO_SEED` and `ANVESHAK_ALLOW_REPLAY_RESET`.

---

## Invariants, mandatory

These assert that configuration and design cannot defeat themselves.
They read values from settings, never hardcoded numbers.

- The virtual clock is off by default, and a reference time supplied while it is off is refused rather than ignored.
- An override is refused in an environment off the allowlist even when the flag is on, so one flag copied into a production `.env` is not the whole gate.
- A reference time in the future is refused, because a row dated ahead of now keeps matching every window relative to `NOW()` forever.
- A Replay host suspends every pass that measures Capture Time against the wall clock, content retention first.
- Publication Time is never written from `now()`, and a NULL is never filled by inference from Capture Time.
- A rubric baseline is bounded to the credibility range, and every criterion in the file is one a reviewer can check on the outlet's own pages.

---

## Test matrix

Eight seams, seven of which already existed before this epic.
Only Publication Time extraction is new, and it is a pure function.

| Seam | Tests | Covers |
|------|-------|--------|
| Publication Time extraction | `tests/unit/test_publication_time_extraction.py` over `tests/fixtures/publication_time/` | precedence order, naive timestamp refusal, per-source timezone, URL path dates |
| Feed collection | `tests/unit/test_news_feed_adapter.py`, `tests/fixtures/news_feeds/` | full text against summary feeds, undated feeds, Atom `updated` only |
| Archive discovery | `tests/unit/test_archive_backfill.py` with `httpx.MockTransport` | sitemap, paginated walk and its wraparound stop, topic feeds, rehydration, feed depth |
| Dated import | `tests/integration/test_corpus_import.py`, `tests/unit/test_corpus_format.py` | new against present against missing, deactivated Source refusal, replay-safe re-run |
| Reference time | `tests/unit/test_detection_reference_time.py`, `tests/unit/test_virtual_clock.py`, `tests/integration/test_virtual_clock_pipeline.py` | window behaviour at a fixed datetime, both guards, output timestamps |
| Replay driver | `tests/unit/test_replay_driver.py`, `tests/unit/test_live_pass_suspension.py`, `tests/integration/test_replay_driver.py` | staging, refusals, reset order, Signals dated to their stage, reset plus re-run reproducing counts |
| Source rubric | `tests/unit/test_source_rubric.py`, `tests/unit/test_source_creation_baseline.py`, `tests/integration/test_source_rubric_apply.py` | criteria scoring, creation baseline, audit row on application |
| Mobilization lexicon | `tests/unit/test_mobilization_lexicon.py`, `benchmark/mobilization.py` | destination idiom, cited phrase, precision against the labelled set |
| Analyst surfaces | `tests/unit/test_content_date_filter.py`, `tests/integration/test_content_date_filter.py`, frontend contract and component tests | server-side filtering, Report range, excluded NULL count |

The Replay integration test injects embeddings rather than waiting for the analyst worker, which is what makes clustering deterministic enough to compare two runs.

---

## Makefile targets

| Target | Runs | When |
|--------|------|------|
| `make test-unit` | `tests/unit/`, no external dependency | every step, under 30s |
| `make test-integration` | real PostgreSQL and Redis from Compose | any step touching SQL, ingest or the Replay |
| `make test-contract` | service contract tests | any step changing an ARQ queue or an API shape |
| `make test-ci` | everything plus the coverage gate | before push |
| `make lint`, `make typecheck` | ruff, black, isort, pyright, eslint | every step |
| `make agents-check` | the `.agents` to `.claude` bridge | after adding a skill or persona |
| `uv run python scripts/verify_env_forwarding.py` | `.env.example` against compose | after adding a setting |
| `uv run python scripts/replay_corpus.py` | a staged Replay | the dataset plan, not this one |

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| The virtual clock reaches a live deployment | Signals dated days they were not produced on, silently | off by default, environment allowlist, future times refused, clock in use logged at startup, ADR 0003 |
| A naive timestamp is guessed rather than refused | every date in a timeline is wrong by a timezone offset and looks plausible | naive refused by default, per-source override, signal name stored per row |
| Publication Time NULL for most rows | timelines and filters look empty and the platform looks broken | excluded count stated at every consumption point, never a silent drop |
| A Replay's retention pass deletes the corpus | the run destroys its own input hours in | live passes suspended on a Replay host, asserted by test |
| Wayback rehydration discloses collection | the URLs being collected leave the deployment boundary | a setting, off-switchable, documented as a disclosure rather than a fallback |
| An outlet changes its archive layout | discovery silently returns nothing for that outlet | unconfigured and empty results log with a reason; feed depth is measured rather than assumed |
| A credibility number reads as an editorial judgement | a government customer asks what produced it and there is no answer | structural criteria only, versioned file the customer owns, ADR 0004 |
| Recommended actions assume prosecution powers | output is mis-framed for a service that does not prosecute | #57, with the design questions recorded; the Intelligence Bureau persona is the lens that catches it in review meanwhile |
| Outbound fetch follows scraped content into the internal network | a collected page reaches postgres, redis or ollama | first-hop validation landed in #43; every-hop validation is #55 |

---

## Definition of done

- Every step in the table above has landed, with tests at the seam named in the test matrix.
- `make test-unit`, `make test-integration` and `make lint` pass on CPU with default configuration.
- Every forwarded setting in the inventory appears in `settings.py`, the compose `environment:` block, and `.env.example`, and every host-only one is in the `EXEMPT_VARS` allowlist with a reason.
- ADRs 0003 and 0004 are Accepted and cited from the code they govern.
- The demonstration can be run from [demonstration_dataset_plan.md](demonstration_dataset_plan.md) without changing any capability in this document.
