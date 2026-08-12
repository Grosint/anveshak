# ShowAllModal + Report/Source Management Modals

**Issue:** #10
**Date:** 2026-07-27
**Status:** Approved

## Summary

Full-screen modals triggered by "show all" and action buttons on IntelligenceView. Analyst stays on Intelligence tab; modals overlay on top. Existing tab navigation unchanged for deep-dive sessions.

## Approach

Extend existing `Modal` component with `fullScreen` prop. Create thin wrapper modal components that reuse existing page components (`Identifiers`, `ReportsTab`, `SourcesTab`). Extract cluster browsing logic from TopicWorkspace into reusable `ClusterBrowser`.

## Modal Component Extension

**File:** `frontend/src/components/ui/Modal.tsx`

Add `fullScreen?: boolean` prop:
- `fullScreen=false` (default): current behavior — centered panel, `max-w-lg`, rounded corners
- `fullScreen=true`: `fixed inset-0`, no max-width, no border-radius, sticky header, scrollable body

Escape key closes modal. Backdrop click closes (non-fullscreen only — fullscreen has no backdrop gap).

## New Components

### 1. IdentifiersModal

**File:** `frontend/src/components/modals/IdentifiersModal.tsx`

```
<Modal fullScreen open={open} onClose={onClose} title="All Identifiers">
  <Identifiers embedded topicId={topicId} />
</Modal>
```

Reuses existing `Identifiers` page component which already has:
- Type filter dropdown
- Top / Clusters / Search view modes
- CSV export button
- Cluster detail panel

**Provenance:** Identifiers page currently has no click-to-provenance. Add `onSelectIdentifier` prop to `Identifiers` component → close modal + push to provenance.

### 2. ClustersModal

**File:** `frontend/src/components/modals/ClustersModal.tsx`

```
<Modal fullScreen open={open} onClose={onClose} title="All Clusters">
  <ClusterBrowser topicId={topicId} onSelectCluster={handleSelect} />
</Modal>
```

**ClusterBrowser extraction:**

**File:** `frontend/src/components/clusters/ClusterBrowser.tsx`

Extract from TopicWorkspace lines 326-475:
- Cluster list with search (content + narrative modes)
- Sort by ISC/size (add sort controls)
- Cluster drilldown with content items
- Search bar

Used by both ClustersModal and TopicWorkspace clusters tab.

**Provenance:** Clicking cluster → close modal + push cluster to provenance. Clicking content item inside drilldown → close modal + push content to provenance.

### 3. ReportGenerationModal

**File:** `frontend/src/components/modals/ReportGenerationModal.tsx`

```
<Modal fullScreen open={open} onClose={onClose} title="Generate Report">
  <ReportsTab topicId={topicId} />
</Modal>
```

Reuses existing `ReportsTab` which already has:
- Report type selector (intelligence_brief, research_summary, weekly_digest)
- Time window input
- Generate button with polling
- Report history list
- Markdown display with PDF download

No provenance integration needed — reports are not provenance entities.

### 4. SourceManagementModal

**File:** `frontend/src/components/modals/SourceManagementModal.tsx`

```
<Modal fullScreen open={open} onClose={onClose} title="Manage Sources">
  <SourcesTab topicId={topicId} />
</Modal>
```

Reuses existing `SourcesTab` which already has:
- Linked sources list with health badges
- Unlink button
- Discover sources tab
- Source assessment panel (lazy-loaded)

No provenance integration needed — sources are managed, not browsed for provenance.

## TopicWorkspace Wiring

Replace tab-switching callbacks with modal state:

```typescript
const [showIdentifiersModal, setShowIdentifiersModal] = useState(false)
const [showClustersModal, setShowClustersModal] = useState(false)
const [showReportModal, setShowReportModal] = useState(false)
const [showSourcesModal, setShowSourcesModal] = useState(false)
```

IntelligenceView callback wiring:
```
onShowAllIdentifiers={() => setShowIdentifiersModal(true)}
onShowAllClusters={() => setShowClustersModal(true)}
onGenerateReport={() => setShowReportModal(true)}
onManageSources={() => setShowSourcesModal(true)}
```

Tab navigation (`onNavigateMap`, `onNavigateContent`) stays as tab switches.

## Provenance Flow

For IdentifiersModal and ClustersModal:
1. User clicks item inside modal
2. Modal calls `onSelectItem` callback
3. Callback pushes to `provenance.push(...)`
4. Callback calls modal's `onClose()`
5. ProvenancePanel opens on right side of Intelligence tab

## Keyboard

- Escape → close topmost modal (handled by Modal component)
- No additional shortcuts

## Files Changed

| File | Change |
|------|--------|
| `components/ui/Modal.tsx` | Add `fullScreen` prop |
| `components/modals/IdentifiersModal.tsx` | New — thin wrapper |
| `components/modals/ClustersModal.tsx` | New — thin wrapper |
| `components/modals/ReportGenerationModal.tsx` | New — thin wrapper |
| `components/modals/SourceManagementModal.tsx` | New — thin wrapper |
| `components/clusters/ClusterBrowser.tsx` | New — extracted from TopicWorkspace |
| `pages/TopicWorkspace.tsx` | Wire modal state, replace tab-switch callbacks, render modals, use ClusterBrowser for clusters tab |
| `pages/Identifiers.tsx` | Add optional `onSelectIdentifier` callback prop |

## Acceptance Criteria Mapping

- [x] "Show all identifiers" → IdentifiersModal with table, type filter, search, CSV export
- [x] "Show all clusters" → ClustersModal with cluster list, search, sort by ISC/size
- [x] "Generate Report" → ReportGenerationModal with type/window form, submit, polling
- [x] Source ⚙️ → SourceManagementModal with add/remove/edit, health details
- [x] All modals close on X button and Escape key
- [x] Modals are full-screen on all viewports
- [x] Items inside modals clickable → close modal, open ProvenancePanel
- [x] Existing functionality preserved (reusing existing components)
