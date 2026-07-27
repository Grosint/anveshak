# ADR 0002: Stack-Based Provenance Panel as Universal Drill-Down

**Status:** Accepted
**Date:** 2026-07-26
**Deciders:** Product owner + engineering

## Context

Every data point in Anveshak exists in isolation. An identifier table shows phone numbers with mention counts but no context — which content item contained it, from which source, in which narrative cluster, did it trigger a signal, does it appear in other topics?

The analyst's mental model is investigation-as-trail-following: click a phone number → see where it appeared → follow to the source → discover co-occurring identifiers → pivot to another topic where the same number surfaces.

## Decision

Implement a **universal stack-based provenance panel** as the sole drill-down mechanism for all entity types.

### Behavior

1. **Click any entity** (identifier, content item, source, cluster, signal) anywhere in the workspace → right panel opens showing that entity's provenance chain.

2. **Provenance chain** is displayed as a breadcrumb trail at the top:
   `Identifier → 4 Content Items → 2 Sources → 1 Cluster → Signal`

3. **Every item inside the panel is also clickable.** Clicking pushes a new view onto the panel's navigation stack. The panel has a back button to retrace steps.

4. **Cross-topic links** are shown when an identifier appears in other topics. Clicking navigates to that topic's workspace with the panel pre-opened.

### Panel Sections (per entity type)

**Identifier:** Found In (content items with snippet) → Sources → Narrative Cluster → Cross-Topic appearances

**Content Item:** Full text/media → Source (with credibility) → Cluster membership → Extracted identifiers → Vision results (if media)

**Source:** Credibility score + audit history → Recent content items → Health status → Topics using this source

**Cluster:** Label + ISC + growth → Member content items → Key identifiers within → Signal status

**Signal:** Trigger details (ISC threshold crossed) → Cluster → Content items → Identifiers

### Implementation Constraints

- Panel width: 400px desktop, full-screen below tablet breakpoint
- Stack depth: unlimited (analyst follows trail as deep as needed)
- Panel state: cleared on view switch (Intelligence/Content/Map) — fresh start
- Data fetching: lazy per panel view (don't prefetch entire provenance tree)

## Alternatives Considered

1. **One-level panel (no stack).** Click entity → panel shows detail. Click item inside panel → replaces main content area. Rejected: loses context. Analyst can't retrace investigation path without browser back button (which navigates away entirely).

2. **Full-page drill-down.** Click entity → navigate to `/identifiers/:id` page. Rejected: loses workspace context. Analyst must mentally hold previous state while viewing detail.

3. **Inline expand (accordion).** Click table row → expand in place showing nested provenance. Rejected: gets cramped with nested data. Doesn't scale to deep trails (identifier → content → source → co-occurring identifier → its content).

## Consequences

- Every list component (identifiers, content, sources, clusters, signals) must emit click events with entity type + ID
- Panel component manages its own navigation stack (array of `{entityType, entityId}`)
- API endpoints already support provenance queries (90% coverage) — minimal backend work
- Panel replaces current WorkspacePanel, SignalDetailPanel, SourceAssessmentPanel, ContentDetail — one component instead of four
- Global search (⌘K) must be able to open a specific topic workspace with panel pre-loaded for a given identifier
