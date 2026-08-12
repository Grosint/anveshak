# User Stories — OSINT Capability Gaps

Identified during Bidadi Township demo preparation (2026-08-11).
These represent capabilities Anveshak SHOULD have but currently lacks.

---

## US-001: Government Portal Scraper (DARPAN/FCRA)

**Title:** `feat: scrape NGO DARPAN and FCRA portals for org registration data`

**As** an intelligence analyst investigating foreign-funded NGOs,
**I want** Anveshak to automatically extract registration details from MHA DARPAN (ngodarpan.gov.in) and FCRA Online (fcraonline.nic.in),
**So that** I can map NGO registration numbers, FCRA status, bank details from annual returns, and foreign contribution amounts without manually searching government portals.

### Acceptance Criteria

- [ ] Given an org name, scrape DARPAN search results: unique ID, registration number, registration type, city, state, key persons
- [ ] Given an org name, scrape FCRA portal: FCRA registration number, validity dates, designated bank account (name + branch), annual foreign contribution received
- [ ] Handle DARPAN's JavaScript-rendered pages (Crawl4AI headless browser mode, not plain HTTP)
- [ ] Handle FCRA portal's CAPTCHA — queue for analyst solve or integrate CAPTCHA service
- [ ] Store results as `extracted_identifiers` linked to source entity
- [ ] Cross-link: if FCRA bank account appears in content_items from other topics → fire identifier convergence signal
- [ ] Rate limit: max 10 requests/minute per portal (polite scraping)
- [ ] Cache results 7 days — these records don't change daily

### Technical Notes

- DARPAN is server-rendered but uses pagination via query params — Crawl4AI can handle
- FCRA portal uses ASP.NET ViewState — need stateful session (Crawl4AI browser context persistence)
- FCRA annual returns (FC-4) contain: bank name, account number, total foreign contribution, donor-wise breakup — all public data under RTI
- New source type: `platform: "gov_portal"`, `source_type: "darpan"` / `"fcra"`

### Priority

**HIGH** — IB/MHA is target customer. Their own portals, and we can't read them.

### Identifier Types Extracted

| Field | Identifier Type | Example |
|-------|----------------|---------|
| DARPAN Unique ID | `NGO_DARPAN_ID` | `KA/2024/0123456` |
| FCRA Registration No | `FCRA_REG` | `094421234` |
| Bank Account | `BANK_ACCOUNT` | `SBI Mysore Main Branch, A/c 12345678901` |
| PAN | `PAN` | `AAATK1234A` |
| Annual FC Amount | metadata | `Rs 15,00,000 (FY 2024-25)` |

---

## US-002: Click-to-Reveal Extractor (JustDial, Sulekha, IndiaMart)

**Title:** `feat: extract hidden contact details from Indian business directories`

**As** an intelligence analyst tracing organizational networks,
**I want** Anveshak to extract phone numbers, addresses, and contact details from Indian business directories that hide data behind click-to-reveal or login walls,
**So that** I can build contact graphs for organizations without manual lookup on 10 different directory sites.

### Acceptance Criteria

- [ ] Extract phone numbers from JustDial listings (API reverse-engineering or headless browser click simulation)
- [ ] Extract contact details from Sulekha, IndiaMart, TradeIndia listings
- [ ] Handle JustDial's number obfuscation (CSS sprite positions or custom font glyphs)
- [ ] Store as `PHONE_IN` / `EMAIL` identifier type linked to org entity
- [ ] Cross-link: phone from JustDial org listing matches phone in Telegram message → fire convergence signal
- [ ] Respect rate limits, rotate user-agents
- [ ] Flag confidence: `extraction_method: "directory_listing"`, `confidence: 0.85`

### Technical Notes

- JustDial uses font-face obfuscation — each digit mapped to random glyph in custom font
  - Download font → parse cmap table → reverse map glyphs to digits
- Alternative: JustDial undocumented API (`/api/function/search/...`) returns JSON with encoded phone
- Sulekha/IndiaMart simpler — standard AJAX call on click, intercept via headless browser
- New adapter in scraper service (web sources, not social)

### Priority

**MEDIUM** — useful but not as unique as gov portal scraping.

---

## US-003: RTI Document Parser

**Title:** `feat: parse RTI responses and government gazette notifications for structured entity extraction`

**As** an intelligence analyst,
**I want** Anveshak to ingest PDF gazette notifications, RTI responses, and government orders, extract structured data (survey numbers, land areas, person names, amounts),
**So that** I can automatically link land acquisition notifications to persons and financial flows.

### Acceptance Criteria

- [ ] Ingest PDF/scanned gazette notifications via upload or URL
- [ ] OCR for scanned documents (Tesseract with Kannada + English + Hindi + Devanagari models)
- [ ] Extract structured fields: survey numbers, village names, acres/guntas, person names, amounts (Rs), notification numbers, case numbers
- [ ] Store as structured `extracted_identifiers` with document provenance
- [ ] Cross-link: survey number from gazette appears in content_item about land deal → fire signal
- [ ] Support batch upload (analyst drops 20 RTI PDFs at once)

### Technical Notes

- Tesseract 5 + `kan` (Kannada), `eng`, `hin` language packs
- Pre-process: deskew, binarize, denoise for scanned docs
- Regex patterns for Indian document identifiers:
  - Survey numbers: `Sy\.?\s*No\.?\s*[\d/]+`
  - Case numbers: `WP\s*No\.\s*\d+/\d{4}`, `PIL\s*No\.\s*\d+`
  - Amounts: `Rs\.?\s*[\d,]+(?:\.\d{2})?(?:\s*(?:crore|lakh|cr|L))?`
  - Notification: `No\.\s*[A-Z]+\s*\d+\s*[A-Z]+\s*\d{4}`
- Vision service can host Tesseract (already has ONNX runtime)
- New content type: `source_type: "document_upload"`

### Priority

**MEDIUM** — big differentiator for land/property intelligence. Unique in Indian OSINT market.

---

## US-004: SEBI/MCA Corporate Registry Scraper

**Title:** `feat: scrape SEBI EDIFAR and MCA portal for corporate entity data`

**As** an intelligence analyst investigating corporate-politician nexus,
**I want** Anveshak to extract company registration details, director names, shareholding patterns, and SEBI enforcement orders from MCA21 and SEBI portals,
**So that** I can map corporate networks connected to persons of interest.

### Acceptance Criteria

- [ ] Given a company name or CIN, scrape MCA: directors, registered address, authorized capital, filing history
- [ ] Given a company name, scrape SEBI enforcement orders: order numbers, penalties, noticee names
- [ ] Given a BSE/NSE code, extract shareholding pattern (promoter vs public vs FII)
- [ ] Store directors as `PERSON` entities, cross-link to other topics
- [ ] Cross-link: director name from MCA appears as land buyer in Topic 2 → fire convergence signal

### Technical Notes

- MCA21 (v3) is React SPA — needs headless browser
- SEBI enforcement orders are public PDFs — parse with US-003 RTI parser
- Tofler, Zauba Corp as fallback (aggregator sites, easier to scrape)
- BSE/NSE shareholding pattern via public quarterly filings

### Priority

**HIGH** — Sobha Developers case proved this. SEBI order + MCA directors + BSE shareholding = complete corporate intelligence.

---

## Implementation Sequence

```
Phase 1 (ship for demo): US-001 (DARPAN/FCRA) — directly serves IB/MHA customer
Phase 2 (month 1):       US-004 (SEBI/MCA) — corporate nexus intelligence
Phase 3 (month 2):       US-002 (JustDial) — contact graph enrichment
Phase 4 (month 3):       US-003 (RTI/Gazette) — document intelligence
```

Each phase adds a new source adapter. All identifiers flow into existing
identifier convergence engine — no new signal infrastructure needed.
