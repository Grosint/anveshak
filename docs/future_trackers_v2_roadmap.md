# Trackers v2+ Roadmap — Agency-Specific Enhancements

## Context

Trackers v1 ships the core two-tier model: ephemeral Active Narratives (Leiden clustering)
+ permanent Trackers (analyst-owned case files). v1 was validated by 8 personas:
Solution Architect, Product Manager, LEA Cyber Crime, NIA, MEA, SEBI, ED/FIU, NCB.

This document captures every v2+ enhancement identified during the multi-persona review,
organized by capability, beneficiary, and implementation notes. Each item includes
the rationale from the specific persona who requested it.

---

## v2.1 — Evidence Integrity (NIA, ED, NCB, SEBI)

### Hash Chain Tamper-Evidence

**Requested by:** NIA analyst, ED investigator, NCB analyst

**Problem:** In NIA Special Court, PMLA Appellate Tribunal, and NDPS Court, the defence
challenges evidence integrity. Current audit log is append-only but not cryptographically
verifiable. A database admin could insert/delete rows without detection.

**Solution:** Every entry in `tracker_audit_log` includes a hash chain:
```
event_hash = SHA-256(previous_event_hash + event_data + timestamp)
```
If any row is modified or deleted mid-chain, all downstream hashes break. A verification
script can audit chain integrity on demand.

**Implementation notes:**
- Add `event_hash TEXT` and `prev_event_hash TEXT` columns to `tracker_audit_log`
- Compute hash in application code (not DB trigger — need access to previous hash)
- `verify_tracker_integrity(tracker_id)` function walks the chain and reports breaks
- API endpoint: `GET /trackers/{id}/integrity-check`
- Performance: O(N) where N = audit entries per tracker. Acceptable up to ~10,000 entries.

**NIA quote:** "Show me the hash chain. Show me that if a database administrator modifies
a record, the chain breaks. Without this, I cannot use investigation records as evidence."

### Section 63 BSA Certificate Auto-Generation

**Requested by:** ED investigator, NCB analyst, NIA analyst

**Problem:** Under Bharatiya Sakshya Adhiniyam 2023 Section 63 (formerly Indian Evidence Act
Section 65B), electronic records require a certificate from the person in charge of the
computer system. Without this certificate, OSINT evidence is inadmissible.

**Solution:** Auto-generate a Section 63 BSA certificate for each tracker's evidence package:
- States that the content was produced by a computer in proper working order
- Lists each content item with: URL, capture timestamp, content hash (SHA-256)
- Identifies the platform and scraping method
- Generated as a PDF, attached to the tracker
- Requires officer's digital signature before submission

**Implementation notes:**
- New template in reporter service: `bsa_section_63_certificate.html`
- Pulls data from `tracker_content_items` with `attached_by` provenance
- Includes `content_hash` from `content_items` table for each item
- WeasyPrint PDF generation (already in reporter service)
- API: `POST /trackers/{id}/generate-bsa-certificate`

**ED quote:** "Get hash chain and Section 63 certificate done, and I will pilot this in my unit."

---

## v2.2 — Narrative Lifecycle (MEA)

### Dormancy Detection and Auto-Reactivation

**Requested by:** MEA analyst

**Problem:** Diplomatic narratives go dormant for weeks/months and resurface around
predictable events (UNGA, OIC meetings, bilateral summits). The "concluded" status
implies finality, but these narratives are cyclical. Currently no way to distinguish
"nothing happening right now" from "this is over."

**Solution:** Add `dormant` status between `active` and `concluded`:
- System auto-suggests dormancy when no new matching content arrives for a configurable
  period (default: 14 days)
- Auto-reactivation alert when a dormant tracker starts receiving matches again
- "TRK-2026-0047 has 12 new items in the last 48 hours after 6 weeks of dormancy"
- Spike-after-silence pattern is often the most important signal

**Status progression becomes:**
```
watching → active → dormant → active → dormant → ... → concluded (analyst only)
```

**Implementation notes:**
- Add `dormant` to status CHECK constraint (migration)
- New scheduler function: `_check_tracker_dormancy(pool)` — runs daily
- Query: trackers WHERE status='active' AND no new tracker_content_items in N days
- Auto-set status to 'dormant' with audit log entry
- Reverse: when `_run_tracker_matching_cycle` inserts pending items for a dormant tracker,
  fire a `tracker_reactivation` signal via WebSocket
- Add `dormancy_threshold_days INT DEFAULT 14` to trackers table

### Cyclical/Seasonal Tagging

**Requested by:** MEA analyst

**Problem:** Some narratives recur around predictable events. An analyst tracking the
"anti-India narrative at OIC" wants a reminder when the next OIC meeting approaches.

**Solution:**
- Add `cyclical_events JSONB` to trackers (array of event labels + approximate dates)
- Example: `[{"event": "UNGA", "month": 9}, {"event": "OIC Summit", "approximate": "2026-12"}]`
- Dashboard widget: "Upcoming events for your trackers"
- No automatic action — just reminders

**MEA quote:** "The spike-after-silence pattern is often the most important signal.
If Anveshak can reliably detect that, I would adopt it tomorrow."

---

## v2.3 — Geographic Intelligence (MEA, NCB)

### Geographic Tagging and Flow Visualization

**Requested by:** MEA analyst, NCB analyst

**Problem:** MEA tracks narratives BY COUNTRY ("What is being said about India in Turkish media
vs Gulf media?"). NCB tracks drug routes ("Mephedrone manufactured in Gujarat → shipped to
Mumbai → distributed via Telegram dead drops"). Neither can be expressed in v1.

**Solution:**

For content items:
- Add `country_code TEXT` and `region TEXT` to sources table (or source metadata)
- Derive country from source, not content (a Dawn article is Pakistani regardless of topic)
- Content items inherit country from their source

For trackers:
- Add `geographic_scope TEXT[]` to trackers (array of country/region codes)
- Filter tracker content by geography: "Show me only Gulf-relevant content"
- Geographic spread visualization: overlay content items on a map/timeline by country

For NCB drug routes:
- Extract location mentions via spaCy NER + abbreviation dictionary (BLR, MUM, DEL)
- Temporal sequencing: "identifier X mentioned Gujarat on day 1, Mumbai on day 5"
- Route visualization on MapLibre (already in tech stack)

**Implementation notes:**
- Migration: `ALTER TABLE sources ADD COLUMN country_code TEXT, ADD COLUMN region TEXT`
- Seed country codes for existing sources (manual curation or domain-based inference)
- New API: `GET /trackers/{id}/geographic-breakdown` — content count by country
- Frontend: MapLibre integration on tracker detail page (lazy-loaded per frontend rules)

**MEA quote:** "My entire reporting structure is organized geographically. When I brief
the JS (East Asia), they don't care about what Gulf media is saying."

### Provenance Cascade View

**Requested by:** MEA analyst

**Problem:** The most valuable analytical product for MEA is the provenance chain:
"Here's where this narrative started, here's who amplified it, here's the timeline."
No commercial tool (Meltwater, Brandwatch) provides this.

**Solution:**
- Chronological cascade view: content items ordered by publication time, grouped by
  country/source
- First-seen timestamp and source highlighted as probable origin point
- Textual similarity between items flagged as possible coordinated amplification
- "Anchor article" identification: analyst marks one item as the anchor, system shows
  which subsequent items are textually similar

**Implementation notes:**
- Frontend component: `ProvenanceCascade.tsx` — timeline with country swim lanes
- Backend: `GET /trackers/{id}/content?sort_by=captured_at&group_by=country`
- Similarity detection: pairwise cosine similarity between items in tracker, surface
  pairs with similarity > 0.85 as "possible amplification"
- Uses existing embedding infrastructure, no new ML needed

**MEA quote:** "If Anveshak can reliably show me 'this narrative moved from Source A to
Source B to Source C over 10 days, here's the evidence,' that's a capability no commercial
tool offers me today."

---

## v2.4 — Tracker Hierarchy (NIA, ED, NCB)

### Parent-Child Tracker Relationships

**Requested by:** NIA analyst, ED investigator, NCB analyst

**Problem:** Complex investigations have sub-investigations:
- NIA: PFI case → radicalization + financing + training camps + international links
- ED: Main ECIR → associates + shell companies + foreign connections
- NCB: Drug network → financier + manufacturer + couriers + distributors

A flat tracker list cannot express these relationships.

**Solution:**
- Add `parent_tracker_id TEXT REFERENCES trackers(id) ON DELETE SET NULL` to trackers
- Case number inheritance: parent TRK-2026-0042, children TRK-2026-0042/A, TRK-2026-0042/B
- Tree view in tracker list page
- Parent tracker dashboard shows aggregate stats across children
- Content items can exist in both parent and child trackers

**Implementation notes:**
- Migration: add column + index
- API: `GET /trackers/{id}/children`, add `parent_tracker_id` to create/update
- Frontend: tree view component, breadcrumb navigation
- Aggregate queries: recursive CTE for counting content across hierarchy

**NIA quote:** "A single PMLA case often spawns sub-investigations. I need parent-child
tracker relationships — a tree, not a flat list."

---

## v2.5 — Classification and Access Control (NIA, MEA, SEBI)

### Classification Levels

**Requested by:** NIA analyst (showstopper), MEA analyst

**Problem:** The moment an NIA analyst writes a note saying "this Telegram channel is
operated by ISI's S-Wing based on HUMINT," that note is classified. The tracker becomes
a classified container. Current `labels` JSONB is not sufficient — classification is an
access control primitive, not a tag.

**Solution:**
- Add `classification_level TEXT CHECK (classification_level IN ('unclassified', 'restricted',
  'confidential', 'secret', 'top_secret'))` to trackers and tracker_notes
- High-water mark: tracker classification = MAX(own level, max note level)
- API layer filters notes by user clearance level
- Users table gets `clearance_level` field
- Export controls: classified trackers require approval before PDF export

**Implementation notes:**
- Migration: add columns to trackers, tracker_notes, users
- Middleware: classification check on every tracker read endpoint
- Note filtering: `WHERE classification_level <= user.clearance_level`
- Audit logging on every classification change

### Dual Titles (MEA)

**Requested by:** MEA analyst

**Problem:** A tracker titled "Chinese influence operations in Sri Lanka" is diplomatically
explosive if visible during screen sharing or in shared dashboards.

**Solution:**
- Add `display_title TEXT` to trackers (public/sanitized title)
- `title` remains the internal sensitive title, visible only to assigned analyst + admins
- Shared views, exports, and dashboards use `display_title` when set

### Intra-Org ACLs / Chinese Wall (SEBI)

**Requested by:** SEBI analyst

**Problem:** Within SEBI, Team A investigating Company X must not see Team B's investigation
into Company Y. Org-level isolation is too coarse.

**Solution:**
- `tracker_access` join table: `(tracker_id, user_id, access_level)` where access_level
  is 'viewer' | 'editor' | 'owner'
- Default: creator is owner, org admins have viewer access
- Explicit sharing required for other analysts within the same org
- Read audit logging: log WHO viewed WHICH tracker WHEN

**SEBI quote:** "Team A investigating Company X must not see Team B's investigation into
Company Y, even within the same SEBI department."

---

## v2.6 — Cross-Topic Trackers (NIA, ED)

### Investigations Spanning Multiple Topics

**Requested by:** NIA analyst, ED investigator

**Problem:** Every significant NIA case spans multiple topics. The PFI ban case involved
radicalization content, hawala financing, training camps, and international linkages —
each a separate topic in Anveshak.

**Solution:**
- Replace single `topic_id` FK with M:M join table: `tracker_topics(tracker_id, topic_id)`
- Auto-matching runs across all linked topics
- Content from any linked topic eligible for matching
- Primary topic (originating) gets lower similarity threshold than adjacent topics

**Implementation notes:**
- Migration: create join table, migrate existing `topic_id` data, drop column
- Breaking change — must be carefully sequenced
- Org isolation: cross-topic tracker must verify all topics belong to same org
  (or have explicit cross-org authorization for NIA-type use cases)

**NIA quote:** "An investigation must be able to span multiple topic_id values."

---

## v2.7 — Velocity and Reach Dashboards (MEA, SEBI)

### Narrative Velocity Metrics

**Requested by:** MEA analyst, SEBI analyst

**Problem:** MEA needs "How fast is this narrative spreading?" SEBI needs "Posts per hour
about this scrip across sources." Neither has a velocity metric.

**Solution:**
- Tracker dashboard widget: items per day over tracker lifetime
- Source diversity over time: distinct sources per day
- Velocity alert: "Content intake increased 400% in last 24 hours"
- For SEBI: pump-and-dump velocity signal (posts/hour by scrip across sources)

**Implementation notes:**
- Backend: `GET /trackers/{id}/velocity` — time-series of content volume
- Frontend: Recharts line chart on Overview tab
- Alert: scheduler checks velocity against baseline, fires signal if threshold exceeded
- Add `velocity_alert_threshold FLOAT` to trackers (e.g., 4.0 = 400% increase triggers alert)

**MEA quote:** "If it was 3 Pakistani outlets last week and now it's 12 outlets across 5
countries, that's an escalation I need to flag immediately."

---

## v2.8 — Multi-Agency Sharing (NIA, MEA, ED, NCB)

### Sanitized Export with Redaction

**Requested by:** NIA analyst, MEA analyst, ED investigator, NCB analyst

**Problem:** Every agency shares intelligence selectively. NIA shares with state police
without exposing sources and methods. ED shares with foreign FIUs via Egmont Group.
MEA shares with missions. NCB shares with DRI and state ANC.

**Solution:**
- `tracker_shares` table: `(tracker_id, shared_with_org, shared_by, shared_at,
  classification_ceiling, redactions JSONB, purpose, expiry_date)`
- Sanitized export: strips notes, strips source identities, keeps only content + metadata
- PDF export with watermark: "SHARED WITH [AGENCY] ON [DATE] — NOT FOR FURTHER DISTRIBUTION"
- Recipient-specific redaction rules
- Sharing audit log: who received what, when, through what channel

**Implementation notes:**
- New table + API endpoints
- PDF template with watermark in reporter service
- Redaction engine: regex-based entity masking in content text
- Expiry: auto-revoke access after expiry_date

**ED quote:** "When I share intelligence with a foreign FIU, I cannot share the full tracker.
I need to export a sanitised package."

---

## Vertical Add-Ons (Per-Customer Deployment)

### Financial Crime Vertical (ED, SEBI)

**New identifier types:**
- CIN (Corporate Identification Number): `[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}`
- DIN (Director Identification Number): 8-digit number
- ISIN: `INE[A-Z0-9]{7}\d{2}\d`
- NSE/BSE ticker symbols
- SWIFT/BIC codes
- RERA registration numbers
- Vehicle registration numbers

**Features:**
- Shell company detection score (shared directors, address reuse, absence of web presence)
- Financial data import (CSV/Excel bank statements, STR data)
- Trading data overlay (public NSE/BSE bhav copy price/volume on tracker timeline)
- Temporal correlation view: OSINT events + financial events on same axis
- Legal hold: freeze entire evidence package when attachment order issued
- One-click evidence package for provisional attachment orders

**ED quote:** "CIN and DIN extraction unlocks shell company detection — highest investigation
value per engineering effort."

**SEBI quote:** "The single feature that would make my department adopt this: real-time
coordination velocity alerts with scrip extraction."

### Narcotics Vertical (NCB)

**Features:**
- Drug-specific CLIP categories: "heroin powder", "mephedrone crystals", "MDMA pills",
  "cannabis buds" (config change, no model retraining)
- pHash batch matching: same drug product photo across vendor listings
- Drug route flow visualization on MapLibre
- Telegram real-time event streaming (Telethon event handlers, not just polling)
- Drug slang vocabulary refresh mechanism (periodic update from seized communications)
- NDPS Act section auto-mapping from scam templates
- Disposable Telethon account rotation for OPSEC

**NCB quote:** "Show an NCB officer that when a Telegram channel gets burned, the system
automatically detects the replacement through shared identifiers. That single moment
justifies the platform."

### Diplomatic Vertical (MEA)

**Features:**
- Counter-narrative tracking: link hostile narrative tracker + response tracker on same timeline
- Source stance profiling: tag sources as state-affiliated, independent, opposition
- Diplomatic calendar integration: tag trackers with UNGA, G20, bilateral summit dates
- Comparative country dashboards: tone on India across countries on one screen
- Briefing templates: Daily Media Environment Summary, Fortnightly Narrative Assessment
- Multi-language breakdown per tracker: "18 Urdu, 14 English, 8 Arabic"

**MEA quote:** "If Anveshak genuinely solves multi-language narrative tracking, that alone
justifies adoption. Meltwater's Arabic and Malay coverage is thin."

---

## Priority Matrix

| Phase | Capability | Beneficiary | Effort | Impact |
|-------|-----------|-------------|--------|--------|
| v2.1 | Hash chain + BSA certificate | NIA, ED, NCB, SEBI | Medium | Critical for court |
| v2.2 | Dormancy + reactivation | MEA | Small | High for diplomatic |
| v2.3 | Geographic tagging + flow viz | MEA, NCB | Large | Differentiator |
| v2.4 | Parent-child hierarchy | NIA, ED, NCB | Medium | High for complex cases |
| v2.5 | Classification + ACLs | NIA, MEA, SEBI | Large | Showstopper for NIA |
| v2.6 | Cross-topic trackers | NIA, ED | Medium | High for NIA |
| v2.7 | Velocity dashboards | MEA, SEBI | Small | High for MEA |
| v2.8 | Multi-agency sharing | All | Large | Differentiator |

**Recommended build order:** v2.1 → v2.2 → v2.4 → v2.7 → v2.3 → v2.5 → v2.6 → v2.8

Rationale: Evidence integrity (v2.1) unlocks government procurement. Dormancy (v2.2) is
small effort, high MEA impact. Hierarchy (v2.4) is needed before cross-topic (v2.6).
Velocity (v2.7) is small and serves two agencies. Geographic (v2.3) and classification
(v2.5) are large but critical. Sharing (v2.8) requires all previous features stable.

---

## Persona Reviews Reference

Full reviews from all 8 personas were conducted during feature design:
1. **Solution Architect** — Schema design, performance, edge cases, migration safety
2. **Product Manager** — Naming ("Tracker" not "Investigation"), adoption risk, demo strategy
3. **LEA Cyber Crime Analyst** — Search-first creation, FIR numbers, evidence preservation
4. **NIA Analyst** — Evidence integrity, classification, cross-topic, long-running ops
5. **MEA Analyst** — Geographic dimension, dormancy, provenance cascade, multi-language
6. **SEBI ISD Analyst** — Scrip extraction, velocity detection, coordination, Chinese wall
7. **ED/FIU Investigator** — CIN/DIN extraction, money trail correlation, legal hold
8. **NCB Analyst** — Identity persistence, drug image classification, dark web, OPSEC

Each persona identified v1 as sufficient for initial deployment with their specific v2
enhancements as the upgrade path.
