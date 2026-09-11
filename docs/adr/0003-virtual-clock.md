# ADR 0003: Detection takes a reference time, rather than reading the system clock

- Status: Accepted
- Date: 2026-09-11
- Epic: #39, #46

## Context

Detection was written against the system clock.
Clustering, Signal and mobilization queries filtered on Capture Time relative to `NOW()`, and Signal, Narrative Cluster, Candidate Topic and credibility audit rows defaulted their timestamps to `NOW()`.

That is correct for live collection and impossible for a historic corpus, in two directions at once.

Set Capture Time to the historic date, so that detection output dates correctly, and every relative window excludes everything.
Nothing fires, so there is no output to date.

Set Capture Time to the import time, so that detection fires, and every Signal is dated the day of the import.
An analyst navigating back to the day an event occurred finds nothing, and the platform's claim to show what it would have told them then is false.

The hostility shift Signal is the sharpest case.
It compares a recent window against a prior one, which measures nothing when every item was captured in the same minute.

A secondary consequence is that none of these paths could be tested without freezing the system clock, so time-dependent behaviour had no deterministic test.

## Decision

The reference time is an explicit parameter on the detection query paths and on the functions that write detection output.
It defaults to the current time, so live behaviour is unchanged and the live path needs no flag.

1. `resolve_reference_time()` in `sdk/anveshak/clock.py` is the single resolution point.
   Passed nothing, it returns `datetime.now(UTC)`.
2. Detection SQL takes the reference time as a bind parameter.
   `NOW() - INTERVAL '24 hours'` becomes `$n::timestamptz - INTERVAL '24 hours'`, so a pass reads and writes one consistent moment.
3. One pass resolves the reference time once, at its entry point, and threads that value through every query and every write it performs.
   A loop that read the clock per iteration would date rows from the same pass differently.
4. An override is gated behind `VIRTUAL_CLOCK_ENABLED`, which defaults to false, and refused outside `VIRTUAL_CLOCK_ALLOWED_ENVIRONMENTS`.
   Two layers, for the reason ADR 0002 gives: one flag copied from a Replay host into a production `.env` would otherwise be the whole gate.
   A reference time in the future is refused too, since a Replay runs over history and a row dated ahead of now keeps matching every "since `NOW() - interval`" query forever.
   Which clock is in use, and why, is logged at INFO at worker startup.
   Supplying a reference time while the flag is off raises `ClockOverrideRefusedError` rather than falling back to the wall clock.
   Falling back would date a whole Replay stage the day it ran, silently, which is the failure this work exists to remove.
5. A naive timestamp is refused even with the flag on, for the reason the corpus importer refuses one: a guessed zone moves the reference across a day boundary, and a day is the unit an analyst reads.
6. ARQ jobs carry the reference time as an ISO-8601 string with an offset.
   An unparseable value is refused; it never degrades to live time.
7. Report generation timestamps are set from the same reference time.
   This honours architectural rule 4, which forbids updating `generated_at` but says nothing against setting it correctly when the report is created.

Tables in scope: `signals`, `narrative_clusters`, `candidate_topics`, `credibility_audit_log` and `reports`.

An `updated_at` is monotonic. A pass that touches a row created by an earlier live run writes `GREATEST(updated_at, reference)` rather than assigning, because a Replay runs at a past moment and a plain assignment would drag a live cluster's `updated_at` backwards into the range the scheduler's staleness archival collects.

A window gains a lower bound from the reference time and keeps no upper bound.
`captured_at >= reference - interval` rather than that plus `captured_at <= reference`.
This is deliberate and it follows from what Capture Time means: a Backfill's Capture Times are all the day it was loaded, which is later than any reference time a Replay stage uses.
An upper bound would therefore exclude the entire corpus at every stage.
What limits a stage to its own content is the staged import, not a filter.

## What this is not

The reference time dates a report and anchors the windows inside it that are relative, such as "trending keywords from the last 7 days".
It does not bound a report's evidence to a date range.
A report generated at a past reference time still draws its RAG chunks and its evidence appendix from everything collected, so it reads as an assessment written on that date from the whole corpus, not as the assessment that date's corpus alone would have produced.
Restricting a report to an arbitrary historic date range is a separate capability in #39 and needs the report's own `time_window_start` and `time_window_end`, which this work does not touch.

A window over a collection-time column widens during a Replay rather than moving.
`content_items.captured_at`, `content_items.created_at` and `vision_results.processed_at` all record when Anveshak acted, not when the story happened, and a Backfill sets them to the day it ran.
Measured back from a past reference time, those windows therefore admit everything imported so far rather than a 24 hour or 7 day slice of it.
What bounds a stage is the staged import.
The honest bound is Publication Time, which is #39's work and not a column these queries can filter on yet.

This has a sharp consequence for the hostility shift Signal, which is the case that motivated the work.
Its baseline and its recent window both filter `captured_at`, so unless the corpus carries per-stage Capture Times they select the same rows and the delta is zero.
The Replay driver has to stage its import for that Signal to mean anything; the clock alone is not sufficient for it.

A report generated at a past reference time has `generated_at` earlier than its own `created_at`, because the row is created live when an analyst asks for the report and generated at the reference time.
`generated_at` is also taken once at the start of the job rather than at the write, so the row, the PDF footer and the relative windows inside the report all agree on one moment.
For a live report that shifts the value by the generation duration, which is the price of the row and the artifact never disagreeing.

Timestamps on enrichment that is not detection output stay on the wall clock: `content_items.label_generated_at` from the labeller, the mobilization confirmation labels, the per-topic relevance calibration.
Each records when a model ran, which is a fact about the deployment rather than about the story.

The Signal engine loop is a live poller and takes no reference time.
A Replay produces Signals by calling the detector functions directly with its own pool and reference time, which is what makes them a parameter rather than a setting read inside the loop.

## Consequences

A Replay stage runs detection at the date its evidence existed, so a Signal carries that date and hostility shift is measured against the period that actually preceded it.

Time-dependent behaviour is testable at a fixed reference time, by passing the parameter, without freezing the system clock.

Every live dispatch omits the parameter, so live operation is identical to what it was, and the flag it would need is off in every deployment.

Cluster archival by staleness is suspended wherever the flag is on, and logs that it is.
Archival measures `updated_at` against the wall clock, and a Replay writes clusters stamped months ago, which the next tick would archive; every downstream query filters `archived_at IS NULL`, so the clusters would form and then no Signal would fire, with nothing to say why.

The parameter is threaded rather than injected as a global or a module-level clock object.
A global would be reachable from any code path, including ones that must never be backdated, such as Capture Time on collection.
The parameter makes the reachable surface exactly the set of functions that declare it.

Nothing here backdates a row after it is written.
The reference time is supplied when detection runs and the row is written once with it.
Rewriting existing rows to a different date is rejected outright, because a record of what the platform said, and when, is the thing an evaluating officer is being asked to trust.

A future reader who finds a `reference_time` parameter threaded through detection should not remove it as dead configuration, and should not reach for it to change a timestamp a live deployment produced.
