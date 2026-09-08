# ADR 0001: Rank narratives by propagation, never by concern

- Status: Accepted
- Date: 2026-09-08
- Epic: #21

## Context

Anveshak surfaces narratives forming inside a Watch Space and presents them to an analyst for triage.
The first deployment targets a domain that includes lawful political organising, and the first named target is a political group with public accounts on two platforms.

Any ordering the system applies is an editorial act.
If the system ranks narratives by how concerning it judges their content to be, it becomes a dissent detector: it tells an analyst which political speech to look at first, on the system's own judgement, with no auditable arithmetic behind the order.
That is indefensible to a customer, to a court, and to a journalist.

A second pressure points the same way.
The pattern the customer actually described from their own experience is a manufactured narrative: many accounts amplifying one claim while independent sourcing stays flat.
That pattern is identifiable purely from how content spreads.
No judgement about the truth or the danger of the claim is needed to detect it.

## Decision

Every ordered list in Anveshak is ordered by a measurement of propagation.

Permitted ordering keys are item count, contributing account count, independent source count, growth rate, and recency.
Each is a count or a rate over rows an analyst can open and read.

Concern categories exist, and they are filters only.
An analyst may apply a concern filter to change which narratives appear in a list.
Applying it never changes the order of the narratives that remain.
The system never surfaces a concern category unprompted.

Severity survives as a concept, because it is already computed from propagation facts rather than from content.
Its presentation changes.
Severity renders as a neutral magnitude indicator shown next to the arithmetic that produced it, never as an alarm.

Signal titles state what was measured.
A title never states what the measurement means.
Every signal card leads with its evidence; any score is secondary.

## Consequences

An analyst can always verify an ordering by recomputing it from rows in the database.
That is the property that makes the output defensible under scrutiny.

A future reader will notice that concern scores sort no list anywhere in the codebase.
That is deliberate, and this ADR is the reason.
Tests assert it: applying a concern filter changes membership and does not change ordering.

The system will sometimes rank a benign narrative above a serious one, because the benign one is spreading faster.
That is the correct behaviour.
The analyst decides what matters; the system reports how things spread.

The concern taxonomy is drafted here and handed to the customer to own and version thereafter, because it encodes a definition of what counts as concerning, and that definition belongs to the agency accountable for it.
Categories are defined by behaviour or harm, never by viewpoint or political position.
