# UX Rewiring Spec — Provenance-Connected Analyst Workbench

**Status:** Approved (grilling session 2026-07-25)
**Approach:** Big bang — single release, clean break from current UX
**ADRs:** 0001 (three-view workspace), 0002 (stack-based provenance panel)

---

## Problem

Every data point in Anveshak is siloed. Identifiers show values with no context. Content items don't trace to the narrative they belong to. Sources don't connect to what they produced. The analyst's investigation story is fragmented across 8 tabs.

## Core Principle

**Every data point must answer "why am I here?"** via a clickable provenance chain:
`Identifier → Content Item(s) → Source(s) → Cluster → Topic`

Bidirectional. Every node clickable. Every node shows parents and children.

---

## 1. Sidebar Navigation

```
┌─ SIDEBAR ──────────┐
│  🔍 Search (⌘K)    │  Global identifier search
│                     │
│  📋 Topics          │  Topic list + create
│  ⚡ Signals         │  Cross-topic signal inbox (unchanged)
│  🎯 Cases           │  Long-running investigations (renamed from Trackers)
│  👁️ Vision          │  Standalone media analysis
│                     │
│  ──────────────     │
│  ⚙️ Settings        │  Users, Orgs, Audit, Dashboard
└─────────────────────┘
```

**Changes from current:**
- Reports removed (action button in topic workspace)
- Trackers renamed to Cases
- Standalone Identifiers page removed (embedded in topic + ⌘K search)
- Sources removed from sidebar (managed within topic)

---

## 2. Topics Dashboard (`/topics`)

Card grid sorted by urgency. Each card shows:

| Element | Source |
|---------|--------|
| Topic name + status badge | `topics.name`, `topics.status` |
| 🔴 Unacknowledged signal count | `signals WHERE status = 'new' AND topic_id = X` |
| 📈 New content last 24h | `content_items WHERE captured_at > now() - 24h` |
| 🟢🟡🔴 Source health dot | Worst health status across topic's sources |
| Last activity timestamp | Most recent content_item.captured_at |

**Sort order:** Topics with unacked signals first, then by most recent activity.

---

## 3. Topic Workspace (`/topics/:topicId`)

### 3.1 Three Views (tab bar at top)

```
[ Intelligence ]  [ Content ]  [ Map ]
```

### 3.2 Intelligence View (default)

Single scrollable page, sections in priority order:

#### Section: Signals (top)
- Active (unacknowledged) signals as horizontal cards
- Each card: cluster label, ISC, time fired
- Click → provenance panel
- Hidden when zero active signals

#### Section: Narratives
- Narrative cluster cards: label, size (item count), growth rate, ISC
- Top N clusters sorted by ISC then size
- "Show all →" → full-screen modal with cluster list + search
- Click cluster → provenance panel

#### Section: Key Identifiers
- Top identifiers by mention frequency
- Each: value, type badge, mention count, source count
- "Show all →" → full-screen modal (current identifier table + filters)
- Click identifier → provenance panel

#### Section: Location Pills
- Geocoded location names with content count: `📍 Kochi (12)  📍 Mumbai (3)`
- Click pill → Map view opens centered on that location
- "Open Map →" button → Map view
- Hidden when zero geocoded content

#### Section: Recent Content (compact)
- Last 5 content items as compact cards (title, source, platform badge, time)
- "Show all →" → Content view
- Click item → provenance panel

#### Section: Source Health Strip
- Horizontal strip of source dots: 🟢 healthy, 🟡 degraded, 🔴 down
- Source name on hover
- ⚙️ button → source management panel (right side)

#### Header Actions
- "Generate Report" button → report generation modal
- Topic status toggle (active/paused)
- Topic settings gear icon

### 3.3 Content View

- Infinite scroll content items (existing ContentFeed, relocated)
- Filter bar: platform, language, sentiment, date range, credibility min
- Content cards: title, snippet, platform badge, credibility badge, sentiment, timestamp
- Click item → provenance panel
- Export CSV button

### 3.4 Map View

- Full-area MapLibre GL instance
- Sovereign boundary overlay (existing)
- Content location pins with clustering
- Heatmap layer toggle
- Analyst pins (existing)
- Click pin → provenance panel showing content items at that location
- Export GeoJSON button

---

## 4. Provenance Panel (universal)

Right-side panel, 400px wide on desktop, full-screen overlay on mobile/tablet.

### 4.1 Structure

```
┌─ PROVENANCE PANEL ─────────────────────┐
│  ← Back              [close X]         │
│                                        │
│  ENTITY_TYPE: value              icon  │
│                                        │
│  TRACE: Identifier → 4 Items           │
│         → 2 Sources → 1 Cluster        │
│         ↗ Also in: "Drug Network"      │
│                                        │
│  ─── Section 1 ──────────────────      │
│  • Clickable items...                  │
│                                        │
│  ─── Section 2 ──────────────────      │
│  • Clickable items...                  │
│                                        │
└────────────────────────────────────────┘
```

### 4.2 Panel Content Per Entity Type

**Identifier:**
1. Found In — content items containing this identifier (snippet + platform badge)
2. Sources — sources that produced those content items (name + credibility)
3. Narrative Cluster — cluster(s) those items belong to (label + ISC)
4. Signals — signal(s) linked to those clusters
5. Cross-Topic — same identifier in other topics (convergence)

**Content Item:**
1. Full text/media preview
2. Source — producing source (name + platform + credibility)
3. Cluster — narrative cluster membership (label + ISC)
4. Identifiers — all identifiers extracted from this content
5. Vision Results — deepfake score, YOLO detections, EXIF (if media)

**Source:**
1. Credibility score + trend
2. Recent content — last 5 items from this source
3. Health status + last check time
4. Topics — topics using this source
5. Audit log — credibility changes

**Cluster:**
1. Label + ISC + item count + growth
2. Content items — member items (compact list)
3. Key identifiers — identifiers found across cluster items
4. Signal — signal fired (if any), with status

**Signal:**
1. Trigger details — ISC threshold crossed, when
2. Cluster — triggering cluster (label + items)
3. Content items — items in triggering cluster
4. Identifiers — key identifiers in those items

### 4.3 Stack Navigation

- Internal state: `Array<{ entityType: string, entityId: string }>`
- Click item inside panel → push new view onto stack
- Back button → pop stack, show previous view
- Close button → clear stack, close panel
- View switch (Intelligence/Content/Map) → clear stack, close panel

---

## 5. Modals (full-screen)

Triggered by "show all →" buttons and action buttons:

| Trigger | Modal Content |
|---------|--------------|
| "Show all identifiers" | Identifier table + type filter + search + export CSV |
| "Show all clusters" | Cluster list + search by label + sort by ISC/size |
| "Show all content" → | Navigates to Content view (not modal) |
| "Open Map" → | Navigates to Map view (not modal) |
| "Generate Report" | Report type + time window + credibility min → submit |
| Source ⚙️ | Source add/remove/edit + health details |
| Location pill click → | Navigates to Map view centered on location |

---

## 6. Global Search (⌘K)

- Identifier-only search (Phase 1)
- Cross-topic: searches all topics within analyst's org
- Results: identifier value, type, topic name, mention count
- Click result → navigates to topic workspace with provenance panel pre-opened for that identifier

---

## 7. Vision Integration

- **Standalone page** (`/vision`): unchanged, for ad-hoc uploads
- **Ad-hoc upload**: optional topic selector — if linked, results appear in topic's content
- **Scraped media**: vision results (deepfake, YOLO, EXIF) shown in content item's provenance panel under "Vision Results" section

---

## 8. Cases (renamed from Trackers)

- Sidebar label: "Cases" (not "Trackers")
- Route: `/cases`, `/cases/:caseId`
- Functionality unchanged
- Internal model name migration: `Tracker` → `Case` (optional, low priority)

---

## 9. Mobile / Tablet

- Provenance panel → full-screen overlay (slide up from bottom)
- Back button to dismiss
- Three-view tabs remain at top
- Source health strip wraps to multiple lines
- Modals remain full-screen (already are)

---

## 10. Backend Requirements

**Already supported (90%):**
- Identifier → content items (extracted_entities JOIN)
- Content item → source (source_id FK)
- Content item → cluster (narrative_cluster_id FK)
- Cross-topic identifier search (SQL_SEARCH_IDENTIFIERS_GLOBAL)
- Identifier convergence detection (SQL_IDENTIFIER_CONVERGENCE)
- Co-occurrence queries (SQL_CO_OCCURRENCE)
- Export with full provenance chain (SQL_EXPORT_IDENTIFIERS)

**New endpoints needed:**
1. `GET /api/v1/topics/:id/intelligence` — aggregated overview data (signals + top clusters + top identifiers + location pills + source health) in single call
2. `GET /api/v1/identifiers/:value/provenance?topic_id=X` — full provenance chain for one identifier
3. `GET /api/v1/content/:id/provenance` — content item with source + cluster + identifiers + vision results in single call
4. `GET /api/v1/topics/:id/urgency` — urgency metrics for dashboard sort (or include in topic list endpoint)

---

## 11. Components to Create

| Component | Purpose |
|-----------|---------|
| `IntelligenceView` | Default topic view — signals, clusters, identifiers, locations, content, sources |
| `ProvenancePanel` | Universal right-side drill-down with stack navigation |
| `ProvenanceBreadcrumb` | Trace chain display at top of panel |
| `SignalCards` | Horizontal signal card strip |
| `NarrativeCards` | Cluster cards with ISC, size, growth |
| `IdentifierPills` | Top identifiers with type badges |
| `LocationPills` | Geocoded location pills with counts |
| `SourceHealthStrip` | Horizontal source health dots |
| `ShowAllModal` | Generic full-screen modal for expanded lists |
| `UrgencyBadge` | Red/amber/green urgency indicator for topic cards |

## 12. Components to Remove

| Component | Replaced By |
|-----------|------------|
| `DashboardTab` | IntelligenceView |
| `OverviewTab` | IntelligenceView |
| `SourcesTab` | SourceHealthStrip + modal |
| `ReportsTab` | Header button + modal |
| `ClustersTab` | NarrativeCards + ShowAllModal |
| `IdentifiersTab` | IdentifierPills + ShowAllModal |
| `IntelSidebar` | Absorbed into IntelligenceView |
| `SignalDetailPanel` | ProvenancePanel (signal type) |
| `SourceAssessmentPanel` | ProvenancePanel (source type) |
| `ContentDetail` | ProvenancePanel (content type) |

---

## 13. Interaction Pattern Summary

Only two patterns in the entire app:

1. **Click single entity** → Provenance Panel (right side, stack-based)
2. **Click collection/action** → Full-screen Modal (show all, generate report, manage sources, map)

No other drill-down mechanisms. Consistent everywhere.
