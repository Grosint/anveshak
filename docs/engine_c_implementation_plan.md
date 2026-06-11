# Engine C — Identifier Intelligence Implementation Plan

**Status:** Approved for implementation
**Duration:** 8 weeks (4 phases)
**Objective:** Transform Anveshak from narrative-only OSINT to identifier-aware intelligence platform
**Markets unlocked:** MEA (today), Police Cyber (Phase 1), SEBI (Phase 1), NCB/Narco (Phase 1)

---

## Architecture Overview

```
Content arrives (scraper/social)
    │
    ├── EXISTING NLP PIPELINE (unchanged)
    │   ├── Language detection
    │   ├── NLLB-200 translation
    │   ├── spaCy NER (PERSON, ORG, GPE, etc.)
    │   ├── VADER sentiment
    │   ├── YAKE keywords
    │   ├── Embedding (MiniLM-L6-v2, 384-dim)
    │   └── Entity MinHash
    │
    ├── NEW: IDENTIFIER EXTRACTION (Engine C, Step 1)
    │   ├── Phone numbers (Indian format)
    │   ├── UPI IDs (user@bank)
    │   ├── Crypto wallets (BTC, ETH, TRC-20)
    │   ├── Email addresses
    │   ├── Social handles (Telegram, Instagram)
    │   ├── URLs / phishing domains
    │   ├── Document IDs (GSTIN, Udyam, PAN, IFSC)
    │   └── Bank account numbers (contextual)
    │
    ├── NEW: SCAM TEMPLATE MATCHING (Engine C, Step 2)
    │   ├── Keyword overlap scoring
    │   ├── Embedding similarity to template reference
    │   ├── Expected identifier validation
    │   └── Confidence score → labels JSONB
    │
    ├── EXISTING: NARRATIVE CLUSTERING (unchanged)
    │   └── Leiden → narrative_clusters → ISC
    │
    ├── NEW: IDENTIFIER CLUSTERING (Engine C, Step 3)
    │   └── Group by shared identifier → identifier_clusters
    │
    └── SIGNALS (existing + 2 new types)
        ├── multi_source_convergence (existing)
        ├── sentiment_shift (existing)
        ├── cross_topic_convergence (existing)
        ├── identifier_convergence (NEW)
        └── scam_template_match (NEW)
```

---

## Finalized 10 Steps

### Step 1: Identifier Extraction Engine
**Module:** `services/analyst/anveshak/analyst/identifiers.py`
**Purpose:** Extract actionable identifiers from every content item using regex + context validation

**What gets built:**
- Pattern registry: 15 identifier types with compiled regex patterns
- Normalization layer: canonical form for each type (phone → 10-digit, UPI → lowercase, handles → strip @)
- Context validation: reduce false positives (10 digits near "call"/"WhatsApp" = phone; standalone = maybe not)
- Integration point: called from `analyse_content` ARQ job, AFTER spaCy NER
- Storage: new rows in `extracted_entities` table with new `entity_type` values

**Identifier types:**
| Type | Pattern | Normalization | False Positive Strategy |
|------|---------|--------------|----------------------|
| `PHONE_IN` | `(?:\+91\|0)?[6-9]\d{9}` | Strip to 10 digits | Require proximity to contact-context words OR standalone with +91/0 prefix |
| `UPI` | `[a-zA-Z0-9._-]+@(?:ybl\|paytm\|okaxis\|oksbi\|ibl\|upi\|axl\|icici\|apl\|barodampay)` | Lowercase | Very low FP — bank suffix is distinctive |
| `EMAIL` | Standard email regex | Lowercase | Exclude UPI matches (already caught above) |
| `CRYPTO_BTC` | `(?:1\|3\|bc1)[a-zA-HJ-NP-Z0-9]{25,62}` | Preserve case | Very low FP — prefix + length |
| `CRYPTO_ETH` | `0x[a-fA-F0-9]{40}` | Lowercase | Very low FP — prefix + exact length |
| `CRYPTO_TRC20` | `T[a-zA-Z0-9]{33}` | Preserve case | Moderate — validate checksum if possible |
| `TELEGRAM_HANDLE` | `@[a-zA-Z][a-zA-Z0-9_]{4,31}` | Strip @, lowercase | Context: in Telegram content = high confidence; in news article = lower |
| `INSTAGRAM_HANDLE` | Same as Telegram | Strip @, lowercase | Context: in Instagram content = high; elsewhere = needs validation |
| `URL_DOMAIN` | `https?://[^\s<>"']+` | Extract domain, strip params | Already extracted by NLP for link discovery; add domain normalization |
| `GSTIN` | `\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d][Z][A-Z\d]` | Uppercase | Very low FP — exact format |
| `UDYAM` | `UDYAM-[A-Z]{2}-\d{2}-\d{7}` | Uppercase | Very low FP — exact format |
| `PAN` | `[A-Z]{5}\d{4}[A-Z]` | Uppercase | Moderate — 10 chars, could match random strings; require context |
| `IFSC` | `[A-Z]{4}0[A-Z0-9]{6}` | Uppercase | Low FP — 5th char always 0 |
| `BANK_ACCOUNT` | `\d{9,18}` | Strip spaces | HIGH FP — only extract when near "account"/"a/c"/"bank" |
| `SEBI_REG` | `IN[A-Z]\d{12}` | Uppercase | Very low FP — exact format |

**Key design decisions:**
- Identifiers stored in SAME `extracted_entities` table as spaCy entities (no new table for extraction)
- New `entity_type` values coexist with spaCy types (PERSON, ORG, etc.)
- `confidence` field used: 1.0 for exact-match patterns (GSTIN), 0.7-0.9 for context-dependent (PHONE, PAN)
- Extraction runs on `clean_text` (post-translation English), NOT `raw_text`

### Step 2: Scam Template Library
**Module:** `services/analyst/anveshak/analyst/templates.py`
**Table:** `scam_templates` + `topic_templates` (join)
**Purpose:** Automatically classify content against known fraud/info-op patterns

**What gets built:**
- Template data model: keywords, min_keyword_hits, expected_identifiers, severity, reference_embedding, legal_sections
- Matching engine: keyword overlap + embedding similarity → confidence score
- 11 built-in templates shipped with platform
- Custom template CRUD via API (analyst creates per-org)
- Topic-template association: which templates active per topic
- Result stored in `content_items.labels`: `{"scam_template": "mule_recruitment", "template_confidence": 0.85}`

**Matching algorithm:**
```
For each active template T on this content item's topic:
  1. keyword_hits = count(T.keywords ∩ content_keywords)
  2. if keyword_hits < T.min_keyword_hits → skip
  3. keyword_score = keyword_hits / len(T.keywords)
  4. identifier_match = count(extracted_identifiers ∩ T.expected_identifiers) / len(T.expected_identifiers)
  5. if T.reference_embedding exists:
       embedding_score = cosine_sim(content.embedding, T.reference_embedding)
     else:
       embedding_score = 0
  6. confidence = max(
       (0.6 × keyword_score + 0.4 × identifier_match),
       embedding_score
     )
  7. if confidence ≥ 0.5 → MATCH
  8. Pick highest-confidence match if multiple templates match
```

**Built-in templates (11):**
| Name | Category | Primary User | Severity |
|------|----------|-------------|----------|
| `investment_fraud` | fraud | SEBI, Police | CRITICAL |
| `mule_recruitment` | fraud | Police, NCB | CRITICAL |
| `maas` (Mule-as-a-Service) | fraud | Police | CRITICAL |
| `digital_arrest` | fraud | Police | HIGH |
| `job_fraud` | fraud | Police | HIGH |
| `pump_and_dump` | fraud | SEBI | CRITICAL |
| `fake_research_report` | fraud | SEBI | HIGH |
| `drug_sale` | narco | NCB | HIGH |
| `drug_delivery_recruitment` | narco | NCB | HIGH |
| `fake_sim_sale` | fraud | Police | MEDIUM |
| `crypto_cashout` | fraud | Police, NCB | HIGH |

**MEA-specific templates (examples, created per-embassy):**
| Name | Category | Use |
|------|----------|-----|
| `anti_india_territorial` | info_op | "Arunachal = South Tibet" narrative |
| `anti_india_minority` | info_op | "India persecutes Muslims" narrative |
| `anti_india_kashmir` | info_op | Kashmir sovereignty narrative |
| `state_media_coordination` | info_op | Simultaneous same talking points |
| `fabricated_attribution` | info_op | Fake quotes attributed to Indian officials |

MEA templates are custom (created by embassy analysts), not built-in.

### Step 3: Identifier Clustering
**Module:** `services/analyst/anveshak/analyst/identifier_clustering.py`
**Table:** `identifier_clusters`
**Purpose:** Group content items sharing the same identifier to reveal actors/networks

**What gets built:**
- Cluster creation: when identifier X appears in 2+ content items from 2+ distinct sources → create cluster
- Incremental update: new content item with known identifier → add to existing cluster, update stats
- Source count: distinct `source_id` values in cluster (not platform — consistent with narrative ISC)
- Cluster metadata: identifier_type, identifier_value, source_count, content_item_count, first_seen, last_seen

**Table schema:**
```sql
CREATE TABLE identifier_clusters (
    id                  TEXT PRIMARY KEY,
    topic_id            TEXT NOT NULL REFERENCES topics(id),
    identifier_type     TEXT NOT NULL,       -- PHONE_IN, UPI, CRYPTO_BTC, etc.
    identifier_value    TEXT NOT NULL,       -- normalized value
    source_count        INT NOT NULL DEFAULT 0,
    content_item_count  INT NOT NULL DEFAULT 0,
    first_seen_at       TIMESTAMPTZ,
    last_seen_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    labels              JSONB NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX idx_ic_topic_type_value
    ON identifier_clusters(topic_id, identifier_type, identifier_value);

-- Junction table: which content items belong to which identifier cluster
CREATE TABLE identifier_cluster_items (
    identifier_cluster_id TEXT REFERENCES identifier_clusters(id),
    content_item_id       TEXT REFERENCES content_items(id),
    source_id             TEXT NOT NULL,
    PRIMARY KEY (identifier_cluster_id, content_item_id)
);
```

**Execution flow:**
```
After identifier extraction completes for a content item:
  For each extracted identifier (phone, UPI, etc.):
    1. Normalize identifier value
    2. SELECT identifier_cluster WHERE topic_id = X
       AND identifier_type = Y AND identifier_value = Z
    3. If cluster exists:
       - INSERT INTO identifier_cluster_items
       - UPDATE source_count, content_item_count, last_seen_at
    4. If no cluster AND this identifier appears in 2+ content items:
       - CREATE new identifier_cluster
       - Backfill: add all content items with this identifier
       - Compute initial source_count
    5. If source_count crosses signal threshold → fire signal
```

**Key design:**
- Runs in SAME `analyse_content` job, after identifier extraction
- Parallel to narrative clustering (both run, both produce signals)
- `identifier_cluster_id` NOT added as FK on `content_items` — one item can belong to MULTIPLE identifier clusters (phone cluster + UPI cluster). Junction table handles this.
- Cross-topic: identifier clusters are per-topic. Cross-topic identifier overlap is a future enhancement (use cross-topic convergence signal for now).

### Step 4: New Signal Types
**Module:** `services/analyst/anveshak/analyst/signal_engine.py` (extend existing)
**Purpose:** Fire alerts when identifier patterns or scam templates are detected

**Two new signal types:**

**4a: `identifier_convergence`**
- Fires when: same identifier appears in N+ distinct sources within a topic
- Threshold: per-topic configurable, column `identifier_signal_threshold` on topics table (default 2)
- SQL check: `SELECT * FROM identifier_clusters WHERE topic_id = $1 AND source_count >= $2 AND id NOT IN (recently_signaled)`
- Dedup: 24h window (same identifier_cluster_id + signal_type)
- Evidence JSONB:
  ```json
  {
    "identifier_cluster_id": "...",
    "identifier_type": "PHONE_IN",
    "identifier_value": "+919876543210",
    "source_count": 5,
    "sources": ["telegram:easy_money", "telegram:account_service", ...],
    "content_item_count": 14
  }
  ```
- Severity: HIGH if source_count >= 3, CRITICAL if source_count >= 5

**4b: `scam_template_match`**
- Fires when: content matches a scam template with confidence >= threshold
- Threshold: per-template severity determines signal behavior
  - CRITICAL templates → always fire signal
  - HIGH templates → fire if 2+ items match in 24h window
  - MEDIUM templates → fire if 3+ items match in 24h window
- Dedup: 24h window per (template_name + topic_id)
- Evidence JSONB:
  ```json
  {
    "template_name": "mule_recruitment",
    "template_display": "Mule Account Recruitment",
    "confidence": 0.85,
    "matched_keywords": ["bank account", "commission", "per transaction", "easy money"],
    "extracted_identifiers": {"PHONE_IN": ["+919876543210"], "TELEGRAM_HANDLE": ["account_service"]},
    "legal_sections": ["PMLA Section 3", "IT Act 66D"],
    "content_item_id": "..."
  }
  ```

**Integration:** Both signal types use the existing `signals` table, existing WebSocket delivery, existing signal status flow (new → acknowledged → dismissed).

### Step 5: Instagram Adapter
**Module:** `services/social/anveshak/social/adapters/instagram.py`
**Purpose:** Monitor Instagram profiles and hashtag searches for fraud/narco/finfluencer content

**What gets built:**
- Adapter using Instagrapi (unofficial Meta API)
- Two collection modes:
  - **Profile monitoring:** Fetch recent posts from pre-registered profile handles
  - **Hashtag search:** Search posts by hashtag (limited to avoid rate limits)
- Bio extraction: when fetching profile, extract bio text → feed through Engine C for identifiers
- Media extraction: image URLs for vision pipeline (deepfake, CLIP, EXIF, pHash)
- Circuit breaker: reuse existing `AdapterCircuitBreaker` from
  `services/social/anveshak/social/circuit_breaker.py` (Redis-backed, 3-state: CLOSED/OPEN/HALF_OPEN)
  - Parameters: `threshold=10` (Meta API is flaky), `cooldown_s=86400` (24h — Meta bans are longer)
  - Same Redis key pattern: `anveshak:social:failures:instagram`, `anveshak:social:opened_at:instagram`
  - Does NOT crash other adapters (per-adapter isolation already built)
- Rate limiting: max 100 requests/hour (conservative)
- Session management: login via stored session, re-login on expiry
- Must pass `SourceAdapterConformanceSuite`

**Data extracted per post:**
- `raw_text`: caption text
- `url`: `https://instagram.com/p/{shortcode}`
- `platform`: "instagram"
- `captured_at`: post timestamp
- `media_urls`: image/video URLs
- `source_handle`: @username

**Data extracted per profile (on first fetch + periodic refresh):**
- Bio text → content_item with `platform="instagram_bio"`
- Bio identifiers: phone, email, UPI, website link (Engine C extracts)
- Follower count, following count (stored in labels for context)

### Step 6: Tip-Line Ingestion Endpoint
**Module:** `services/api/anveshak/api/routes/tipline.py`
**Purpose:** Receive citizen-forwarded scam messages via HTTP POST (WhatsApp proxy)

**What gets built:**
- `POST /api/v1/tipline/ingest` — accepts forwarded message content
- Request body:
  ```json
  {
    "text": "message content forwarded by citizen",
    "media_url": "optional URL to attached image/video",
    "source_phone": "optional — tipline number that received it",
    "forwarded_from": "optional — original sender if known",
    "topic_id": "which topic to associate with"
  }
  ```
- Authentication: API key per organization (header `X-Api-Key`)
- Creates `content_item` with:
  - `platform = "tipline"`
  - `source_handle = "whatsapp_tipline"` (or configured name)
  - Flows through full NLP + Engine C pipeline
- Rate limiting: 100 requests/minute per API key (prevent abuse)
- No WhatsApp Business API dependency — any HTTP client can POST
- Use cases:
  - Police WhatsApp tipline bot forwards received messages
  - Citizen web form submits scam content
  - Bulk import from complaint database (CSV → API calls)

### Step 7: Identifier Search API
**Module:** `services/api/anveshak/api/routes/identifiers.py`
**Purpose:** Let analysts search, browse, and export identifiers

**Endpoints:**
- `GET /api/v1/identifiers/search?q=+919876543210&type=PHONE_IN`
  → Returns all content items containing this identifier, grouped by source
  → Supports partial match (last 6 digits of phone, domain part of UPI)
- `GET /api/v1/identifiers/top?topic_id=X&type=PHONE_IN&limit=20`
  → Returns most frequently appearing identifiers (by source_count desc)
  → Filterable by identifier type
- `GET /api/v1/identifiers/clusters?topic_id=X`
  → Returns all identifier clusters for a topic, sorted by source_count desc
- `GET /api/v1/identifiers/clusters/{cluster_id}`
  → Returns full cluster detail: identifier, all content items, all sources, timeline
- `GET /api/v1/identifiers/export?topic_id=X&format=csv`
  → CSV/JSON export of all identifiers with metadata (for feeding into CFCFRMS, I4C, bank requests)
- `GET /api/v1/identifiers/co-occurrence?identifier_a=X&identifier_b=Y`
  → Returns content items where BOTH identifiers appear (network inference)

**Indexes required:**
- `idx_entities_type_text` already exists (composite) — extend with trigram for partial match
- New: `idx_entities_identifier_type` partial index `WHERE entity_type IN ('PHONE_IN', 'UPI', ...)` for fast filtering

### Step 8: Frontend — Identifier Dashboard
**Module:** `frontend/src/pages/Identifiers/`
**Purpose:** Visual interface for identifier intelligence

**What gets built:**
- New nav item: "Identifiers" (between "Signals" and "Reports")
- **Identifier table view:**
  - Columns: Value, Type, Source Count, First Seen, Last Seen, Template Match
  - Sortable by source count (most suspicious first)
  - Filterable by type (Phone, UPI, Crypto, Handle, etc.)
  - Click row → identifier detail view
- **Identifier detail view:**
  - All content items containing this identifier (timeline, newest first)
  - Source breakdown: which channels/sites this appeared in
  - Template matches: which scam templates matched content with this identifier
  - Co-occurring identifiers: other identifiers that appear in same content items
  - Mini network graph: identifier → sources (using existing Cytoscape.js or simple SVG)
- **Identifier cluster view:**
  - Card per cluster showing: identifier value, type, source count, item count, severity
  - Click → detail view with all linked content
- **Export button:** CSV download of all identifiers (for CFCFRMS submission)
- **Integration with existing views:**
  - Signal cards show extracted identifiers inline (phone, UPI in signal card)
  - Content item detail shows extracted identifiers highlighted in text
  - Reports include identifier summary section

**Component reuse:**
- Table component: reuse existing content table pattern
- Detail panel: reuse existing entity detail pattern with embedded prop
- Export: reuse existing CSV export pattern
- Lazy-load Cytoscape.js for network graph (behind click, not on page load)

### Step 9: Report Enhancements
**Module:** `services/reporter/anveshak/reporter/` (extend existing)
**Purpose:** Include identifier intelligence in generated reports

**What gets modified:**
- **RAG context assembly:** Include identifier summary alongside content chunks
  ```
  IDENTIFIED INDICATORS IN THIS TOPIC:
  Phones: +91-98765XXXXX (5 sources), +91-87654XXXXX (3 sources)
  UPI IDs: service123@paytm (4 sources), easymoney@ybl (2 sources)
  Crypto: TRc8x...4Kj2 (2 sources)
  Handles: @account_service_india (5 sources)
  ```
- **Report template sections (added):**
  - "Identified Indicators" — table of all extracted identifiers with source counts
  - "Identifier Clusters" — summary of actor clusters with linked identifiers
  - "Scam Template Matches" — which templates matched, with confidence scores
  - "Recommended Actions" — auto-generated based on template (CDR request for phone, UPI freeze for UPI, etc.)
- **Legal mapping enhancement:** Template-specific legal sections injected into report
  - Mule recruitment → PMLA Section 3, 4
  - Investment fraud → SEBI (PFUTP) Regulations
  - Drug sale → NDPS Act Sections 20, 22, 25
  - Info operation → (no domestic legal action, but flag for XP Division response)
- **PDF layout:** New section in PDF between "Key Findings" and "Source Citations"

### Step 10: Database Migration
**Module:** `services/api/migrations/versions/` (new migration file)
**Purpose:** Schema changes for Engine C

**New tables:**
```sql
-- Scam/info-op templates
CREATE TABLE scam_templates (
    id                   TEXT PRIMARY KEY,
    org_id               TEXT REFERENCES organizations(id),
    name                 TEXT NOT NULL,
    display              TEXT NOT NULL,
    category             TEXT NOT NULL CHECK (category IN ('fraud', 'info_op', 'narco', 'custom')),
    keywords             TEXT[] NOT NULL DEFAULT '{}',
    min_keyword_hits     INT NOT NULL DEFAULT 3,
    expected_identifiers TEXT[] DEFAULT '{}',
    severity             TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    reference_embedding  vector(384),
    legal_sections       TEXT[] DEFAULT '{}',
    is_builtin           BOOLEAN DEFAULT FALSE,
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    labels               JSONB NOT NULL DEFAULT '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
);

-- Topic-template association
CREATE TABLE topic_templates (
    topic_id    TEXT REFERENCES topics(id) ON DELETE CASCADE,
    template_id TEXT REFERENCES scam_templates(id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, template_id)
);

-- Identifier clusters
CREATE TABLE identifier_clusters (
    id                  TEXT PRIMARY KEY,
    topic_id            TEXT NOT NULL REFERENCES topics(id),
    identifier_type     TEXT NOT NULL,
    identifier_value    TEXT NOT NULL,
    source_count        INT NOT NULL DEFAULT 0,
    content_item_count  INT NOT NULL DEFAULT 0,
    first_seen_at       TIMESTAMPTZ,
    last_seen_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    labels              JSONB NOT NULL DEFAULT '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'
);
CREATE UNIQUE INDEX idx_ic_topic_type_value
    ON identifier_clusters(topic_id, identifier_type, identifier_value);

-- Identifier cluster items (junction)
CREATE TABLE identifier_cluster_items (
    identifier_cluster_id TEXT REFERENCES identifier_clusters(id) ON DELETE CASCADE,
    content_item_id       TEXT REFERENCES content_items(id) ON DELETE CASCADE,
    source_id             TEXT NOT NULL,
    PRIMARY KEY (identifier_cluster_id, content_item_id)
);
```

**Modified tables:**
```sql
-- Topics: add identifier signal threshold
ALTER TABLE topics ADD COLUMN identifier_signal_threshold INT NOT NULL DEFAULT 2;

-- extracted_entities: no schema change needed — new entity_type values are just strings
-- content_items: no FK change — identifier clusters use junction table
```

**New indexes:**
```sql
-- Fast identifier type filtering
CREATE INDEX idx_entities_identifier_types
    ON extracted_entities(entity_type, entity_text)
    WHERE entity_type IN ('PHONE_IN', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH',
                          'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE',
                          'URL_DOMAIN', 'GSTIN', 'UDYAM', 'PAN', 'IFSC',
                          'BANK_ACCOUNT', 'SEBI_REG');

-- Identifier cluster lookup by source count
CREATE INDEX idx_ic_source_count ON identifier_clusters(topic_id, source_count DESC);
```

**Seed data:** Insert 11 built-in templates with `is_builtin=true`, `org_id=NULL` (global).

---

## Development Workflow (Per Step)

Every step follows this workflow. No exceptions.

```
1. /tdd           → Write failing tests FIRST (RED)
2. Implement      → Write code until tests pass (GREEN)
3. Refactor       → Clean up without breaking tests (REFACTOR)
4. /code-review   → Review code for quality, architecture, security
5. Fix findings   → Address all FAIL issues from code review
6. /test          → Run appropriate test layer for what changed
7. Gate check     → ALL existing + new tests must pass before next step
```

---

## Test Types Used in Engine C

All 9 test types are mapped to specific Engine C components. Each phase
specifies exactly which test types run at exit.

| # | Type | What it covers in Engine C | When it runs |
|---|------|---------------------------|-------------|
| 1 | **Unit** | Identifier regex matching, normalization, context validation. Template keyword scoring, confidence calc. Identifier cluster source_count logic. Signal threshold math. Pydantic models (labels non-optional). | Every step. `make test-unit` |
| 2 | **Integration** | Identifier extraction → `extracted_entities` table (real PG). Template matching → `content_items.labels` (real PG). Identifier clustering → `identifier_clusters` table (real PG + Redis). Signal firing → `signals` table. API endpoints → real HTTP responses. Multi-tenancy isolation (org_id filtering). | Every phase exit. `make test-integration` |
| 3 | **E2E** | Full pipeline: content ingested → identifiers extracted → template matched → cluster formed → signal fired → WebSocket delivered → report generated with identifier section. 4 agency scenarios (MEA, Police, SEBI, NCB) against seeded demo data with real JWT auth. | Phase EC-4. `make test-e2e` |
| 4 | **Smoke** | After `make up`: `/health/ready` returns 200. New tables exist. New indexes exist. Built-in templates seeded. Identifier extraction enabled (not silently disabled by missing env var). | Every phase exit. `make test-smoke` |
| 5 | **Contract** | ARQ job `analyse_content` signature unchanged (first param `ctx`, async). New signal types (`identifier_convergence`, `scam_template_match`) have required evidence fields. Template CRUD API response shapes match frontend expectations. Identifier search API response shapes validated. Instagram adapter conforms to `SourceAdapterBase` interface. | Every phase exit. `make test-contract` |
| 6 | **Resilience** | Identifier extraction on malformed text (no crash, return empty list). Template matching when no templates exist (graceful skip). Identifier clustering when Redis is down (fail-open, log warning). Instagram adapter circuit breaker (10 failures → OPEN, cooldown → HALF_OPEN → probe). Report generation when no identifiers found (section omitted, not crash). | Phase EC-4. `make test-resilience` |
| 7 | **Regression** | Existing NLP pipeline produces same entities, sentiment, keywords after Engine C wired in. Existing narrative clustering ISC unchanged. Existing 3 signal types fire at same thresholds. `content_hash` dedup still works. Credibility audit trail unaffected. Report immutability guard (`WHERE generated_at IS NULL`) still holds. | Every phase exit. `make test-unit` (regression tests live in unit suite) |
| 8 | **Migration** | New tables exist (`scam_templates`, `topic_templates`, `identifier_clusters`, `identifier_cluster_items`). `identifier_signal_threshold` column on `topics`. New indexes exist. Labels JSONB non-optional on all new tables. CHECK constraints on `scam_templates.category` and `severity`. pgvector extension still loaded. RLS policies still active on existing tables. | Phase EC-1. `make test-migration` |
| 9 | **Connectivity** | Instagram API reachable (Instagrapi login succeeds). Tip-line endpoint accepts POST from external client. Skipped in CI — manual only. | Phase EC-3 (manual). Skipped in CI. |

---

## Phased Implementation Plan

### Phase EC-1: Foundation (Week 1-2)
**Goal:** Identifiers extracted from every content item. Templates matching. Clusters forming.

#### Week 1: Database Migration + Identifier Extraction

| Day | Task | Workflow |
|-----|------|---------|
| 1 | **Migration (Step 10)**: Create all new tables, indexes, constraints. Seed 11 built-in templates. Add `identifier_signal_threshold` to topics. | `/tdd` → Migration tests (type 8): tables exist, columns correct, constraints valid, templates seeded, labels non-optional. Implement migration. `/code-review`. |
| 2-3 | **Identifier extractor (Step 1):** Build `identifiers.py` — 15 regex patterns + normalization + context validation. | `/tdd` → Unit tests (type 1): 15 identifier types × 4 tests each (positive match, negative, normalization, edge case) = 60 tests. Implement one type at a time. `/code-review`. |
| 4 | **Pipeline integration:** Wire `extract_identifiers()` into `analyse_content` ARQ job after spaCy NER. | `/tdd` → Contract test (type 5): `analyse_content` signature unchanged. Integration test (type 2): content with phone → PHONE_IN in `extracted_entities`. Regression test (type 7): existing NER entities still produced. |
| 5 | **Context validation + false positive filters.** PAN/BANK_ACCOUNT require proximity to context words. | `/tdd` → Unit tests (type 1): "His PAN is ABCDE1234F" → extracted; "ABCDE1234F" alone → NOT extracted. |

**Week 1 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit        — all existing + ~60 new identifier unit tests
  [ ] make test-integration — identifier extraction writes to real PG
  [ ] make test-migration   — all new tables, indexes, seed data exist
  [ ] make test-contract    — analyse_content signature unchanged
  [ ] make test-smoke       — /health/ready 200, new tables visible

Regressions verified:
  [ ] Existing NLP pipeline unchanged (same entities, sentiment, keywords)
  [ ] 267 existing tests still pass
  [ ] /code-review on identifiers.py — all FAIL issues resolved
```

#### Week 2: Scam Templates + Identifier Clustering

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **Template matching engine (Step 2):** Build `templates.py` — keyword scoring, identifier validation, embedding similarity, confidence calculation. | `/tdd` → Unit tests (type 1): 11 templates × 2 tests (positive + negative) = 22 tests. Test confidence scoring formula. Test "no active templates" → graceful skip. `/code-review`. |
| 2 | **Template CRUD API.** Create, read, update, delete custom templates. Topic-template association. | `/tdd` → Unit tests for DB functions. Contract tests (type 5): API response shapes. Integration tests (type 2): CRUD with real PG, org isolation. `/code-review`. |
| 3-4 | **Identifier clustering (Step 3):** Build `identifier_clustering.py`. Create/update clusters when identifiers extracted. | `/tdd` → Unit tests (type 1): source_count logic, dedup logic. Integration tests (type 2): 3 items with same phone from 3 sources → cluster with source_count=3. 4th item from same source → source_count stays 3. `/code-review`. |
| 5 | **Full pipeline integration:** Wire template matching + identifier clustering into `analyse_content` job. | `/tdd` → Integration test (type 2): content with mule keywords + phone → template match in labels AND identifier cluster created. Regression test (type 7): existing clustering + signals unaffected. |

**Week 2 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit        — all existing + ~82 new (60 identifier + 22 template)
  [ ] make test-integration — template CRUD, identifier clustering with real PG
  [ ] make test-contract    — template API response shapes, analyse_content signature
  [ ] make test-smoke       — /health/ready 200, templates endpoint reachable

Regressions verified:
  [ ] Narrative clustering still works (Leiden, ISC counting)
  [ ] Existing signals still fire at same thresholds
  [ ] All existing tests still pass
  [ ] /code-review on templates.py, identifier_clustering.py — all FAIL resolved
```

### Phase EC-2: Signals + API (Week 3-4)
**Goal:** Signals fire for identifier patterns and template matches. API serves identifier data.

#### Week 3: New Signal Types

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **Identifier convergence signal (Step 4a):** Extend `signal_engine.py`. | `/tdd` → Unit tests (type 1): threshold logic, severity mapping. Integration test (type 2): cluster with source_count=3, topic threshold=2 → signal in `signals` table. Dedup: same cluster doesn't fire twice in 24h. Regression test (type 7): existing 3 signal types unaffected. `/code-review`. |
| 3-4 | **Scam template match signal (Step 4b):** Extend `signal_engine.py`. | `/tdd` → Unit tests (type 1): CRITICAL → immediate fire, HIGH → 2+ matches, MEDIUM → 3+ matches. Integration test (type 2): insert CRITICAL template match → signal in DB. `/code-review`. |
| 5 | **WebSocket delivery verification.** Both new signal types through existing delivery pipeline. | `/tdd` → Contract test (type 5): WebSocket payload contains identifier_type, identifier_value, source_count for identifier_convergence. Contains template_name, confidence, legal_sections for scam_template_match. Integration test (type 2): WebSocket client receives new signal types. |

**Week 3 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit        — signal threshold + severity unit tests
  [ ] make test-integration — signals fire and deliver via WebSocket
  [ ] make test-contract    — WebSocket payload shapes for new signal types
  [ ] make test-smoke       — signals endpoint still returns 200

Regressions verified:
  [ ] multi_source_convergence, sentiment_shift, cross_topic_convergence unchanged
  [ ] Signal status flow (new → acknowledged → dismissed) unchanged
  [ ] /code-review on signal_engine.py changes — all FAIL resolved
```

#### Week 4: Identifier Search API

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **6 API endpoints (Step 7):** search, top, clusters, cluster detail, export, co-occurrence. | `/tdd` → Unit tests (type 1): DB query functions. Contract tests (type 5): response shapes for all 6 endpoints. Integration tests (type 2): insert test data → search returns correct results, export generates valid CSV, co-occurrence finds shared items. `/code-review`. |
| 3 | **Partial match.** Phone suffix, UPI domain, handle substring. | `/tdd` → Unit tests: partial match SQL logic. Integration test: search "543210" → returns full phone. Search "@paytm" → returns all paytm UPIs. |
| 4-5 | **Multi-tenancy.** Org isolation on all identifier endpoints. | `/tdd` → Integration test (type 2): org A user searches → only org A identifiers. Org B same query → different results. Regression test (type 7): existing topic/source org isolation unaffected. `/code-review`. |

**Week 4 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit        — all identifier API unit tests
  [ ] make test-integration — all 6 endpoints with real PG, org isolation
  [ ] make test-contract    — all API response shapes validated
  [ ] make test-smoke       — /api/v1/identifiers/search returns 200

Regressions verified:
  [ ] Existing API endpoints unchanged
  [ ] Multi-tenancy on topics, sources, content still works
  [ ] /code-review on all new route files — all FAIL resolved
```

### Phase EC-3: Instagram + Tipline + Frontend (Week 5-6)
**Goal:** New data sources flowing. Analysts see identifiers in the UI.

#### Week 5: Instagram Adapter + Tip-Line

| Day | Task | Workflow |
|-----|------|---------|
| 1-3 | **Instagram adapter (Step 5).** Profile monitoring, hashtag search, bio extraction, circuit breaker. | `/tdd` → Unit tests (type 1): mock Instagrapi → test post/bio/media extraction. Contract test (type 5): adapter conforms to `SourceAdapterBase` interface. Resilience test (type 6): 10 consecutive 403s → circuit OPEN, cooldown → HALF_OPEN. Connectivity test (type 9): real Instagram login (manual, skipped in CI). `/code-review`. |
| 4-5 | **Tip-line endpoint (Step 6).** POST ingest, API key auth, pipeline integration. | `/tdd` → Unit tests (type 1): request validation, API key auth logic. Contract test (type 5): tipline request/response shape. Integration test (type 2): POST message with phone → content_item created → phone extracted → identifier cluster updated. Resilience test (type 6): invalid payload → 400 not crash, missing API key → 401. `/code-review`. |

**Week 5 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit         — Instagram adapter unit tests, tipline unit tests
  [ ] make test-integration  — tipline → full pipeline flow with real PG
  [ ] make test-contract     — Instagram conforms to SourceAdapterBase,
                                tipline request/response shapes
  [ ] make test-smoke        — /api/v1/tipline/ingest returns 401 (no key) / 200 (with key)
  [ ] make test-resilience   — Instagram circuit breaker, tipline bad payload handling

Regressions verified:
  [ ] Existing social adapters (Telegram, Reddit, Bluesky, X) unaffected
  [ ] Existing social circuit breaker still works for all adapters
  [ ] /code-review on instagram.py, tipline.py — all FAIL resolved
```

#### Week 6: Frontend Identifier Dashboard

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **Identifier table view (Step 8).** Sort by source_count, filter by type. | Frontend tests: component renders, sort works, filter shows correct types. Contract test (type 5): mock API factory returns unwrapped shape matching real API. |
| 3 | **Identifier detail + cluster view.** Timeline, source breakdown, co-occurrence. | Frontend tests: detail view renders correct items, sources listed. |
| 4 | **Signal card + content item enhancements.** Identifiers inline in signals. Highlighted in content detail. | Frontend tests: signal card shows identifier value for new signal types. Content detail shows highlighted identifiers. Regression: existing signal card rendering unchanged for old signal types. |
| 5 | **Export + polish.** CSV download. Responsive layout. | Frontend tests: export triggers download. `npm run build` → 0 TS errors. |

**Week 6 exit gate:**
```
Tests that MUST pass:
  [ ] npm run build          — 0 TypeScript errors
  [ ] npm run test           — all frontend tests pass
  [ ] make test-contract     — API mock shapes match real API responses
  [ ] make test-smoke        — all pages load without console errors

Regressions verified:
  [ ] Existing pages (Topics, Sources, Signals, Reports) unchanged
  [ ] Existing signal card rendering unchanged for old signal types
  [ ] Navigation still works (all routes resolve)
```

### Phase EC-4: Reports + Hardening + Demo (Week 7-8)
**Goal:** Reports include identifier intelligence. Full test suite green. Demo-ready for all 4 agencies.

#### Week 7: Report Enhancements + Resilience + Regression

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **Report enhancements (Step 9).** Identifier section, cluster summary, template matches, legal mapping, recommended actions. | `/tdd` → Unit tests (type 1): report context assembly includes identifiers. Integration test (type 2): generate report → PDF contains indicator section, legal mapping correct. `/code-review`. |
| 3 | **4 agency scenario reports.** MEA, Police, SEBI, NCB report generation verified. | `/tdd` → Integration test (type 2): 4 reports with different template/identifier combinations. Verify correct legal sections per agency context (PMLA for mule, PFUTP for pump-and-dump, NDPS for drug, no legal for MEA info_op). |
| 4 | **Resilience testing (type 6).** All degradation scenarios. | Identifier extraction on garbage text → empty list, no crash. Template matching with 0 active templates → skip gracefully. Identifier clustering when Redis down → fail-open, log warning. Report generation with 0 identifiers → section omitted, not crash. Instagram circuit breaker full cycle. |
| 5 | **Regression sweep (type 7).** All known invariants verified. | Existing content_hash dedup still works. Credibility audit trail still appends. Report immutability (`generated_at IS NULL` guard) still holds. Narrative clustering ISC calculation unchanged. 3 existing signal types fire at exact same thresholds. spaCy NER produces same entity count for known test content. |

**Week 7 exit gate:**
```
Tests that MUST pass:
  [ ] make test-unit         — all unit tests (existing + new)
  [ ] make test-integration  — report generation with identifiers, all 4 agency scenarios
  [ ] make test-resilience   — all degradation scenarios pass
  [ ] make test-contract     — report response shapes unchanged

Regressions verified:
  [ ] Every regression test (type 7) passes
  [ ] /code-review on reporter changes — all FAIL resolved
```

#### Week 8: E2E Testing + Demo Preparation

| Day | Task | Workflow |
|-----|------|---------|
| 1-2 | **E2E tests (type 3).** Full pipeline against seeded data. 4 agency scenarios end-to-end. | E2E test: seed 4 topics (MEA, Police, SEBI, NCB) with realistic content → verify for EACH: content ingested → identifiers extracted → templates matched → clusters formed → signals fired → reports generated with correct sections. Real JWT auth. Real PostgreSQL + Redis. |
| 3 | **Demo data seeding.** Create realistic demo topics with pre-seeded content for live demos. | Seed scripts: "Cyber Fraud Demo" (mule + investment fraud content), "MEA Beijing Demo" (Chinese media articles), "SEBI Surveillance Demo" (pump-and-dump messages), "NCB Intelligence Demo" (drug channel content). `/test demo-check` to verify all demo steps pass. |
| 4 | **Demo scripts.** Step-by-step walkthrough document per agency. | Document: what to click, what signals appear, what the report looks like, talking points per screen. One script per agency. |
| 5 | **Final gate.** ALL test types pass. Coverage verified. System healthy. | Run full test suite in sequence (or see Makefile targets below). |

**Week 8 exit gate:**
```
  [ ] make test-unit         — all unit tests pass
  [ ] make test-integration  — all integration tests pass
  [ ] make test-e2e          — 4 agency E2E scenarios pass
  [ ] make test-smoke        — /health/ready 200, all endpoints reachable
  [ ] make test-contract     — all service seam agreements hold
  [ ] make test-resilience   — all degradation scenarios handled
  [ ] make test-migration    — all tables, indexes, constraints, seeds present
  [ ] npm run build          — 0 TypeScript errors
  [ ] npm run test           — all frontend tests pass
  [ ] Coverage ≥ 80% on all new Engine C modules
  [ ] ALL existing tests (267+) still pass
```

### Phase EC-5: Demo Seed Data + Validation (Week 9)
**Goal:** 4 agency-specific demo topics seeded with org isolation. `/demo-check` passes all 50 steps.

#### Organization & User Setup

Each agency demo gets its own org + user. Data is completely isolated via multi-tenancy.

| Org | User | Role | Demo Topic |
|-----|------|------|-----------|
| `org_mea` | `demo_mea@anveshak.local` | analyst | MEA Beijing Demo |
| `org_cyber` | `demo_cyber@anveshak.local` | analyst | Cyber Fraud Demo |
| `org_sebi` | `demo_sebi@anveshak.local` | analyst | SEBI Surveillance Demo |
| `org_ncb` | `demo_ncb@anveshak.local` | analyst | NCB Intelligence Demo |
| (existing) | `superadmin@anveshak.local` | super-admin | Can see all orgs for cross-org isolation test |

#### Seed Data Requirements Per Agency

**MEA Beijing Demo (org_mea):**
```
Topic: "Anti-India Narratives in Chinese Media"
Keywords: "India", "LAC", "Arunachal", "South Tibet", "Modi"

Sources (5):
  - web/RSS: Global Times, CGTN, Xinhua, People's Daily, China Military Online

Content items (10+):
  - 4 articles in Chinese (zh) → must have translated_text after pipeline
  - 6 articles in English
  - 3+ articles about "Arunachal = South Tibet" (same narrative → cluster)
  - 3+ articles about "India road building near LAC" (second cluster)
  - At least 3 from different sources sharing same narrative (ISC ≥ 3 → signal)

Expected after pipeline:
  - ≥ 2 narrative clusters
  - ≥ 1 multi_source_convergence signal
  - translated_text populated for Chinese articles
  - GeoJSON locations extractable (Arunachal, LAC, Tawang)

Templates active: none required (MEA uses custom info_op templates, not built-in)
Identifiers: not primary for MEA — but URLs of Chinese media extracted as URL_DOMAIN
```

**Cyber Fraud Demo (org_cyber):**
```
Topic: "Mule Account & Investment Fraud Networks"
Keywords: "bank account", "commission", "guaranteed returns", "easy money"

Sources (6):
  - telegram: "Easy Money India", "Account Service 24/7", "VIP Earning Group",
              "Investment Tips Pro", "Trading VIP"
  - web: fakeinvestment.example.com

Content items (20+):
  - 8 mule recruitment messages across 4 Telegram channels
    Each contains: phone number (+91-9876543210 in 3+ channels → cluster)
    Each contains: UPI ID (service123@paytm in 2+ channels)
    Each contains: Telegram handle (@account_service in 3+ channels)
    Keywords: "bank account for sale", "₹5000 per transaction", "no questions"
  - 6 investment fraud messages across 3 channels
    Each contains: phone (+91-8765432109 in 2+ channels)
    Each contains: website URL (fakeinvestment.example.com)
    Keywords: "guaranteed 5% daily", "invest now", "no risk"
  - 4 MaaS (Mule-as-a-Service) messages
    Keywords: "bulk accounts", "verified accounts", "cash out service"
    Contains: different phone (+91-7654321098)
  - 2 messages with GSTIN (shell company facade)

Expected after pipeline:
  - ≥ 3 identifier clusters (one per phone appearing in 2+ sources)
  - ≥ 1 identifier_convergence signal (phone in 3+ sources)
  - ≥ 1 scam_template_match signal (mule_recruitment CRITICAL)
  - content_items.labels.scam_template = "mule_recruitment" on 8+ items
  - content_items.labels.scam_template = "investment_fraud" on 6+ items
  - Extracted identifiers: PHONE_IN, UPI, TELEGRAM_HANDLE, GSTIN, URL_DOMAIN
  - Report contains "Identified Indicators" section

Templates active: mule_recruitment, maas, investment_fraud
```

**SEBI Surveillance Demo (org_sebi):**
```
Topic: "Pump-and-Dump Detection — Small Cap"
Keywords: "multibagger", "guaranteed returns", "buy before", "insider tip"

Sources (5):
  - telegram: "Stock Tips Free", "Penny Stock VIP", "Trading Guru India",
              "Research Reports Daily"
  - web: fakeresearch.example.com

Content items (15+):
  - 10 pump-and-dump messages pushing same stock "XYZLTD" across 4 channels
    Keywords: "XYZLTD next multibagger", "buy before ₹500", "100% guaranteed"
    Contains: Telegram handle (@stockguru_india in 3+ channels)
    Contains: UPI (premiumtips@paytm — "₹999 for VIP access")
    Contains: phone (+91-9998877665 — "call for premium tips")
  - 3 fake research report messages
    Contains: URL (fakeresearch.example.com/reports/xyz.pdf)
    Keywords: "target price ₹500", "buy rating", "SEBI registered"
    Contains: SEBI_REG number (INZ000123456789 — fake, needs verification)
  - 2 generic stock tip messages (control — should NOT match templates)

Expected after pipeline:
  - ≥ 1 narrative cluster (coordinated XYZLTD push, ISC ≥ 4)
  - ≥ 1 identifier cluster (@stockguru_india in 3+ channels)
  - ≥ 1 multi_source_convergence signal
  - ≥ 1 scam_template_match signal (pump_and_dump CRITICAL)
  - content_items.labels.scam_template = "pump_and_dump" on 10+ items
  - Extracted identifiers: TELEGRAM_HANDLE, UPI, PHONE_IN, URL_DOMAIN, SEBI_REG

Templates active: pump_and_dump, fake_research_report
```

**NCB Intelligence Demo (org_ncb):**
```
Topic: "Drug Network Monitoring — South India"
Keywords: "stuff available", "delivery", "420", "green"

Sources (4):
  - telegram: "Stuff BLR", "420 Club India", "Green Life Bangalore"
  - darkweb: india-market.onion (simulated as web source for demo)

Content items (12+):
  - 6 drug sale messages across 3 Telegram channels
    Contains: phone (+91-9753186420 in 3 channels → cluster)
    Contains: UPI (dealer420@paytm in 2 channels)
    Contains: Telegram handle (@stuff_blr admin of 3 channels)
    Contains: crypto wallet (bc1qr8fake...m4n in 2 channels)
    Keywords + emoji: "stuff available 🍃", "delivery Bangalore 🔥", "DM for menu"
  - 3 dark web drug listings
    Contains: BTC wallet (same bc1qr8fake...m4n → links TG to dark web)
    Keywords: "India shipping", "quality guaranteed", "escrow accepted"
  - 3 mule recruitment messages (shared infrastructure with cyber fraud)
    Keywords: "bank account needed", "commission", "easy money"
    Contains: different phone (+91-8642097531)

Expected after pipeline:
  - ≥ 2 identifier clusters (dealer phone + BTC wallet)
  - ≥ 1 identifier_convergence signal (phone in 3 channels)
  - ≥ 1 scam_template_match signal (drug_sale HIGH)
  - content_items.labels.scam_template = "drug_sale" on 6+ items
  - content_items.labels.scam_template = "mule_recruitment" on 3 items
  - Extracted identifiers: PHONE_IN, UPI, TELEGRAM_HANDLE, CRYPTO_BTC
  - BTC wallet links Telegram channels to dark web listing (same identifier)

Templates active: drug_sale, drug_delivery_recruitment, mule_recruitment, crypto_cashout
```

#### Cross-Org Isolation Verification

After all 4 orgs seeded:
- Login as demo_mea@anveshak.local → can ONLY see MEA topic, sources, content, signals
- Login as demo_cyber@anveshak.local → can ONLY see Cyber Fraud topic
- Login as demo_sebi@anveshak.local → can ONLY see SEBI topic
- Login as demo_ncb@anveshak.local → can ONLY see NCB topic
- Login as superadmin → can see all 4 orgs
- GET /api/v1/identifiers/search with org_cyber creds → returns ONLY cyber fraud identifiers
- GET /api/v1/identifiers/search with org_ncb creds → returns ONLY NCB identifiers
- Same phone number in cyber and NCB topics → NOT cross-visible (org-isolated)

#### Session 13 Workflow

| Day | Task | Workflow |
|-----|------|---------|
| 1 | **Create seed SQL:** `scripts/seed_demo_engine_c.sql` with 4 orgs, 4 users, 4 topics, ~57 content items, sources, topic_sources, org_sources, topic_templates associations. All INSERTs include org_id. All sources linked via org_sources and topic_sources. | Follow existing `seed_demo_full.sql` patterns. Use ON CONFLICT DO NOTHING for idempotency. Verify org_id on all root tables per multi-tenancy rules. |
| 2 | **Run seed + pipeline:** `make seed-demo-ec` → wait for analyst pipeline to process all items → verify identifiers extracted, templates matched, clusters formed, signals fired. | If pipeline doesn't auto-process seeded items, manually enqueue `analyse_content` for each. Verify with SQL queries before running demo-check. |
| 3 | **Run `/demo-check`:** All 50 steps. Fix any failures. | Target: Part A (9/9), Part B (17/17), Part C (21/21 — no SKIPs), Part D (3/3). Verdict: GO. |
| 4 | **Write demo scripts:** One doc per agency — what to click, what appears, talking points. | Save to `docs/demo_script_mea.md`, `docs/demo_script_cyber.md`, `docs/demo_script_sebi.md`, `docs/demo_script_ncb.md`. |

**Session 13 exit gate — FINAL ENGINE C GATE:**
```
ALL of the following must pass:

  [ ] make test-unit         — all unit tests pass
  [ ] make test-integration  — all integration tests pass
  [ ] make test-e2e          — 4 agency E2E scenarios pass
  [ ] make test-smoke        — /health/ready 200, all endpoints reachable
  [ ] make test-contract     — all service seam agreements hold
  [ ] make test-resilience   — all degradation scenarios handled
  [ ] make test-migration    — all tables, indexes, constraints, seeds present
  [ ] npm run build          — 0 TypeScript errors
  [ ] npm run test           — all frontend tests pass

Coverage:
  [ ] Coverage ≥ 80% on all new Engine C modules

Regression:
  [ ] ALL existing tests (267+) still pass

Demo:
  [ ] 4 orgs created (org_mea, org_cyber, org_sebi, org_ncb)
  [ ] 4 users created (one per org, analyst role)
  [ ] 4 demo topics seeded with realistic content
  [ ] Cross-org isolation verified (no data leakage between orgs)
  [ ] /demo-check verdict = GO (50/50 steps pass, 0 SKIP, 0 FAIL)
  [ ] 4 demo scripts written

System health:
  [ ] make ps → all containers healthy
  [ ] Grafana dashboards load (check identifier metrics visible)
```

---

## Test Count Estimate (All 9 Types)

| Type | Phase EC-1 | Phase EC-2 | Phase EC-3 | Phase EC-4 | Total |
|------|-----------|-----------|-----------|-----------|-------|
| 1. Unit | ~60 | ~20 | ~15 | ~10 | **~105** |
| 2. Integration | 5 | 8 | 5 | 6 | **~24** |
| 3. E2E | — | — | — | 4 | **4** |
| 4. Smoke | 2 | 1 | 2 | 1 | **6** |
| 5. Contract | 2 | 4 | 3 | 1 | **~10** |
| 6. Resilience | — | — | 3 | 5 | **8** |
| 7. Regression | 3 | 2 | 1 | 5 | **~11** |
| 8. Migration | 5 | — | — | 1 | **6** |
| 9. Connectivity | — | — | 1 (manual) | — | **1** |
| **Phase total** | **~77** | **~35** | **~30** | **~33** | **~175** |

Added to existing 267 → **~442 total tests.**

---

## Makefile Targets (New)

```makefile
# Run specific Engine C test categories
test-identifiers:    pytest tests/unit/test_identifier_*.py -v
test-templates:      pytest tests/unit/test_template_*.py -v
test-id-clustering:  pytest tests/unit/test_identifier_cluster*.py -v
test-id-signals:     pytest tests/unit/test_signal_identifier*.py -v
test-id-api:         pytest tests/integration/test_identifier_api*.py -v
test-instagram:      pytest tests/unit/test_instagram_*.py -v
test-tipline:        pytest tests/integration/test_tipline*.py -v
test-ec-e2e:         pytest tests/e2e/test_engine_c_*.py -v

# Full Engine C test suite
test-engine-c:       make test-identifiers test-templates test-id-clustering \
                     test-id-signals test-id-api test-instagram test-tipline

# Gate check (run before moving to next phase)
test-ec-gate:        make test-unit test-integration test-contract \
                     test-smoke test-migration
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Instagram API breaks (Meta changes) | Instagram adapter goes down | Circuit breaker auto-disables. Other adapters unaffected. Instagram is enhancement, not core. |
| High false positive rate on phone extraction | Analyst overwhelmed with noise | Context validation in Step 1. Threshold tuning. Analyst dismiss feedback collected for Phase 2 ML. |
| Template keyword matching too rigid | Misses paraphrased fraud messages | Embedding similarity provides fallback. Reference embeddings catch semantic matches keywords miss. |
| Identifier clustering performance at scale | Slow with 100K+ identifiers | PostgreSQL UNIQUE index on (topic, type, value) ensures O(1) lookup. Cluster update is single UPDATE. |
| Migration breaks existing data | Existing functionality regressed | Migration is additive (new tables + optional column). No existing columns modified. All 267 existing tests must pass. |
| Existing pipeline slows down | analyse_content job takes longer | Identifier extraction is regex (< 1ms). Template matching is keyword + embedding (< 5ms). Clustering is 1 SQL query. Total: < 10ms overhead per item. |

---

## Definition of Done (Engine C Complete)

### Functionality
```
[ ] 15 identifier types extracted with normalization and context validation
[ ] 11 built-in scam templates matching with confidence scores
[ ] Custom template CRUD API with org isolation
[ ] Identifier clustering groups content by shared identifiers
[ ] 2 new signal types firing through existing WebSocket delivery
[ ] Instagram adapter passing SourceAdapterConformanceSuite with circuit breaker
[ ] Tip-line inbound webhook accepting and processing forwarded content
[ ] 6 identifier search/browse API endpoints with partial match
[ ] Frontend identifier dashboard with table, detail, export
[ ] Reports include identifier section, clusters, template matches, legal mapping
[ ] 4 demo scenarios working end-to-end (MEA, Police, SEBI, NCB)
```

### Testing (All 9 Types Pass)
```
[ ] Unit (~105 new)           — make test-unit passes
[ ] Integration (~24 new)     — make test-integration passes
[ ] E2E (4 new)               — make test-e2e passes (4 agency scenarios)
[ ] Smoke (6 new)             — make test-smoke passes
[ ] Contract (~10 new)        — make test-contract passes
[ ] Resilience (8 new)        — make test-resilience passes
[ ] Regression (~11 new)      — all regression tests pass (no existing behavior changed)
[ ] Migration (6 new)         — make test-migration passes
[ ] Connectivity (1 manual)   — Instagram login verified manually
[ ] ~175 new tests total, all passing
[ ] ~442 total tests (267 existing + 175 new), all passing
[ ] Coverage ≥ 80% on all new Engine C modules
```

### Quality
```
[ ] /code-review passed on every new module — 0 FAIL issues remaining
[ ] /tdd workflow followed for every step — tests written before code
[ ] npm run build → 0 TypeScript errors
[ ] No regression on existing functionality
```

### Demo Readiness (Phase EC-5)
```
[ ] 4 orgs created (org_mea, org_cyber, org_sebi, org_ncb) — fully isolated
[ ] 4 users created (demo_mea, demo_cyber, demo_sebi, demo_ncb) — one per org
[ ] 4 demo topics seeded with ~57 content items exercising Engine C
[ ] Cross-org isolation verified — no data leakage between agency orgs
[ ] /demo-check verdict = GO (50/50 steps, 0 SKIP, 0 FAIL)
[ ] 4 demo scripts written (docs/demo_script_{mea,cyber,sebi,ncb}.md)
[ ] make ps → all containers healthy
```
