# ANVESHAK ARCHITECTURAL AUDIT — 18 July 2026
Commit: `ab6b041` · Schema source: migrations only (DB not live)

Charter: GARUD ARCHITECTURAL CHARTER v1.0 — 5 invariants for horizontal-infrastructure sovereignty.

---

## VERDICT

| Test | Result | Summary |
|------|--------|---------|
| Test 1 — Entity model | **PASS** | Single `extracted_entities` table, `entity_type TEXT` (not enum), 23 identifier types, zero per-domain entity tables |
| Test 2 — Adapters | **PARTIAL PASS** | Clean `SourceAdapterBase` interface, canonical `RawItem` emit, BUT platform strings leak into 3 core modules + normalisation duplicated |
| Test 3 — Provenance | **PARTIAL PASS** | `content_hash` SHA-256 at ingest, `credibility_score_at_capture` frozen, report immutability enforced, BUT algorithm versions not recorded on derived records |
| Test 4 — Violation mapping | **FAIL** | Statutes hardcoded in 2+ modules, no versioning, no `effective_from`, reports don't record mapping version |
| Test 5 — Confidence | **FAIL** | Two competing scales (0–100 vs 0–1), no central scoring module, vocabulary drift (HIGH/high/High), hardcoded thresholds, zero explainability |

**Cost to add one new domain today: connector + config migration** (not rewrite, but statute mapping and confidence normalization need work first)

---

## FINDINGS

### F-01 · S1 · Statutes hardcoded in code, unversioned

**Invariant:** Test 4 — Violation mapping as configuration
**Evidence:**
- `services/analyst/anveshak/analyst/templates.py:160–316` — 11 templates with `legal_sections` (NDPS 20/22/25, IPC 420, PMLA 3/4, BNS 318/319, IT Act 66C/66D)
- `services/reporter/anveshak/reporter/rag.py:160–217` — `_TEMPLATE_ACTIONS` dict: 11 templates → 33 legal directives hardcoded
- `services/reporter/anveshak/reporter/prompt_templates.py:79–99` — 29 statutory provisions in Jinja template
- `reports` table has no `violation_map_version` or `legal_mapping_version` column
- No `effective_from` date on any statute reference

**What it means:** BNS replaced IPC in July 2024. If section numbers change, every report generated between amendment and code deploy cites wrong law. Historical reports can't distinguish which mapping version produced them.
**Remediation:**
1. Extract statutes to `config/violation_map/` YAML files with `effective_from` + schema validation
2. Add `legal_mapping_version TEXT` to `reports` table (nullable for backcompat, stamped at gen time)
3. Add build-time test: zero statute strings in `.py`/`.ts` files outside config/
**Migration risk:** Zero downtime. Additive column. Backfill historical reports with `"pre-versioning"`.
**Effort:** M

---

### F-02 · S1 · Derived records lack algorithm version

**Invariant:** Test 3 — Provenance
**Evidence:**
- `001_initial_schema.py:188` — `narrative_clusters` has `label_generated_at` but no `clustering_algorithm`, `leiden_threshold`, `embedding_model_name`
- `001_initial_schema.py:389` — `vision_results` has `deepfake_model` but no `yolo_model`, `clip_model` columns
- No `embedding_model_version` on `content_items` or `topics`

**What it means:** Re-running clustering with different params produces different results. Without recorded params, earlier conclusions are unreproducible. Undermines evidence chain for any derived intelligence.
**Remediation:**
1. Add `algorithm_version JSONB` to `narrative_clusters` and `vision_results` (stores model name, version, threshold)
2. Populate at derivation time from `settings.*` values
3. Add `embedding_model TEXT` to `content_items` (set at embed time)
**Migration risk:** Zero downtime. Nullable additive columns. Historical rows get `NULL` (explicitly: "version unknown").
**Effort:** S

---

### F-03 · S2 · Two competing score scales (0–100 vs 0–1)

**Invariant:** Test 5 — Uniform confidence
**Evidence:**
- `sdk/anveshak/models/source.py:14` — `credibility_score: float = 50.0` (0–100)
- `services/vision/anveshak/vision/detectors/base.py:41` — `score() -> float` (0–1)
- `services/analyst/anveshak/analyst/identifiers.py:338` — confidence 0.95/0.85/0.6 (0–1)
- `services/reporter/anveshak/reporter/llm.py:78` — `confidence_level: float` (0–1)
- `frontend/src/lib/domain.ts:44` — `credibilityLabel()` expects 0–100
- `frontend/src/lib/domain.ts:30` — `confidenceVariant()` expects 0–1

**What it means:** Field commander sees "credibility 70" and "confidence 0.7" — same number, different meanings. Comparisons across modules require mental conversion. Demo credibility undermined.
**Remediation:**
1. Document canonical scale: 0–1.0 for all ML/algorithmic scores, 0–100 for human-facing credibility only
2. Add `sdk/anveshak/scoring.py` with conversion utilities + verbal anchors
3. Frontend normalizes at display layer, not in domain logic
**Migration risk:** Low. Credibility 0–100 is established; changing it touches too many surfaces. Better to document the split and enforce consistency within each scale.
**Effort:** M

---

### F-04 · S3 · Platform strings leak into core modules

**Invariant:** Test 2 — Adapters
**Evidence:**
- `services/api/anveshak/api/routes/sources.py:111–240` — `if req.platform == "rss"` / `"web"` / `"darkweb"` — 6 branches for health probing
- `services/analyst/anveshak/analyst/identifiers.py:376–380` — `if platform_lower == "instagram"` / `"telegram"` — confidence boosting per platform
- `services/social/anveshak/social/jobs.py:161,268` — `if adapter.platform == "instagram"` / `"twitter"` — circuit breaker + poll interval tuning

**What it means:** Adding a new platform (e.g., Signal, Discord) requires editing core modules, not just adding an adapter. Charter says core diff should be zero for new source.
**Remediation:**
1. Health probe strategy → adapter method `probe() -> HealthResult` (each adapter knows how to probe itself)
2. Confidence boost → config table `platform_confidence_modifiers` or adapter property
3. Circuit breaker tuning → adapter-level config properties
**Migration risk:** None. Refactor only. No schema change.
**Effort:** M

---

### F-05 · S3 · Normalisation duplicated between scraper and social

**Invariant:** Test 2 — Adapters
**Evidence:**
- `services/scraper/anveshak/scraper/normalise.py:9` — `normalise_text()` + `compute_content_hash()`
- `services/social/anveshak/social/ingest.py:73–80` — `_normalise()` + `_compute_hash()` — identical logic, separate copy

**What it means:** Same phone number entering via RSS vs Telegram could normalize differently if copies diverge. Identifier resolution breaks silently.
**Remediation:** Move to SDK (`sdk/anveshak/normalise.py`). Both services import from shared module.
**Migration risk:** Zero. Pure refactor, no schema change.
**Effort:** S

---

### F-06 · S4 · Vocabulary drift in severity/risk labels

**Invariant:** Test 5 — Confidence
**Evidence:**
- `services/api/anveshak/api/signal_delivery.py:58` — `"HIGH"` / `"MEDIUM"` (uppercase)
- `services/api/anveshak/api/db/topics.py:556` — `"high"` / `"medium"` / `"low"` (lowercase)
- `sdk/anveshak/models/catalog.py:25` — `risk_level: str = "low"` (lowercase default)
- `sdk/anveshak/models/tracker.py:26` — `priority: Literal["low", "medium", "high", "critical"]` (lowercase)
- `services/reporter/anveshak/reporter/llm.py:55` — `risk_level: str # LOW | MEDIUM | HIGH | CRITICAL` (uppercase)
- `frontend/src/lib/domain.ts:13` — `inferSeverity()` returns `'HIGH'` (uppercase)

**What it means:** Frontend does case-insensitive compare or breaks. Three people reading same report see different grammar. Undermines the "one confidence language" invariant.
**Remediation:** Pick one casing (UPPERCASE for severity/risk, as used in signals). Add `Literal["LOW","MEDIUM","HIGH","CRITICAL"]` to SDK models. Frontend normalizes at boundary.
**Effort:** S

---

### F-07 · S4 · Hardcoded thresholds outside config

**Invariant:** Test 5 — Confidence
**Evidence:**
- `services/analyst/anveshak/analyst/templates.py:15` — `_CONFIDENCE_THRESHOLD = 0.5`
- `services/analyst/anveshak/analyst/identifiers.py:338–342` — confidence 0.95/0.85/0.6
- `services/api/anveshak/api/routes/intelligence.py:299–397` — `ee.confidence >= 0.8` in 6 routes
- `services/api/anveshak/api/db/topics.py:555–559` — thresholds 0.45/0.30 in SQL

**What it means:** Tuning requires code deploy. Analyst can't adjust sensitivity per deployment. Different deployments forced to same thresholds.
**Remediation:** Move all to `settings.py` with env var overrides. Add invariant test asserting no numeric threshold literals in service code.
**Effort:** S

---

### F-08 · S4 · Scores carry no contributing factors

**Invariant:** Test 5 — Confidence
**Evidence:**
- `services/analyst/anveshak/analyst/templates.py:113–121` — `confidence = max(kw_score, emb_score)` — formula result stored, components lost
- `services/vision/anveshak/vision/detectors/base.py:41–50` — returns scalar float, no breakdown
- `services/reporter/anveshak/reporter/llm.py:78` — `confidence_level: float` with no explanation

**What it means:** "Why 0.7?" is unanswerable. In demo or courtroom, unexplainable score = untrusted score. Charter requires contributing factors alongside every score.
**Remediation:** Add optional `score_components: dict` to scoring models. Vision: `{"face_count": 3, "max_face_score": 0.92}`. Templates: `{"keyword_score": 0.6, "embedding_score": 0.7}`.
**Effort:** M

---

## QUICK WINS (S1/S2 with S-effort)

| # | Finding | Severity | Effort | Action |
|---|---------|----------|--------|--------|
| 1 | F-02: Algorithm version columns | S1 | S | Add `algorithm_version JSONB` to `narrative_clusters` + `vision_results` |
| 2 | F-05: Normalisation dedup | S3 | S | Move to SDK shared module |
| 3 | F-06: Vocabulary drift | S4 | S | Standardize on UPPERCASE Literals in SDK |
| 4 | F-07: Hardcoded thresholds | S4 | S | Move to settings.py |

## DEFERRED

| # | Finding | Rationale |
|---|---------|-----------|
| F-03 | Two score scales | Credibility 0–100 deeply embedded, changing it is high-risk for marginal gain. Document the split, enforce within each scale. |
| F-08 | Score components | Valuable but not blocking any domain expansion. Add incrementally per module. |

---

## WHAT PASSES CLEANLY

**Test 1** is the strongest result. Single `extracted_entities` table with `entity_type TEXT` (not enum), 23 identifier types registered dynamically, zero per-domain entity tables, `identifier_clusters` for aggregation. Domain vocabulary lives in `scam_templates` (config data), not schema. Entity model is genuinely horizontal.

**Test 3** is mostly solid. `content_hash` SHA-256 at ingest, `credibility_score_at_capture` frozen at collection, report immutability enforced with `WHERE generated_at IS NULL` sentinel, `credibility_audit_log` tracks every score change. The gap is algorithm versioning on derived records (F-02).

**Test 2** adapter interface (`SourceAdapterBase` → `RawItem`) is clean. 7 social adapters + web/RSS all emit canonical records. Registration via config dict. The leaks (F-04, F-05) are containable.

---

## FIX ORDER

1. **F-01 + F-02** (S1) — statute versioning + algorithm version columns. Both irreversible data quality issues.
2. **F-05** (S3, S-effort) — normalisation dedup. Cheapest coupling fix.
3. **F-06 + F-07** (S4, S-effort) — vocabulary + thresholds. Consistency wins before next demo.
4. **F-04** (S3, M-effort) — platform string cleanup. Fold into normal release work.
5. **F-03 + F-08** (S2/S4, M-effort) — score scale documentation + explainability. Deferred until post-demo cycle.
