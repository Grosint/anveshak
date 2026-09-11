# Cockroach Janta Party dataset and demonstration plan

Epic #39.
Dataset sub-issues #40 and #52, whose code is on `feature/narrative_signal`, and #54, whose tooling is on the same branch and whose collection run has not been made.
All three GitHub issues are still open.

This document is written once and read at the start of every session that works on the dataset half of this epic.
A session needs three lines: read this plan, state the step, run the step.

The capability half lives in [historic_backfill_plan.md](historic_backfill_plan.md).
Nothing in this document adds a product capability.
Everything here is collection, configuration and a run, and the separation exists so that a reader looking for a shipped feature never has to read a demonstration document to find it.

Vocabulary is in [CONTEXT.md](../CONTEXT.md).
Operator documentation for the mechanisms this plan drives is in [replay.md](replay.md) and [corpus_format.md](corpus_format.md).
The demonstration order is in [run_sheet.md](run_sheet.md).

The machine-readable half of this plan is `infra/configs/corpora/cockroach_janta_party.yaml`.
It carries the arc, the phases, the report points, the expected Signals and the collection targets, and it is read by `scripts/build_corpus.py` and by `scripts/assert_demo_run.py`.
This document is the reasoning; that file is what the two programs agree on.
Editing an expectation in it after a run that missed the expectation defeats the arrangement, so a miss is recorded in [tuning_history.md](tuning_history.md) instead.

---

## The claim, and what it forbids

The claim made to an evaluating officer is that the platform surfaced the narrative unaided.

That claim is load bearing, it is the first thing a customer checks, and it constrains the dataset more than any technical decision in this plan:

1. No Watch Space names the organisation, its leaders, or its slogans.
   A customer reads the configuration.
2. No Signal is pre-seeded.
   Every Signal in the demonstration is one detection produced from the corpus.
3. No timestamp is fabricated.
   Every Publication Time comes from the item, and every detection timestamp comes from the Replay stage that produced it.

A Signal that does not fire on real data is a finding to investigate, not a threshold to tune away.
Recording the expectations before the run, in this document, is what makes that distinction possible after it.

---

## The arc

The subject is the Cockroach Janta Party, a real and heavily documented movement.
The arc is 117 days from the founding on 16 May 2026 and is still running, so the corpus has a freeze date rather than an end.

| Phase | Dates | What happened |
|-------|-------|---------------|
| 1 | 15 to 31 May 2026 | A Chief Justice of India remark on 15 May, the movement founded the following day |
| 2 | June 2026 | Growth online, and the block of the movement's primary social account for part of the period |
| 3 | 1 to 19 July 2026 | Street mobilization, calls to assemble |
| 4 | 20 July 2026 | The Sansad Chalo march and the police action |
| 5 | 21 to 31 July 2026 | The Education Minister resigned on 25 July |
| 6 | August 2026 | Consolidation, counter-narrative and impersonation activity |
| 7 | 1 to 10 September 2026 | The split into a breakaway faction on 3 September |

If the story moves before the demonstration date the corpus is extended and the Replay re-run from reset, never appended to, because a partial re-run leaves detection output from two different corpora in one database.

---

## Corpus composition

Languages are English and Hindi, and Hindi content is analysed in Hindi rather than through a translation.

| Layer | Route | Note |
|-------|-------|------|
| News | archive Backfill, then article body fetch | the three discovery routes in the capability plan; Wayback rehydration only where a publisher 4xxs |
| Primary social account | adapter paging on a dedicated collector account | the movement's own timeline |
| The blocked period | placed by hand from cited reporting and archives | not reachable through the platform interface, and the block leaves a gap in the account's own timeline |
| Third social platform | conditional | collected only if a real channel exists; absent otherwise, and recorded as absent |
| Counter-narrative and impersonation | the same routes as above | needed for user story 5, and it is material about the movement rather than by it |

Each item carries its Publication Time and the name of the signal that produced that time, per [corpus_format.md](corpus_format.md).
An item with no recoverable Publication Time is stored with a NULL rather than a guess, and counted.

The corpus file is committed.
The post-Replay database dump is not: it is held outside version control under a specifically named ignored path, never a blanket pattern, because a blanket `corpora/` or `dumps/` rule silently excludes same-named packages elsewhere in the tree.
See the `git-build` skill.

---

## Watch Spaces

Two, and neither names the subject.

| Watch Space | State | File |
|-------------|-------|------|
| Internal security tension | unmodified, pre-existing | `infra/configs/watch_spaces/internal_security_tension.yaml` |
| Youth grievance | added in #52 | `infra/configs/watch_spaces/youth_grievance.yaml` |

The second exists so that discovery is not one tuned case.
A single Watch Space that happens to surface the subject is indistinguishable from a Watch Space written to surface it.

Seeded with `scripts/seed_watch_space.py`, asserted by `tests/unit/test_watch_space.py` and `tests/integration/test_watch_space_seed.py`, which include the assertion that no keyword names a known organisation or person.

---

## Sources

Sources are created before import, with structural credibility baselines from the rubric, per ADR 0004.
The corpus spans international wire services, national mainstream outlets, party-affiliated publications, anonymous partisan sites and fact-checkers, and the rubric is what makes the differences between them answerable.

Baselines are applied with `scripts/apply_source_rubric.py`, which writes a `credibility_audit_log` row per change, per architectural rule 8.
Credibility movement during the Replay is behavioural and audited, never typed in.

---

## Replay

Weekly stages across the arc, which is 17 stages, with detection between each.
Driven by `scripts/replay_corpus.py`, on a deployment with `ENVIRONMENT=replay`, `VIRTUAL_CLOCK_ENABLED=true` and `ANVESHAK_ALLOW_REPLAY_RESET=1`.

Reports are generated at three points, each in both the brief and the full format:

| Report point | Reference date | Why this date |
|--------------|----------------|---------------|
| 1 | late May 2026 | the narrative as it looked in its first fortnight, when an early warning would have been useful |
| 2 | late July 2026 | after the march, the police action and the resignation |
| 3 | early September 2026 | after the split |

Three Reports with distinct `generated_at` values are what demonstrate an assessment changing over the life of a narrative rather than a snapshot.
Report immutability is architectural rule 4, so a Report is never regenerated in place, and the run therefore produces new Reports rather than refreshing old ones.

---

## Expected Signals per phase

Written before the collection run, per epic #39.
This table is the prediction, and the run is the measurement.

| Phase | Expected Signals | Reasoning |
|-------|------------------|-----------|
| 1 | `new_cluster`, then `threshold_crossed` | founding coverage reaches three independent sources within the fortnight |
| 1 | a Candidate Topic raised from a Watch Space and promoted | the four promotion gates pass once the founding cluster persists across two runs |
| 2 | `manufactured_narrative` | item and account counts climb while independent source count stays flat, which is what an account-driven growth phase looks like |
| 2 | `credibility_drop` | partisan and anonymous sites carry claims the mainstream record contradicts |
| 3 | `mobilization_call` | explicit calls to assemble, in Hindi destination idiom as well as English, citing the phrase that fired |
| 4 | `hostility_shift`, `mobilization_call`, `threshold_crossed` | the march and the police action are the sharpest week in the arc on every measure |
| 5 | `threshold_crossed` | the resignation is carried by every outlet, so independent source count peaks |
| 6 | `manufactured_narrative` on the counter-narrative cluster | impersonation and counter-messaging is amplification, not reporting |
| 7 | `new_cluster` for the breakaway faction, passing the novelty gate | a split is a genuinely new narrative rather than a rediscovery of the parent |

A Signal in this table that does not fire is investigated at the seam, and the finding is recorded in `docs/tuning_history.md` whether or not it changes a threshold.

Two known limits that may show up here rather than as a defect: transliterated mobilization patterns are unreachable on an item the detector labels `hi`, which is #56, and the mobilization confirmation step ships disabled until its labelled set exists, so the lexicon runs alone.

---

## Phases

### Phase 0 - Decisions before the run
The corpus contains material authored by identifiable people in a matter still before the courts.
Its classification labels, and whether the artifact may leave the build machine, are decided here and not at demonstration time.
Exit criteria: both recorded in writing, and the collector account and its OPSEC posture agreed.

### Phase 1 - An honest starting database, Watch Spaces and Sources
Issues #40 and #52, both landed, plus Source creation.
#40 is the precondition for everything else: the pre-existing demonstration seed fabricated Signals and left Publication Time unset, and a database that already contains invented Signals cannot demonstrate that detection produced any.
Exit criteria: no Signal in the seed that detection did not produce, asserted by `tests/unit/test_demo_seed_honesty.py`; every seeded content item carrying a Publication Time; two Watch Spaces seeded with no keyword naming the subject; and every Source created at a rubric baseline with an audit row.

### Phase 2 - Collection
Not run.
`scripts/build_corpus.py` collects the news layer through the archive Backfill route and merges the hand-placed layer, and it refuses to start until the collection targets in the plan file are pinned and every outlet has an `OUTLET_BACKFILL` entry.
Both refusals are the point: a guessed channel identifier collects a copycat channel, and an unconfigured outlet discovers nothing and reads as an outlet that published nothing.
The run itself reaches the public internet, so it happens on a machine where that is intended and after Phase 0's OPSEC decision, not on a demonstration host.

The movement's video channel holds more videos than `YOUTUBE_BACKFILL_COUNT` defaults to, so the collection run raises it in the environment for that run: `YOUTUBE_BACKFILL_COUNT=200`.
The service default stays where it is, because this is one collection rather than a new deployment-wide collection width.

Exit criteria: the corpus covers all seven phases with no week empty, Publication Time present on every news item with the NULL count stated, and every Hindi item labelled in Hindi rather than as English.

### Phase 3 - Freeze
The dump path is named in `.gitignore` by exact path: `/artifacts/replay/cockroach_janta_party.dump`.
`make replay-freeze` writes it and `make replay-restore` reads it back, so a repeated demonstration restores in minutes rather than re-running the Replay for hours.
Both read the path from the plan's `output.dump_file`, so it is stated once; `.gitignore` repeats it literally because it cannot read a YAML file.
The restore drops and replaces every table, so it carries the same typed `ANVESHAK_ALLOW_REPLAY_RESET=1` guard the Replay's own reset does.
The dump is the whole database, including the users table, which is what Phase 0's decision about whether the artifact may leave the build machine is about.

Exit criteria: the corpus file committed, its item count and date histogram recorded here, and a dump path named in `.gitignore` by exact path.

### Phase 4 - Replay
`--report-type` is repeatable, so one run produces both formats at each of the three report points.
A second run for the other format would be a second reset, and the first run's reports would no longer exist to compare against.

Exit criteria: 17 stages completed, exit code 0, per-stage counts recorded, and a reset plus re-run reproducing the first run's counts.

### Phase 5 - Reports
`make demo-assert` checks the three points in both formats, with distinct generation timestamps.

Exit criteria: three Reports at the three reference dates, in both formats, each carrying its source snapshot, and the three report points distinct in `generated_at` within each format.
The two formats at one point share a `generated_at`, because the Replay generates both at that stage's reference time: they are the same moment assessed twice, which is what rule 4 means by a point-in-time snapshot.

### Phase 6 - Run sheet
Written, in [run_sheet.md](run_sheet.md), with its timings marked as estimates until the first execution corrects them.

Exit criteria: the demonstration order written down, timed, and run once end to end by someone who did not build it.

---

## What the run asserts

The run is the test.
After the Replay, assert against the database:

1. A Candidate Topic was raised from a Watch Space and promoted.
2. Signals of each expected type exist, with timestamps inside the phase the table above predicts.
3. The Sentiment Timeline returns non-empty buckets across the arc, with a stated excluded count.
4. Three report points exist in each format, distinct in generation time from each other.
5. A reset plus re-run reproduces the first run's counts.

Surfaces expected to be empty are asserted empty rather than quietly ignored: vision, deepfake and the geographic map, which a text corpus is not expected to populate.
An honest empty state is part of the demonstration, because it tells an evaluating officer what the platform does not have.

Each assertion is made at a seam that already exists, so the run adds no new test mechanism:

`make demo-assert` runs assertions 1 to 4 and the empty-surface checks against the database, reading the same plan file the corpus was built from.
Assertion 5, a reset plus re-run reproducing the counts, is the Replay's own integration test.

| Assertion | Seam | Prior art |
|-----------|------|-----------|
| Watch Spaces seeded, no keyword naming the subject | database, after seeding | `tests/integration/test_watch_space_seed.py`, `tests/unit/test_watch_space.py` |
| Corpus imported, new against present against missing | ingest, against a real database | `tests/integration/test_corpus_import.py` |
| Signals dated to their stage, reset plus re-run reproducing counts | database, after a Replay | `tests/integration/test_replay_driver.py` |
| No Signal written by a seed script | seed honesty | `tests/unit/test_demo_seed_honesty.py` |
| Expected Signals, promotion, timeline, report points, empty surfaces | database, after a Replay | `scripts/assert_demo_run.py`, `tests/unit/test_demo_run_assertions.py` |
| The plan itself is answerable: no phase gap, no unknown Signal type | the plan file | `tests/unit/test_corpus_plan.py` |
| An impostor domain, an uncited hand-placed item, an unconfigured outlet | the build | `tests/unit/test_build_corpus.py` |
| Three Reports with distinct `generated_at` | reporter | existing Report immutability tests |

---

## Commands

| Step | Command |
|------|---------|
| Seed a Watch Space | `uv run python scripts/seed_watch_space.py infra/configs/watch_spaces/youth_grievance.yaml` |
| Apply Source baselines | `uv run python scripts/apply_source_rubric.py` |
| See which collection targets are still unpinned | `make corpus-plan` |
| Build the corpus | `make corpus-build` |
| Import a corpus without staging | `uv run python scripts/import_corpus.py <corpus> --topic-id <uuid> --org-id <org>` |
| Run the staged Replay | `uv run python scripts/replay_corpus.py <corpus> --topic-id <uuid> --org-id <org> --report-date ... --report-type intelligence_brief --report-type research_summary` |
| Assert the run against this plan | `make demo-assert`, or `make demo-assert TOPIC_ID=<uuid>` |
| Freeze the result | `make replay-freeze` |
| Restore a frozen run | `ANVESHAK_ALLOW_REPLAY_RESET=1 make replay-restore` |
| Check the demonstration database | `make demo-check` |
| Assert the seams above | `make test-integration` |

`POSTGRES_URL` and `REDIS_URL` come from the environment and never from a flag, because a DSN on argv is a password in `ps` output and in shell history.
The Replay host needs `ENVIRONMENT=replay`, `VIRTUAL_CLOCK_ENABLED=true` and, for a reset, `ANVESHAK_ALLOW_REPLAY_RESET=1`.

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| A Watch Space keyword names the subject | the unaided-detection claim is false, and checkable in one file | keyword assertion test, two Watch Spaces rather than one |
| An expected Signal does not fire and a threshold is tuned to make it | the demonstration measures the tuning, not the platform | this table is written before the run; a miss is recorded in `docs/tuning_history.md` as a finding |
| The story moves before the demonstration | the corpus ends mid-arc, or is appended to and mixes two runs | extend the corpus and re-run from reset, never append |
| A stage hangs on CPU | a run that takes hours stalls unnoticed | per-stage progress line with `[n/17]` and the stage dates; unembedded count reported per stage |
| Concurrent Report generation times out on CPU | the three Report points fail late in the run | one generation at a time, as the demo seed pattern already requires |
| The blocked-period content is placed without a citation | a fabricated timestamp inside a corpus that claims none | each hand-placed item carries the reporting or archive it came from, or it is not placed |
| The dump reaches version control | a database dump of material about identifiable people enters every clone | exact-path ignore rule, verified before the freeze commit |
| Hindi content is collected but read as English | the assessment describes half the discourse | language label checked per item at Phase 2 exit, and #56 is the known gap |
| Live collection runs during the demonstration | the demonstration stops being reproducible | the dataset is frozen, and live scraping is out of scope for the run |

---

## Definition of done

- The corpus is committed, and its item count, date histogram and NULL Publication Time count are recorded in this document.
- The Replay runs to completion from reset with exit code 0, twice, with matching counts.
- Every expected Signal either fired, or has a recorded finding explaining why it did not.
- Three Reports exist at the three reference dates, in both formats.
- The run sheet exists and has been executed once by someone who did not build the dataset.
- No Signal in the demonstration database was written by a seed script.
