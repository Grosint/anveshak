# Platform Features Plan — V1 + V2 Roadmap

Generated: 2026-07-03
Status: Approved for implementation
Persona reviews: 8/8 complete (SA, PM, LEA Cyber, NIA, MEA, SEBI, ED, NCB)

---

## Persona Consensus

### What All Agree On

| Consensus | Personas |
|---|---|
| Event-triggered reports > cron-only | MEA, SEBI, NCB, ED |
| Exports need hash-sealed audit trail | ED, NIA, SEBI, NCB, LEA |
| Bulk import needs validation + quarantine | NIA, NCB, LEA, SA |
| Alert threshold changes need mandatory audit with reason | NIA, ED, LEA |
| Source health = activity monitoring, not DevOps uptime | MEA, SEBI, ED |
| Classification markings on exports | NIA, MEA, NCB |
| Scheduled reports need review gate before delivery | LEA, NIA |
| FIR/case reference field missing from data model | LEA (critical gap) |

### Where They Diverge

| Topic | View A | View B |
|---|---|---|
| Export: ship minimal vs wait for full compliance | PM, LEA: ship PDF now with headers | NIA: don't ship without BSA Section 63 signing |
| Bulk import: CSV vs paste box | SA, PM: CSV upload | LEA: free-text paste box (real workflow) |
| Source health priority | LEA: #1 priority (daily pain) | ED, PM: lowest priority |
| Alert rules: simple vs compound | PM: inline threshold only | MEA, SEBI, NCB: need compound rules |
| Scheduled reports priority | PM: #2 (PS-18 commitment) | NCB, ED: lowest priority |

### Priority Rankings by Persona

| Persona | #1 | #2 | #3 | #4 | #5 |
|---|---|---|---|---|---|
| **PM** | Export Signals | Scheduled Reports | Bulk Import | Alert Rules | Source Health |
| **LEA Cyber** | Source Health | Export Signals | Alert Rules | Bulk Import | Scheduled Reports |
| **NIA** | Alert Rules | Source Health | Scheduled Reports | Bulk Import | Export Signals |
| **MEA** | Export Signals | Alert Rules | Bulk Import | Source Health | Scheduled Reports |
| **SEBI** | Alert Rules | Export Signals | Bulk Import | Source Health | Scheduled Reports |
| **ED** | Bulk Import | Export Signals | Alert Rules | Scheduled Reports | Source Health |
| **NCB** | Alert Rules | Export Signals | Bulk Import | Source Health | Scheduled Reports |

---

## Critical Findings from Solution Architect

Half these features are partially built. Existing code:

| What Exists | Where | What's Missing |
|---|---|---|
| Scheduled report cron job | `reporter/worker.py` — `check_scheduled_reports` fires every 15 min | API endpoint to set cron, ARQ pool wiring (None bug), notification |
| Topic schedule columns | `topics.scheduled_report_cron`, `topics.scheduled_report_type` (migration 001) | PATCH endpoint, frontend UI |
| CSV signal export | `GET /api/v1/export/signals?topic_id=X&format=csv` in `routes/export.py` | Missing ISC, source list, evidence columns |
| Keyword alert rules backend | `keyword_alert_rules` table, full CRUD API | Frontend UI |
| Source health columns | `sources.health_status`, `consecutive_failures`, `health_error`, `last_checked_at` | Frontend page |
| Source list returns health data | `SQL_LIST_SOURCES_BY_ORG` already includes health columns | Frontend rendering |

### Bugs to Fix First

| Bug | Impact | Location |
|---|---|---|
| ARQ pool `ctx.get("arq_pool")` returns None in reporter | Scheduled reports created in DB but never enqueue for generation | `services/reporter/worker.py` startup() |
| JSONB `str()` serialization in CSV export | Python repr `{'key': 'value'}` instead of valid JSON | `services/api/routes/export.py` `_rows_to_csv` |
| No UNIQUE constraint on `sources(url_or_handle, platform)` | Bulk import creates duplicates silently | Schema migration needed |
| No CHECK constraint on `signal_threshold` | Analyst can set 0 (fire on everything) or 999 (disable signals) | Schema migration needed |
| `check_scheduled_reports` hardcodes 7-day window | Daily brief includes stale week-old content | `reporter/worker.py` |

---

## V1 vs V2 Split

### V1 — Ship Now

| Feature | V1 Scope |
|---|---|
| **Scheduled Reports** | Fix ARQ pool bug, PATCH endpoint, preset cadences (daily/weekly), review gate (pending → approved), WebSocket notification |
| **Source Health** | Inline health indicators on source list (colored dots), searchable, topic-filterable. Data already there. |
| **Bulk Import** | Free-text paste box + CSV upload, mandatory topic assignment, validation preview, import batch audit log |
| **Export Signals** | Enrich existing CSV (ISC, sources, evidence), PDF via reporter ARQ job, export audit log (SHA-256), IST timestamps, institutional headers, AI-generated section labels |
| **Alert Rules UI** | Expose existing `signal_threshold` + `identifier_signal_threshold` + `keyword_alert_rules` in frontend, mandatory reason on threshold change, CHECK constraint |

### V2 — Later

| Feature | V2 Scope |
|---|---|
| **Scheduled Reports** | Event-triggered reports (signal → auto-report), differential reports ("new since last"), audience/template selector |
| **Source Health** | Trend history table, activity rate charts (posts/day rolling), silence-as-signal detection, source activity timeline with enforcement event annotations |
| **Bulk Import** | Quarantine/review queue (`status='pending_review'`), auto-platform detection from URL/handle, Telegram channel ID resolution |
| **Export Signals** | Classification markings (RESTRICTED/OFFICIAL), redaction layer per agency tier, BSA Section 63 digital signing, FATF metadata for FIU sharing |
| **Alert Rules UI** | Compound rules (time windows, credibility filters, tier pickup, language spread, velocity change), per-analyst routing, stock symbol binding |

### Cross-Cutting V2 (Separate Initiatives)

| Initiative | Requested By | Description |
|---|---|---|
| **FIR/Case Reference Field** | LEA | Add `case_reference` field to topics, surface in reports/exports |
| **Analyst Notes** | LEA | Annotations on signals and content items |
| **Case Management Layer** | NIA, ED | ECIR/case wrapper, evidence attachment, prosecution complaint annex |
| **Cross-Report Search** | PM | Search across historical reports by identifier/entity |
| **Collaboration/Handover** | PM | Topic ownership transfer, analyst notes, handover reports |
| **Trading Data Overlay** | SEBI | NSE bhav copy ingest, price/volume correlation with content timeline |
| **Crypto Wallet Tracking** | NCB | BTC/ETH/USDT identifier type in Engine C |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| ARQ pool None bug — scheduled reports silently broken | HIGH | Fix in reporter `startup()` before any other work |
| Duplicate sources on bulk import — no UNIQUE constraint | HIGH | Add constraint in migration with dedup cleanup step |
| Export PDF architecture — WeasyPrint in API vs reporter | HIGH | ARQ job on reporter queue, poll from frontend |
| Threshold race condition — change during clustering job | MEDIUM | Add `WHERE cluster_id NOT IN (SELECT ...)` guard |
| CSV/JSON file upload attack surface | MEDIUM | Size limit (5MB), MIME check, defensive parsing |
| Dual source identity (`sources.org_id` + `org_sources`) | MEDIUM | Bulk import must maintain both — integration test |
| Source name exposure in health dashboard (OPSEC) | MEDIUM | Aggregate-only default view, names behind drill-in action |

---

## Implementation Plan

### Sprint 1: Fix Bugs + Backend Foundation (2-3 days)

1. Fix ARQ pool wiring in reporter `startup()`
2. Fix JSONB `str()` → `json.dumps()` in export CSV
3. Migration: UNIQUE constraint on `sources(url_or_handle, platform)` with dedup cleanup
4. Migration: CHECK constraint on `signal_threshold BETWEEN 1 AND 100`
5. PATCH `/topics/{id}` endpoint (signal_threshold, scheduled_report_cron, scheduled_report_type)
6. Threshold change audit log (table + mandatory reason field)

**Files:**
- `services/reporter/anveshak/reporter/worker.py`
- `services/api/anveshak/api/routes/export.py`
- `services/api/anveshak/api/routes/topics.py`
- `services/api/anveshak/api/db/topics.py`
- `services/api/migrations/versions/0XX_*.py` (new migration)

### Sprint 2: Export Enrichment + PDF (2-3 days)

7. Enrich `SQL_EXPORT_SIGNALS` with ISC, source list, evidence
8. Signal PDF ARQ job in reporter service
9. Export audit log (who, when, query params, SHA-256 of output)
10. PDF template: institutional header placeholder, IST timestamps, page numbers, AI-generated labels, mandatory disclaimer
11. Frontend: export button on signals page with CSV download + PDF polling

**Files:**
- `services/api/anveshak/api/db/export.py`
- `services/reporter/anveshak/reporter/signal_pdf.py` (new)
- `services/reporter/anveshak/reporter/worker.py`
- `frontend/src/components/signals/ExportButton.tsx` (new)

### Sprint 3: Source Health + Bulk Import (2-3 days)

12. Frontend: health status indicators inline on source list (colored dots, last_checked_at, error tooltip)
13. Frontend: search + topic filter on source list
14. Bulk import API endpoint (ARQ job, not synchronous)
15. Frontend: paste box + CSV upload, validation preview, mandatory topic assignment
16. Import batch audit log with per-row outcome

**Files:**
- `frontend/src/components/sources/SourceList.tsx`
- `frontend/src/components/sources/BulkImport.tsx` (new)
- `services/api/anveshak/api/routes/sources.py`
- `services/api/anveshak/api/jobs/import_sources.py` (new)

### Sprint 4: Alert Rules UI (1-2 days)

17. Frontend: topic settings panel with signal_threshold slider + mandatory reason field
18. Frontend: keyword alert rules CRUD (backend already exists)
19. Frontend: identifier_signal_threshold control
20. Threshold change history display inline with signal timeline

**Files:**
- `frontend/src/components/topics/AlertRulesPanel.tsx` (new)
- `frontend/src/components/topics/TopicSettings.tsx`

---

## Wiring Checklist

- [ ] PATCH topics endpoint → `verify_topic_access()` called
- [ ] Bulk import → `add_org_source()` + `add_topic_source()` both called per row
- [ ] Export audit log entry created on every export
- [ ] Threshold change → audit log row with reason (mandatory, non-empty)
- [ ] Signal PDF job → registered in reporter `WorkerSettings.functions`
- [ ] All new Pydantic models have `labels: Labels` + `ConfigDict(strict=True)`
- [ ] New migration does not break existing data (dedup before UNIQUE constraint)
- [ ] Import job validates platform against allowed set
- [ ] File upload size-limited + MIME-checked

---

## Verification

### TDD Test Plan

- Unit: threshold validation (0 rejected, 1-100 accepted, 101 rejected)
- Unit: CSV parsing with malformed input, JSONB serialization fix
- Unit: import validation (bad platform, missing URL, duplicate detection)
- Unit: export audit hash computation
- Integration: scheduled report actually enqueues after ARQ pool fix
- Integration: bulk import creates source + org_sources + topic_sources rows
- Integration: export audit log created with correct SHA-256
- Integration: threshold change audit log with reason field
- Frontend: vitest for alert rules panel, export button states, health indicators

### Manual Verification

1. `make build && make up && make migrate`
2. Set topic schedule → verify report appears after cron tick
3. Upload CSV of 10 sources → verify all linked to topic + org
4. Paste 5 Telegram handles → validation preview → import → sources appear
5. Export signals as CSV → verify ISC, source list columns present
6. Export signals as PDF → verify IST timestamp, headers, page numbers
7. Change signal threshold → verify audit log row with reason
8. Check source list → verify health indicators visible (green/yellow/red)

### Demo Walkthrough

1. Open topic → show alert rules panel → adjust threshold (reason required)
2. Paste 5 Telegram handles → validation preview → import → sources appear in list
3. Source list shows green/yellow/red health dots with tooltips
4. Signal fires → click export → PDF downloads with institutional header
5. Schedule daily report → next day report appears in reports list with "scheduled" badge

---

## Persona Review Archive

Full persona reviews available on request. Key quotes:

- **ED:** "Build the ECIR case management wrapper first. Let me create a case, attach evidence items to it, freeze reports against it."
- **NIA:** "Do not build 'export to PDF.' Build 'controlled export with classification enforcement, redaction rules, sharing audit, and BSA signing.'"
- **LEA Cyber:** "The actual workflow is: I get a list of Telegram handles in a WhatsApp message from a colleague. I am not sitting with a well-formatted CSV file."
- **MEA:** "What is needed is event-triggered report generation, not cron. A narrative spikes, you report."
- **SEBI:** "The content_hash collision across N sources in a time window is a direct coordination indicator. This should be a first-class signal type."
- **NCB:** "A dashboard showing which Telegram channels are being monitored is a registry of NCB surveillance targets. Source name redaction is mandatory."
- **PM:** "Export Signals is the highest-value feature on this list. Period. It closes the intelligence production cycle."
- **SA:** "Half these features are partially built. The ARQ pool bug means scheduled reports have been silently broken."
