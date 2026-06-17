# Future: Identifier Watchlist + Temporal Sparkline + Co-occurrence Graph

Status: **PLANNED — not yet prioritized**
Last updated: 2026-06-17
Context: Designed during identifiers UX redesign session. Phase 1 (global search) and Phase 2 (convergence card) shipped. Phase 3 deferred pending pilot demand.

## Persona Reviews Conducted

4 personas reviewed (Solution Architect, PM, ED Investigator, LEA Cyber Crime).
All 4 agreed: **watchlist first, graph last**.

## Phase 3a — Identifier Watchlist + Alerts (ship first when prioritized)

**What:** Analyst pins identifiers to a watchlist. System monitors scraped content 24/7 and fires signals when watched identifiers appear.

**Why:** Only Phase 3 feature that delivers value while analyst sleeps. Police cyber cells work shifts — inspector adds suspect UPI ID, goes home, gets notification when it surfaces.

**Schema:**
```sql
identifier_watchlist (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL REFERENCES organizations(id),
  user_id UUID NOT NULL REFERENCES users(id),
  identifier_type TEXT NOT NULL,
  identifier_value TEXT NOT NULL,
  case_ref TEXT,          -- FIR/ECIR number (LEA + ED feedback)
  created_at TIMESTAMPTZ DEFAULT now(),
  labels JSONB NOT NULL DEFAULT '{}',
  UNIQUE (org_id, identifier_type, identifier_value)
)
```

**Key requirements (from persona reviews):**
- `case_ref` field for FIR/ECIR number tagging (LEA + ED unanimous)
- Bulk import endpoint — analysts have 15+ identifiers per complaint (LEA feedback)
- `labels` mandatory, non-Optional (CLAUDE.md rule)
- RLS policy on watchlist table (SA feedback)
- org_id directly on table — no topic_id path (SA: root entity pattern)
- 24h dedup window on signal firing (same pattern as existing signals)

**Signal integration:**
- Hook into `check_identifier_signals` in analyst scheduler
- After existing breaching-cluster loop, query watchlist entries
- Compare against new `identifier_cluster_items` since `last_checked_at`
- Fire `identifier_watchlist` signal type
- Signal payload includes: content item, source, captured_at, content_hash

**API endpoints:**
- `POST /api/v1/identifiers/watchlist` — add single identifier
- `POST /api/v1/identifiers/watchlist/bulk` — bulk import (array)
- `GET /api/v1/identifiers/watchlist` — list user's watchlist
- `DELETE /api/v1/identifiers/watchlist/{id}` — remove from watchlist

**Frontend:**
- "Watch" button on search results in IdentifierSearch modal
- Watchlist panel/tab showing currently watched identifiers
- Case ref input when adding to watchlist

**Files to modify:**
- `services/api/migrations/versions/010_watchlist.py` — NEW
- `services/api/anveshak/api/db/identifiers.py` — watchlist CRUD SQL
- `services/api/anveshak/api/routes/identifiers.py` — watchlist endpoints
- `services/analyst/anveshak/analyst/identifier_signals.py` — watchlist check
- `services/analyst/anveshak/analyst/scheduler.py` — wire watchlist check
- `frontend/src/api/identifiers.ts` — watchlist API methods
- `frontend/src/components/search/IdentifierSearch.tsx` — watch button + panel

**Estimated effort:** ~1 week

---

## Phase 3b — Temporal Sparkline (ship with 3a)

**What:** Tiny inline sparkline on convergence card rows showing identifier activity over last 7 days.

**Why:** Analyst sees at a glance "this UPI ID spiked yesterday" vs "steady background noise."

**Implementation:**
- New API: `GET /api/v1/identifiers/clusters/{id}/timeline`
- SQL: `date_trunc('hour', ci.captured_at)` GROUP BY on `identifier_cluster_items`
- Frontend: inline SVG sparkline (no charting library needed for this)
- No separate view — visual enhancement only

**SA note:** No new table needed. Existing indexes cover the query.

**Estimated effort:** ~2 days

---

## Phase 3c — Co-occurrence Graph (defer until data density confirmed)

**What:** Visual force-directed graph showing identifier co-occurrence network. From one seed identifier, discover connected identifiers.

**Prerequisites before building:**
1. Confirm data density — how many content items have 2+ identifiers? If < 100, graph looks empty in every demo
2. Materialized `identifier_co_occurrences` table (self-join on extracted_entities won't scale past 100k rows/topic)
3. Export as table/PDF ships BEFORE graph visualization (PM + ED + LEA all demanded this)

**Constraints (from persona reviews):**
- Single-topic only in v1 (no cross-topic — org isolation risk per SA)
- Fan-out cap: 50 nodes max, paginate edges
- Rate-limited endpoint (self-join is expensive)
- React-force-graph lazy-loaded (200KB+ gzipped, per frontend rules)
- NO multi-hop traversal — that's entity resolution, which is Drishti's job
- NO identity linking — co-occurrence says "appeared together", NOT "same person"

**Product boundary (Anveshak vs Drishti):**
- Anveshak co-occurrence = "these identifiers appeared in same content" (narrative intelligence)
- Drishti entity resolution = "these identifiers belong to same person" (identity intelligence)
- Building multi-hop traversal or identity resolution in Anveshak cannibalizes Drishti

**Missing identifier types flagged by ED (future):**
- CIN (Company Identification Number)
- DIN (Director Identification Number)
- Vehicle registration
- Passport number
- SWIFT/BIC code

**Estimated effort:** ~2 weeks (including materialized table + export + graph component)

---

## When to Build

Trigger conditions (any one):
1. Pilot user requests "alert me when identifier X appears again" → build 3a
2. Demo prep needs "system watches 24/7" headline → build 3a
3. Data density check shows 500+ multi-identifier content items → consider 3c
4. Drishti integration planned → co-occurrence graph becomes the bridge visualization
