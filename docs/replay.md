# Replay

Ingesting a committed corpus in chronological stages, running detection between them, so that detection unfolds in the order the story did.

Issue #47.
The driver is `scripts/replay_corpus.py`, the importer under it is `scripts/import_corpus.py`, and the clock it runs against is [ADR 0003](adr/0003-virtual-clock.md).

## Why not a single import

A bulk import of a historic corpus produces the wrong result even when every timestamp in it is correct.

Candidate Topic promotion requires persistence across clustering runs, and a bulk import gives one run.
Hostility shift requires a prior baseline, and a bulk import has none.
The end state arrives with none of the history that makes it meaningful, and the platform's claim to show what it would have told an analyst on a given day is then false.

## What a stage is

A stage is one week of the corpus by Publication Time.

Stages are contiguous and anchored at UTC midnight of the earliest Publication Time in the corpus, so a boundary is a date rather than a time of day.
A week with no items is still a stage: a quiet week is evidence, and dropping it would compress the timeline into something the story did not do.

Weekly rather than daily, because a week gives the persistence and novelty gates enough runs to behave normally and the timeline real slope, without paying for clustering and language model labelling on CPU once per day.
`--stage-days` changes it, and nothing else in the driver assumes seven.

The stage's reference time is the end of its week.
Where a stage ends after today, which the last stage of a still-running narrative does, the reference time is pulled back to now and the run logs `replay.reference_time_clamped`: the clock refuses a reference time in the future.

## What a stage runs

| Step | What it does | Where it runs |
|------|--------------|---------------|
| import | The week's items, through `ingest_raw_item` | this process |
| embed | Waits for the analyst worker to embed them | `analyse-worker` |
| cluster | Near-duplicate detection, then Leiden, at the stage's clock | this process |
| signal | Every detector, at the stage's clock | this process |
| candidate | One Candidate Topic detection pass, at the stage's clock | this process |
| report | Only at a stage carrying a requested report date | `report-worker` |

Clustering and the Signal detectors are called in process rather than dispatched, which is what ADR 0003 describes: the reference time is a parameter on those functions, so one pass reads and writes a single moment.
Labelling is enqueued exactly as the scheduler's own cluster loop enqueues it.
Cross-verification is not: it writes credibility, and a boost landing at whatever point the worker reaches it would change the `credibility_score_at_capture` of whichever later stage it overtook, so two runs of the same corpus would not agree.
It runs in this process, at the stage's clock, before the stage's Signals.
Embedding stays in the analyst worker, because that is where the models are.

Capture Time is the stage's reference time rather than the run's.
The hostility shift Signal compares a recent window against a prior one and both filter Capture Time, so a corpus imported in one moment measures a delta of zero however correct its Publication Times are.

Report generation happens only at the stages carrying a `--report-date`, one report at a time and awaited, because concurrent report generation on CPU is known to time out.

## Reset

A Replay resets first, always.

An incremental re-run drifts from the corpus and leaves an operator unable to say which run produced an artifact, so resuming is not offered: recovery from a failed stage is a re-run, which resets.

The reset deletes, in foreign key safe order and scoped to one organisation: vision results, media assets, extracted entities, report warnings, reports, near duplicates, Signals, Candidate Topics, identifier clusters, Narrative Clusters, topic content links, content items, analysis jobs, discovered Sources and content archive rows.
It then restores each Source's credibility score to the value it held before this organisation's first audited change, and deletes that audit trail in the same transaction.
Architectural rule 8 forbids a silent credibility change, and this leaves no unlogged delta, because the changes being reversed and the rows recording them go together.
Without the restore a re-run would start from drifted scores and produce different Signals from the same corpus.

The restore is bounded to Sources this organisation owns.
A Source is a global entity, and its audit row carries the owning organisation rather than the one whose Replay moved the score.
A wider restore would overwrite a value another organisation's own assessment produced and leave their audit rows describing a score the row no longer holds.
Their drift stays, with its trail intact, which is the recoverable half of the two.

Topics and Sources survive, and so do Trackers and Source assessments.
A Watch Space is configuration the Replay imports into and does not create, a Source is a global entity another organisation may see through `org_sources`, and an analyst configures the other two.

`reset_org_state` carries the environment guard itself rather than trusting its caller, because it is importable.

## The guard

The driver refuses to start unless `VIRTUAL_CLOCK_ENABLED` is true **and** `ENVIRONMENT` is on `VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS`.
Two layers, for the reason [ADR 0002](adr/0002-cloud-model-guard.md) gives: one flag copied from a Replay host into a production `.env` would otherwise be the whole gate.
The check runs before the reset, so a Replay that cannot run destroys nothing on the way to finding that out.

Two further refusals sit beside it.

`ANVESHAK_ALLOW_REPLAY_RESET=1` must be set in the environment the driver runs in.
The clock guard describes the host, not the database `POSTGRES_URL` points at, and a development shell whose `ENVIRONMENT` is on the allowlist passes it while aimed at a production DSN.
This one has to be typed, and cannot be satisfied by a `.env` somebody copied.

A Replay refuses to start where another organisation has an active Topic.
The Signal detectors and Candidate Topic detection sweep every active Topic on the deployment, exactly as the scheduler runs them, so during a Replay they would write Signals dated months ago against Topics that organisation never replayed, and the reset is scoped to one organisation so nothing would remove them.
`--allow-shared-host` accepts that, which is what a development machine full of test fixtures needs and what a demonstration host should never need.

## Live detection is suspended on a Replay host

Where a Replay could run, meaning `VIRTUAL_CLOCK_ENABLED` is on **and** the environment is on the allowlist, every pass that would write detection output at the wall clock stops and logs why:

- `cluster_loop`, `signal_check_loop`, `convergence_loop` and `content_retention_loop` in the analyst scheduler
- `detect_candidate_topics_job`, `run_contradiction_scoring` and `update_source_credibility` when dispatched without a reference time, which is what identifies a cron dispatch
- `check_scheduled_reports` in the reporter

This is not tidiness.
The 24 hour Signal dedup window is measured back from the pass's reference time and has no upper bound, so a single Signal dated today suppresses every stage Signal for that cluster for the rest of the Replay.
The persistence gate counts detection passes, so an hourly live pass promotes a Candidate Topic the Replay's own stages never promoted.
And a re-run after a reset stops reproducing the first run, because the number of live passes that landed between stages is a function of how long the operator took.

Content retention is the sharpest of them: it measures Capture Time against the wall clock and then deletes, and a Replay's Capture Times are months in the past, so its first tick would archive and delete the corpus the Replay was run to produce.
Cluster archival was already suspended under the same flag, for the reason ADR 0003 gives.

The test for suspension is the same two layers a Replay itself has to pass, not the flag alone.
A host with the flag set in an environment off the allowlist refuses every override, so no Replay can run there and there is nothing to protect; suspending live detection there would stop a production pipeline over a stray flag.
Which clock is in use, and whether live detection is suspended, is logged at INFO at worker startup.

## Running one

```bash
# On a deployment with ENVIRONMENT=replay and VIRTUAL_CLOCK_ENABLED=true
export POSTGRES_URL=postgresql://anveshak:...@localhost:5433/anveshak
export ANVESHAK_ALLOW_REPLAY_RESET=1
uv run python scripts/replay_corpus.py corpora/cjp.jsonl \
    --topic-id 1f2e... \
    --org-id org-demo \
    --report-date 2026-07-25 \
    --report-date 2026-09-03 \
    --report-type intelligence_brief \
    --report-type research_summary
```

`--report-type` is repeatable, and every requested format is generated at every report date, one at a time and awaited.
Both formats have to come out of one run: a second run to collect the other format is a second reset, so the first run's reports would no longer exist to compare against.
A format asked for twice is generated once, because a report is immutable once generated and the second is a duplicate row rather than a refreshed one.

The database URL comes from the environment and never from a flag, because a DSN on argv is a password in `ps` output and in shell history.

Progress is one line per stage, carrying `[3/17]` and the stage's dates, so a stage that hangs is obvious in a run that takes hours.
A stage reports items imported, items already present, clusters, Signals and Candidate Topics, and reports the number still unembedded when the analyst worker stopped making progress: the quality gate skips embedding for boilerplate, and those items never cluster.

Exit codes: `0` success, `1` a stage or the corpus failed, `2` the Replay was refused by a guard.

## Testing

- `tests/unit/test_replay_driver.py` for staging, refusals and the reset order
- `tests/unit/test_live_pass_suspension.py` for the suspended live passes
- `tests/integration/test_replay_driver.py` for the database seam: Signals dated to their stage, a Candidate Topic that waits for the persistence gate, and a reset plus re-run reproducing the first run's counts

The integration test injects embeddings rather than waiting for the analyst worker, which is what makes clustering deterministic enough to compare two runs.
