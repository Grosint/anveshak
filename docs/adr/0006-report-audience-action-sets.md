# ADR 0006: A report is addressed to a service, and its recommended actions are that service's

- Status: Accepted
- Date: 2026-09-12
- Epic: #39, #57

## Context

`build_recommended_actions` mapped a matched scam template to a fixed list of steps: file an FIR under IT Act 66C, request a CDR for the identified numbers, report to SEBI surveillance, coordinate with NCB for a controlled delivery, refer to ED under PMLA.
Each matched template also appended its legal provisions as the reader's own.

That is correct for the agencies the templates were written for.
It is wrong for a domestic intelligence consumer, which has none of those powers.
Its output is an assessment for a decision maker rather than a case file: an early-warning note, a movement profile, a periodic brief.
A report that opens by telling such a reader to file an FIR is mis-framed in the first line an officer reads, and that is the kind of error that costs credibility in an evaluation rather than merely being unhelpful.

The block was also unconditional.
Every report for every audience got the same action set for a given template, so the same evidence could not be framed two ways.

## Decision

**A report has an audience, and the audience owns the actions.**

The audience sits on the organisation, in `organizations.report_audience`, not on the report request and not on the Topic.
A deployment serves one service, and every report it generates is addressed to that service, so an audience per request would be a question the analyst answers identically every time and gets wrong once.
A shared deployment with several organisations still works, because the column is per organisation.

The column is nullable and there is no CHECK constraint on it.
The set of audiences is defined in a file the customer owns, and a constraint in the schema would mean a migration every time they add one.

**The action sets are configuration, not code.**

`_TEMPLATE_ACTIONS` is now `infra/configs/audiences/report_actions.yaml`, versioned, keyed by audience and then by matched template, with the path read from `REPORT_AUDIENCE_CONFIG_PATH`.
This follows ADR 0004 and the concern taxonomy: the image carries a copy so a container starts without a mount, and the development Compose file bind-mounts the host directory read-only over it, picked up on restart because the loader caches per process.
Nothing in code knows an audience or a template by name.
Adding an audience is a file change.

The actions themselves stay curated and human-reviewed rather than LLM-generated, for the reasons in `.agents/skills/learned/references/template-driven-actions-not-llm.md`.
Moving them into a file changes who owns them, not how they are written.

**An audience that has no answer produces no actions.**

Two refusals are deliberate, and both log their reason.
An organisation stating an audience the file does not define gets no actions, not the default's.
An audience with no action set for a matched template contributes nothing for that template, not another audience's set.
A silently borrowed prosecution step is the exact error this decision exists to prevent, and a fallback would reintroduce it in the one case nobody is watching.

**Legal provisions are appended only for a reader who can proceed under them.**

Each audience declares `legal_provisions` as `own`, `attributed` or `omitted`.
An advisory audience gets `attributed`, so the sections still appear, marked as the provisions another agency would proceed under.
Dropping them entirely would lose information an assessment legitimately carries, and printing them unmarked would read as a charge sheet.

**A wrong value in the file degrades the block, never the report.**

The rubric in ADR 0004 raises on a malformed file, because a score computed from fewer criteria than the file claims still looks considered.
This file is the opposite case.
The actions block is additive to a report that is complete without it, so a typo must not raise into `generate_report` and leave the row at `generated_at IS NULL` forever, which is the state an analyst reads as "still generating".
An unparseable file yields no audiences and logs at ERROR, a malformed entry is skipped and named, a duplicate id keeps the first, and an unrecognised `legal_provisions` value resolves to `omitted` rather than to `own`, since falling through to the reader's own provisions is the mis-framing this ADR removes.

**The heading belongs to the audience too.**

A prosecuting service reads "Recommended Actions".
An intelligence consumer reads "Assessment Priorities".
The heading is the first line above the block, so leaving it fixed would mis-frame correct content.

**The default keeps existing deployments identical.**

The file's `default_audience` ships as `prosecution`, and an organisation stating nothing resolves to it, logged at INFO.
The alternative, requiring an audience, is more honest and is a breaking change for every existing caller and every report already relied on.
The mis-framing this ADR fixes cannot persist silently under the default, because resolving the default is logged, the audience is logged per report, and the two audiences are asserted to cover the same templates in `tests/unit/test_report_audience.py`.

## Consequences

The audience rides along on the topic row: `SQL_FETCH_TOPIC` LEFT JOINs `organizations` and returns `report_audience` under an alias, since a bare column would be shadowed silently if `topics` ever grew one of the same name.
This costs no extra round trip in `generate_report`, and no extra `AsyncMock` in the dozen test modules that drive it through a mocked `db` module.
A topic whose organisation is missing still returns, with a NULL audience that reads as "not stated".

`build_recommended_actions` distinguishes three states, which is why it takes a sentinel rather than defaulting to `None`.
No argument means "whatever this deployment is set to".
An explicit `None` means an audience was stated and resolved to nothing, which yields no actions.
A `ReportAudience` is that audience.
Collapsing the first two would make an unrecognised audience inherit the default's prosecution steps, which is the failure being designed out.

The shipped file defines two audiences over the same eleven templates.
A template covered for one audience and not the other is a silent gap in a report, so a test asserts the two key sets are equal, and a second test asserts no advisory action uses a power that audience does not hold.

The PDF renders the actions from the same call the markdown does, rather than parsing them back out of the markdown by heading.
The heading is now the audience's, and the on-demand PDF path matched a fixed `"Recommendations"` substring, so an unrecognised heading left the parser's section open and dropped curated actions into the LLM recommendations list: the wrong framing and the wrong provenance in the same bullet.
The on-demand path, which renders an older report rather than a fresh one, reads the actions back out of the stored markdown instead of rebuilding them, because the markdown is the snapshot and an organisation that changed its audience since generation would otherwise get a PDF that disagrees with the report it renders.
That read is keyed on a marker the generator writes above the block, not on the block's position, because a report whose audience produced no actions has no block and the section that follows would otherwise be rendered as its recommended actions.

A super-admin sets an organisation's audience through `PATCH /api/v1/organizations/{id}`, and the organisation list returns it, so the value is not reachable only by raw SQL.
The API accepts any string rather than validating it against the audiences, because the audiences live in a file the reporter image carries and the API image does not.
The reporter is the validating end: an audience it does not recognise produces no actions and logs, which is the same refusal an operator would get from a constraint, one step later and without a migration per audience.
The organisations table in the workbench shows the audience, or "Deployment default" when the organisation states none, and does not offer a picker: the value is deployment configuration set once per organisation, and a picker would have to enumerate audiences the frontend cannot see.

The advisory action sets are drafted by the vendor and handed to the customer, unlike the credibility rubric's assessments, which ship empty.
An action set is a description of what a service can do rather than a judgement about a third party, so a wrong one is visibly wrong to the officer reading it, and shipping none would leave the audience unusable on first deployment.

## Alternatives considered

**Audience on the report request.**
Rejected because it asks the analyst a question with the same answer every time, and a wrong answer produces a mis-framed report with no signal that anything is off.
The organisation is the thing that actually varies.

**Audience on the Topic.**
Rejected for the same reason, with the addition that a Topic is shared across analysts in an organisation and its audience would drift from whoever created it.

**Keep prosecution as a fallback for an unmapped template.**
Rejected: it is precisely the silent mis-framing this decision removes, and it would apply in the case least likely to be reviewed.

**Require an audience, with no default.**
Rejected as a breaking change to every existing caller for a gain the logging already provides.

**Generate the actions from the LLM, conditioned on the audience.**
Rejected for the reasons the actions were template-driven in the first place: a hallucinated legal section or an inapplicable procedure in a block headed "Recommended Actions" is a high-stakes error, and architectural rule 9 would validate the shape of the output without validating whether the step is one the reader can take.
