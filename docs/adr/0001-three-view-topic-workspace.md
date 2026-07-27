# ADR 0001: Three-View Topic Workspace with Provenance Panel

**Status:** Accepted
**Date:** 2026-07-26
**Deciders:** Product owner + engineering

## Context

The topic workspace had 8 tabs (Dashboard, Overview, Feed, Clusters, Map, Identifiers, Reports, Sources). Analysts had to click through each tab to build a mental picture. Data was siloed — identifiers showed values with no context about why they surfaced, which content mentioned them, or which narrative they belonged to. The UX forced hunting instead of absorbing.

The fundamental problem: every data point existed in isolation. The story of the investigation was disconnected across tabs.

## Decision

Replace the 8-tab topic workspace with **3 views** and a **universal provenance panel**.

### Three Views

1. **Intelligence** (default) — Single-page overview answering "what's happening?" Contains: active signals (top), narrative cluster cards, key identifiers, source health strip, location pills. Each section shows top N with "show all →" opening a full-screen modal.

2. **Content** — Full evidence feed with infinite scroll and filters (platform, language, sentiment, date range, credibility). Answers "show me the proof."

3. **Map** — Full-screen MapLibre with pins, heatmap, and cluster overlays. Primary tool for LEA field operations. Not a small widget.

### Provenance Panel (universal)

Right-side panel opens on clicking **any** entity across all three views. Shows full provenance chain: `Identifier → Content Item(s) → Source(s) → Cluster → Topic`. Stack-based navigation — clicking items inside the panel pushes new views with back button, allowing analysts to follow investigation trails.

### Interaction Patterns (two only)

- **Click single item** → provenance panel (right side, stack-based)
- **Click "show all" / "Open Map"** → full-screen modal (collections, map, report generation, source management)

### Reports and Sources

Removed as standalone tabs. Accessed via action buttons:
- "Generate Report" button in topic header → modal
- Source health strip with ⚙️ icon → management panel

### Mobile/Tablet

Provenance panel becomes full-screen overlay below breakpoint. Same drill-down functionality, different layout.

## Alternatives Considered

1. **Pure single page (zero tabs)** — All sections on one scrollable page. Rejected: becomes a wall of cards for data-heavy topics (500+ content items). Analyst scrolls past signals to find identifiers — same hunting problem, just vertical.

2. **Keep 8 tabs, add cross-links** — Add provenance links between existing tabs. Rejected: doesn't solve the fundamental problem of context-switching. Analyst still bounces between tabs to build mental picture.

3. **Two views (Intelligence + Content)** — Map as modal only. Rejected: LEA officers live in the map view. Opening/closing a modal repeatedly is friction for power users. Map deserves first-class view status.

## Consequences

- All existing tab components (DashboardTab, OverviewTab, SourcesTab, ReportsTab, ClustersTab, IdentifiersTab) are replaced
- IntelSidebar is absorbed into the Intelligence view's main content area
- WorkspacePanel component is evolved into the stack-based provenance panel
- MapLibre lazy-loading moves from tab-gated to view-gated
- Backend is 90% ready — identifier→content→source→cluster queries all exist. Frontend-only rewrite.
- Every "show all" modal needs its own filter/search/export UI (lifted from current tab implementations)
