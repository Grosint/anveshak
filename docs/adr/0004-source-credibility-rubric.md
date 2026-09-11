# ADR 0004: Source credibility starts from structural properties, not from an editorial judgement

- Status: Accepted
- Date: 2026-09-11
- Epic: #39, #51

## Context

Every Source was created at the same neutral score of 50.

A corpus that spans international wire services, national mainstream outlets, party-affiliated publications, anonymous partisan sites and fact-checkers therefore treated all of them identically.
The credibility system had automatic drop and boost passes and an audit log, and nothing to show, because every outlet started at the same number and most never moved.

The straightforward fix, typing a score against each outlet, is the problem rather than the solution.
Assigning a number to a news outlet is an editorial act, and this platform is sold to government.
An evaluating officer who sees a partisan publication scored below a mainstream one is entitled to ask what produced the difference, and "our judgement" is not an answer that survives the question.
Neither is a number nobody can reproduce.

A score is also not inert.
`credibility_min` filters content out of a Topic, report generation carries a source snapshot, and analysts read the score as the platform's assessment of an outlet.
A scoring basis that encodes a political preference would propagate it into every one of those places, invisibly.

## Decision

A Source's credibility has two parts, and they are kept apart.

**The baseline is structural.**
It is a sum of points for verifiable properties of the outlet: whether editorial responsibility is named and contactable, whether ownership is disclosed, whether items carry authors and datelines, whether a corrections policy exists and is used, whether opinion and paid material are labelled, whether the operator of a channel can be identified.
Each property is something a reviewer can check by opening the outlet's own pages, and each is worth a stated number of points.

No property is a viewpoint, and none names an outlet or a proprietor.
Two outlets with opposing politics and the same structural properties get the same baseline.
An outlet owned by a political party meets the ownership criterion by disclosing that ownership: the criterion is the disclosure, not the owner.

The points are scaled so no combination of them reaches either end of the range.
An outlet meeting every positive criterion starts at 84, one meeting every negative at 12.
That headroom belongs to behaviour: a structural baseline that pinned a Source at 100 would leave the cross-verification boost nothing to add, and one that pinned it at 0 would make every later drop invisible.
An invariant test holds the margin, because a points change that closed it would look like an ordinary edit.

**Movement is behavioural.**
Everything after creation comes from behaviour this platform observed: amplifying content a vision model scored as a likely deepfake, corroboration across independent sources, a high ratio of unclustered items on a topic other sources cluster on.
Those run through the existing audited drop and boost functions, so every change is a row in `credibility_audit_log` (architectural rule 8).

A criterion that delegates the judgement to a third party, such as membership of an external code of practice for fact-checking, was drafted and then removed.
It is not checkable on the outlet's own pages, its admission rules belong to a body the customer neither owns nor versions, and in the Indian outlet landscape that membership is not politically inert.
It is the criterion an evaluating officer would challenge first, and the answer would be "a body we do not control decided", which is the objection this decision rejects external ratings for.

Criteria that cannot both be true of one outlet, such as carrying bylines and carrying none, declare each other in `exclusive_with`, and a declaration naming both halves is refused.
A repeated property is refused too.
Both would otherwise produce a number that reads like a considered middle rather than like the file being wrong.

**The rubric is configuration the customer owns.**
The criteria and the per-outlet assessments live in `infra/configs/credibility/source_rubric.yaml`, versioned, with the path read from `SOURCE_RUBRIC_PATH`.
Nothing in code knows an outlet by name.
The vendor drafts the criteria; the agency accountable for the assessments owns and edits them, and an edit is a change to a reviewed file rather than a change to code.

Getting an edit into a running deployment differs by environment, and the ADR states it rather than implying it is instant.
The API image carries a copy of the file, so a container starts without a mount.
The development Compose file bind-mounts the host directory read-only over it, so an edit on the host is the file the API reads after a restart; the loader caches per process.
Production has no such mount on purpose: the rubric publishes scores to a customer, so it ships through the same review and image build as anything else that does, and the deployed file is exactly the one in the repository at that tag.

**The assessments ship empty.**
An assessment invented by the vendor for outlets it has not reviewed would be exactly the unaccountable scoring this decision replaces.
An outlet absent from the file has no structural baseline, its Sources are created at the neutral score, and that is logged at INFO with its reason, because a Source quietly created at the neutral score is indistinguishable, on the row, from one assessed as thoroughly ordinary.

## Consequences

`sdk/anveshak/source_rubric.py` is the single resolution point for the score a Source is created at.
The three creation paths, the API, the catalog approval route and the corpus importer, all call `creation_score()`, which returns the score and the basis for it: `stated`, `rubric` or `neutral`.
Each logs which one applied.
An explicitly stated score still wins, because an operator who typed a number meant it.

A Source the rubric placed carries an audit row recording that, written in the same transaction as the insert, with `old_score` set to the neutral score it would otherwise have been created at.
Creation is not a change, so architectural rule 8 does not require it.
It is written anyway, because without it the only record of why a Source starts at 60 is a log line, and the audit log an analyst opens to answer a challenge would be empty for exactly the Sources the rubric placed.
A stated score writes no such row, since the rubric did not place it, and an operator overriding an outlet the rubric does assess is logged at WARNING.

`scripts/apply_source_rubric.py` applies a baseline to Sources that already exist.
It writes the score and its audit row in one transaction, and the row names the rubric version and every property the baseline was built from, so an analyst challenged on a score answers with its basis rather than with the word "rubric".
It writes nothing without `--apply`.

It refuses to touch a Source whose baseline has already been applied, which it detects from the `changed_by` prefix on the audit row.
Once a baseline is set the behavioural passes own the score, and a second run that reset every Source to its structural number would erase observed behaviour, silently, with an audit row that read like an ordinary application.
`--rebaseline` overrides that for the case where the rubric itself changed, and says so in the reason it writes.

A Source is a global entity, so one handle can carry a score several organisations see through `org_sources`, while its audit row lands under the organisation that owns the row and `credibility_audit_log` is under row-level security.
An unscoped run therefore moves scores an analyst in another organisation sees, with an audit trail they cannot read.
`--org-id` scopes a run for that reason, defaulting to `SEED_ORG_ID`; with neither set the run walks every organisation, which is right for a single-tenant deployment and is stated rather than assumed.

A rubric file that is present but wrong raises rather than degrading.
A rubric that quietly dropped an unrecognised property would score an outlet on fewer properties than the file claims, and the resulting number would still look considered.
Every declaration is scored when the file loads, so a bad one fails once, at load, rather than on the first Source that happens to name that outlet.
The API reads the rubric in its lifespan for the same reason: a malformed file fails the container's start rather than surfacing as an opaque 500 on a registration.
A missing file is different: it logs and yields an empty rubric, so every outlet reads as undeclared and Sources keep the neutral score they would have had anyway.
A configured path that does not exist falls back to the shipped copy and says so at WARNING, since silently handing back the vendor's file is how a typo in an operator's path becomes an assessment nobody made.

The points are a judgement, and the decision does not pretend otherwise.
What it fixes is that the judgement is now about which structural properties matter and how much, stated once in a file anyone can read, rather than about individual outlets, restated silently every time one is registered.

## Alternatives considered

**Score outlets by editorial judgement.**
Rejected as indefensible in this deployment, for the reason in the context: the first person asked why an outlet scores as it does has no answer, and the answer would in any case be a political one.

**Import an external rating.**
Existing outlet rating services are mostly United States-centric, have thin and inconsistent coverage of Indian outlets, and carry licence terms and a dependency this platform's sovereignty requirement does not accept.
It would also move the same unanswerable question one step away rather than answer it.

**Classify outlets with a model.**
A model trained on outlet reputation reproduces the priors of whatever it was trained on, cannot state the basis for a score, and would fail the same challenge with an extra layer of opacity in the way.

**Score only on behaviour, with no baseline.**
Considered seriously, since behavioural movement is the defensible part.
Rejected because a corpus has to run for some time before behaviour separates anything, and until then every outlet is identical, which is the problem being solved.
A structural baseline gives the behavioural passes something to move.

**Put the assessments in the corpus file.**
Rejected because the assessment is a property of the outlet rather than of a dataset.
The same outlet appears in several corpora and in live collection, and three copies of an assessment drift.
