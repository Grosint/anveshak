# Deferred scope register

Work deliberately excluded from a shipped epic, with the reason it was excluded and the condition that would bring it back.
A deferral recorded here is a decision, not an oversight.

---

## Epic #21 — Narrative detection, Sentiment Timeline, and Manufactured Narrative signals

### Topic to Case promotion for long-running movements

A movement that runs for months outgrows a Topic and belongs in a Case.
Cases already exist and already span multiple topics, so the promotion path is a small piece of wiring.

Deferred because no analyst has yet run a Watch Space long enough to hit the limit.
Bring it back when a promoted Topic has been active for more than one month.

### Production hardening

Five items travel together: threshold calibration against real collected volume, per-Topic scrape budgets, expiry for Candidate Topics nobody triages, backfill performance at production scale, and per-language model evaluation.

Deferred because every one of them needs production volume to tune against, and tuning them on seeded data would produce numbers that look authoritative and are not.
Bring them back once the internal-security-tension Watch Space has collected for a full month.

### Comment and reply collection

Replies carry most of the stance signal on a public post, and the Sentiment Timeline would be sharper with them.

Deferred because comment collection is thin and inconsistent across the current adapters.
Doing it properly means a per-platform scoping pass.
Bring it back as its own epic.

### Open-web trend discovery

Detection operates inside a Watch Space.
The system does not go looking for subjects nobody configured.

Deferred on purpose rather than for cost.
A system that selects its own subjects from the open web has no human-defined collection boundary, which is the property that makes the current posture defensible.

### Historical data beyond a platform search window

Several platforms expose only a recent search window, seven days on X.
Nothing recovers history from before collection started on those platforms.

Deferred because no technique recovers it.
The historical spine of the timeline comes from platforms with full history, and the constrained portion of the chart is labelled so an analyst never mistakes a data gap for silence.

### A dedicated HTTP contract test seam

The three existing seams cover this work: the analyst pipeline, the database repository, and the frontend integration seam.

Deferred because adding a fourth seam adds maintenance without covering a failure the existing three miss.

---

## Epic #39 - Historic narrative Backfill and Replay

### Recommended actions shaped for a service that does not prosecute

`build_recommended_actions` in `services/reporter/anveshak/reporter/rag.py` maps a matched template to prosecution steps: file an FIR, request a CDR, cite an NDPS or IT Act section, refer to ED under PMLA.
That is correct for the agencies the templates were written for, and wrong for a domestic intelligence consumer, which has none of those powers and produces an assessment rather than a case.

Deferred from #53, which added the Intelligence Bureau persona and left the reporter untouched, because reshaping the block is a product decision about who a report is addressed to, not a wording change.
The shape it needs is an audience on the report and an action set per audience, so an advisory-framed report and a prosecution-framed report come from the same evidence.

Bring it back when a report is generated for a non-prosecuting consumer, which the demonstration in [demonstration_dataset_plan.md](demonstration_dataset_plan.md) is the first occasion for.
The Intelligence Bureau persona is the review lens that catches it in the meantime.

### Personas beyond Intelligence Bureau

#53 added one persona and stopped.

Deferred because a persona is only worth writing when a real design decision needs that operational perspective, and an unused lens is a document that drifts out of date while looking authoritative.
Bring one back when a specific decision has no existing lens that fits.
