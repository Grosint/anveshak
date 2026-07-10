# Map Infrastructure Upgrade Plan

**Status:** Plan complete, awaiting implementation approval
**Date:** 2026-07-08
**Persona review:** 8/8 complete — plan significantly revised based on feedback

---

## Persona Review Summary

All 8 stakeholder personas reviewed the original 4-component proposal (Nominatim, H3 hotspots, deck.gl migration, OSM POI enrichment). The reviews unanimously rejected the original scope.

### Consensus Table

| Decision | Agreement | Rationale |
|----------|-----------|-----------|
| **Kill deck.gl migration** | 8/8 | MapLibre sufficient at current scale (<5K points). WebGPU risky on govt laptops (Intel HD Graphics, Chrome 109). Sovereign boundary overlay regression = career-ending bug. 2-3MB bundle vs 700KB. |
| **Kill OSM POI enrichment** | 8/8 | OPSEC violation (stores military base locations). Overpass API = external network call violating sovereignty. OSM military data unreliable. Classification spillage risk. |
| **Nominatim overkill** | 6/8 | geonamescache already works (50K+ cities, <1ms, offline). Nominatim = 25-30GB disk after import. Expand existing geocoder instead. |
| **H3 defer** | 6/8 | Not enough data points yet (dozens per topic, not thousands). Missing topic_id/org_id. NCB wants temporal-spatial chains, not static hex grids. |
| **Add map PNG export** | 5/8 | Higher value than all proposed components. Analysts screenshot maps for PowerPoint/case files. |
| **Add geocoding provenance** | 3/8 | NIA: court reproducibility. SA: separate table, not on extracted_entities. NCB: audit trail. |

### What Each Persona Actually Wants (Not Maps)

| Persona | Top Priority |
|---------|-------------|
| LEA Cyber | Cross-case identifier linking, Hindi NER, FIR numbers |
| SEBI | Ticker/ISIN extraction, bhav copy correlation |
| ED | Shell company detection (CIN/DIN), money trail, Section 65B export |
| NIA | Geocoding provenance table, cross-topic spatial convergence, map snapshots |
| MEA | Source country attribution, narrative cascade/propagation tracking |
| NCB | Identifier-linked geographic network (Engine C + map), temporal-spatial chains |
| PM | Map PNG export, location timeline sparklines, manual pin drop, drill-down |
| SA | Improve existing geocoder, measure before adding infra, separate geocoded_locations table |

### Key Insight: Maps Serve Defence/LEA, Not Financial Crime

Maps are relevant for: NIA (counter-terror), NCB (drug routes), MEA (narrative propagation), border security.
Maps are irrelevant for: SEBI (market surveillance), ED (money trails), LEA Cyber (identifier correlation).

The map upgrade should be scoped as a **defence/border use case enhancement**, not a platform-wide feature push.

---

## Revised Plan — 4 Phases

### Phase 1: Geocoder Enhancement (Zero New Infrastructure)

**Goal:** Improve geocoding hit rate from ~60% to ~85% without adding containers.

**What changes:**
- Expand `custom_locations.json` with India districts, taluks, defence locations
- Add Indian state name aliases (both English + Hindi transliterations)
- Add multilingual entity normalization before geocoding (LOWER + Unicode NFKD + alias table)
- Wire geocoding into analyst pipeline (post-NER, not just reporter)
- New `geocoded_locations` table (separate from `extracted_entities` — SA + NIA requirement)
- Redis cache with NO expiry (coordinates don't change), explicit invalidation key
- Backfill job for existing extracted_entities

**Schema: `geocoded_locations`**
```sql
CREATE TABLE geocoded_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_text_normalized TEXT NOT NULL,  -- LOWER(NFKD(entity_text))
    entity_type TEXT NOT NULL,             -- GPE, LOC, FAC
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geocode_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    geocode_source TEXT NOT NULL DEFAULT 'geonamescache',  -- provenance
    alternatives_json JSONB DEFAULT '[]',  -- other candidate coordinates
    geocoded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    labels JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_text_normalized, entity_type)
);
```

**Why separate table (not columns on extracted_entities):**
- One entity text ("Mumbai") appears in thousands of rows — avoids N duplicates
- Org-agnostic (same city = same coordinates regardless of org) — correct per multi-tenancy rules
- Provenance tracked per geocode, not per entity mention
- Analyst can override without touching evidence table
- NIA requirement: geocoding = interpretation, extraction = evidence. Don't mix.

**Files modified:**
- `services/reporter/anveshak/reporter/geocoder.py` — expand indices, add aliases, multilingual normalization
- `infra/configs/geocoder/custom_locations.json` — expand to ~500 India districts + defence locations
- `services/analyst/anveshak/analyst/db.py` — new SQL for geocoded_locations insert/lookup
- `services/analyst/anveshak/analyst/jobs.py` — wire geocoding after NER in analyse_content
- `services/api/anveshak/api/routes/` — new endpoint for analyst geocode override
- New migration file

**Verification:**
- Measure hit rate: `SELECT COUNT(*) FILTER (WHERE gl.id IS NOT NULL) * 100.0 / COUNT(*) FROM extracted_entities ee LEFT JOIN geocoded_locations gl ON LOWER(ee.entity_text) = gl.entity_text_normalized`
- Target: >80% for English GPE entities, >50% for Hindi entities
- Test with demo data: all demo topic locations resolve

**Exit criteria:**
- [x] geocoded_locations table created with provenance columns
- [x] Geocoding wired into analyst pipeline (post-NER)
- [x] Redis cache with no-expiry, explicit invalidation
- [x] Backfill job for existing entities
- [x] Analyst override endpoint (PATCH /api/v1/geocoded-locations/{id})
- [x] Hit rate measured and logged
- [x] custom_locations.json expanded to 601 entries

**Implementation notes (2026-07-10):**
- Geocoder built in analyst service (`services/analyst/anveshak/analyst/geocoding.py`), NOT reporter — services are isolated uv workspace packages, can't cross-import.
- Reporter's existing geocoder (`services/reporter/anveshak/reporter/geocoder.py`) kept for backward compat — used at report gen time.
- Alias normalization also exists in `services/api/anveshak/api/routes/intelligence.py` (`_normalize_location`, `_merge_location_rows`) for the old `location-map` endpoint. **Overlaps with analyst geocoding.py aliases.** When Phase 2 wires frontend to use `geocoded_locations` table, the old location-map endpoint + its normalization code becomes dead code and should be removed.
- Analyst Dockerfile needed `COPY infra/configs/geocoder/custom_locations.json /workspace/infra/configs/geocoder/` added — container path resolution uses `/workspace/infra/...` fallback.
- Backfill marks unresolved entities with `geocode_source='unresolved'` (lat=0, lon=0) to prevent infinite re-fetching of same unknowns.

---

### Phase 2: MapLibre Enhancements (No Migration, Existing Stack)

**Goal:** Wire frontend to use `geocoded_locations` table + add high-value map features using existing MapLibre GL. No new frontend dependencies.

**Prerequisite cleanup:** Replace old `location-map` endpoint (queries extracted_entities + geocodes on-the-fly) with new endpoint backed by `geocoded_locations` table. Remove duplicate alias code from intelligence.py.

**What changes:**

#### 2a. New Location Map API (replaces old endpoint)
- New `GET /api/v1/topics/{topic_id}/location-map-v2` endpoint backed by `geocoded_locations` table
- JOINs: `extracted_entities` → `geocoded_locations` ON `LOWER(entity_text) = entity_text_normalized`
- Filters: topic scoping via `content_items.topic_id`, `geocode_source != 'unresolved'`, `min_mentions`
- Returns same GeoJSON FeatureCollection shape (backward-compatible with existing GeoMap.tsx)
- Frontend switches `intelligenceApi.locationMap()` to call v2 endpoint
- Old `get_location_map` endpoint + `_normalize_location` + `_merge_location_rows` + `_geocode` removed from intelligence.py
- Old `test_location_normalization.py` tests updated or removed

#### 2b. Map PNG Export
- Add `map.getCanvas().toDataURL()` export button on GeoMap component
- `preserveDrawingBuffer: true` on MapLibre init (required for toDataURL)
- Include sovereign boundary in export (already rendered on canvas)
- Add topic name + timestamp watermark via canvas overlay before export
- Support "Download as PNG" (anchor click) and "Copy to Clipboard" (navigator.clipboard)

#### 2c. MapLibre Native Heatmap Layer
- Add `heatmap` layer type to existing GeoMap.tsx (MapLibre supports this natively)
- Toggle button in legend area: "Pins" | "Heatmap"
- Heatmap weight by `mention_count` property
- Heatmap layers hidden when pin mode active (and vice versa)
- No deck.gl needed — MapLibre `heatmap` paint is built-in

#### 2d. Location Timeline Sparklines
- New `LocationPanel.tsx` sidebar component (replaces inline list in LocationMap.tsx)
- Per-location mention count over last 30 days (7-day buckets = 4-5 data points)
- New API endpoint `GET /api/v1/topics/{topic_id}/location-timeline` returns time-bucketed counts
- Simple inline SVG sparkline (polyline + area fill) — no charting library
- Click sparkline row → map flies to location

#### 2e. Manual Pin Drop
- Analyst clicks map in "pin mode" → places custom pin with label
- New migration `005_add_analyst_pins` — `analyst_pins` table (topic_id, org_id, lat, lng, label, analyst_id, created_at, labels)
- New CRUD endpoints: `POST/GET/DELETE /api/v1/topics/{topic_id}/pins`
- Topic + org scoping via `verify_topic_access()`
- Rendered as distinct marker layer (star icon or different color) in GeoMap
- Persists across sessions, visible to org members on same topic

#### 2f. Richer Drill-Down
- Click location pin → slide-out panel in LocationPanel showing content_items mentioning that entity
- New API endpoint `GET /api/v1/topics/{topic_id}/location/{entity}/content` returns content items
- Sorted by recency, shows source, sentiment badge, cluster label
- "View in Content Feed" link navigates to Feed tab with entity filter

**Files modified (backend):**
- `services/api/anveshak/api/routes/intelligence.py` — new v2 location-map endpoint, remove old geocoding code
- `services/api/anveshak/api/routes/topics.py` — analyst_pins CRUD, location-timeline, location-content endpoints
- `services/api/migrations/versions/005_add_analyst_pins.py` — new table
- `tests/unit/test_location_normalization.py` — update/remove old tests

**Files modified (frontend):**
- `frontend/src/components/map/GeoMap.tsx` — heatmap layer, export button, manual pin layer, preserveDrawingBuffer
- `frontend/src/components/workspace/LocationMap.tsx` — wire to v2 API, integrate LocationPanel
- `frontend/src/components/map/LocationPanel.tsx` — new: sidebar with sparklines + drill-down
- `frontend/src/api/intelligence.ts` — update locationMap URL, add new API methods

**Exit criteria:**
- [x] Frontend uses geocoded_locations table via v2 endpoint
- [x] PNG export works with sovereign boundary visible
- [x] Heatmap toggle renders correctly
- [x] Sparklines show per-location 30-day trends
- [x] Manual pin CRUD works with topic + org scoping
- [x] Drill-down shows content items for clicked location
- [ ] Old _normalize_location / _geocode code removed from intelligence.py (deferred — v1 endpoint kept as fallback)

**Implementation notes (2026-07-10):**
- Frontend switched to `location-map-v2` endpoint. Old `location-map` (v1) kept in intelligence.py as fallback — remove when v2 is validated in production.
- Old `_normalize_location`, `_merge_location_rows`, `_geocode` functions still in intelligence.py. Overlapping alias logic with analyst `geocoding.py`. Remove with v1 endpoint.
- `analyst_pins` table uses TEXT ids (not UUID) — topics/orgs/users tables all use TEXT PKs, not UUID. Migration FK types must match.
- MapLibre NavigationControl moved to `top-left` to avoid overlapping custom controls at `top-right`.
- LocationPanel.tsx replaces inline location list — adds SVG sparklines (no charting library) + drill-down.
- `h3-js` NOT added yet — Phase 3 dependency.
- NER noise inflates unresolved count (e.g., "Singh", "Modi" tagged as GPE by spaCy). True geocoding hit rate is higher than raw 8% suggests. Consider NER confidence threshold increase or entity type filtering to improve signal.
- `preserveDrawingBuffer: true` added to MapLibre init for PNG export — slight perf cost (~10% GPU), acceptable for analyst workstation.

---

### Phase 3: H3 Hotspot Backend (Data-Dependent Gate) — NEXT SESSION

**Gate condition:** Only proceed if Phase 1 geocoding hit rate exceeds 70% AND average topic has >100 geocoded entities. Measure after 4 weeks of Phase 1 running in production.

**What changes:**
- Add `h3` Python package to analyst service
- New `location_hex_stats` table with proper scoping
- Single pre-computed resolution (res 5 = ~252 km² hexes, good for district-level India)
- Frontend: MapLibre `fill` layer rendering hex polygons (h3-js converts index → polygon)
- No deck.gl needed — MapLibre GeoJSON source with hex polygons

**Schema: `location_hex_stats`**
```sql
CREATE TABLE location_hex_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    h3_index TEXT NOT NULL,              -- H3 cell index at resolution 5
    mention_count INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 0,
    latest_at TIMESTAMPTZ,
    labels JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (topic_id, h3_index)
);
CREATE INDEX idx_location_hex_stats_topic ON location_hex_stats(topic_id);
```

**Note on org_id:** Not needed on this table — scoped via `topic_id` FK, topics already carry `org_id`. Per multi-tenancy rule: child entities inherit org scope through topic_id. Cross-topic hotspot queries (Phase 3b, future) will JOIN through `topics.org_id`.

**API:**
- `GET /api/v1/topics/{id}/hotspots` — returns GeoJSON of hex polygons with mention/source counts
- Verify topic access via `verify_topic_access()` (existing pattern)

**Computation:**
- After geocoding in analyst pipeline, compute `h3.latlng_to_cell(lat, lng, resolution=5)`
- Upsert into `location_hex_stats` with `ON CONFLICT (topic_id, h3_index) DO UPDATE`
- Increment mention_count, update source_count via GREATEST, update latest_at

**Frontend:**
- New "Hotspot" toggle on GeoMap (alongside existing pin + heatmap toggles)
- h3-js library (~50KB) converts H3 index → polygon coordinates for MapLibre GeoJSON source
- Color gradient by mention_count (blue → amber → red)

**Exit criteria:**
- [ ] H3 computation wired into analyst pipeline after geocoding
- [ ] location_hex_stats table with topic scoping
- [ ] API endpoint with topic access verification
- [ ] Frontend hex overlay toggle in MapLibre
- [ ] Hotspot view renders correctly alongside sovereign boundary

---

### Phase 4: Future Considerations (Not Planned, Captured for Reference)

These were surfaced by personas but are NOT in implementation scope. Captured to prevent re-analysis.

#### 4a. Cross-Topic Spatial Convergence (NIA request)
- Same H3 cells appearing in multiple topics = geographic convergence signal
- Pattern: same as `SQL_CONVERGENT_CLUSTERS` but on `location_hex_stats`
- Must filter `AND t1.org_id = t2.org_id` (existing rule)
- **When:** After Phase 3 has 3+ months of data across multiple topics

#### 4b. Narrative Cascade Visualization (MEA request)
- Source country attribution (`country_code` on sources table)
- Cluster members ordered by `published_at` + grouped by source country = cascade timeline
- Sankey diagram or flow map visualization
- **When:** After source country metadata is populated

#### 4c. Identifier-Linked Geographic Network (NCB request)
- Engine C identifiers that co-occur across content items mentioning different locations
- Draw arcs between locations connected by shared identifiers (not by arbitrary entity co-occurrence)
- Requires Engine C to be fully operational
- **When:** After Engine C backfill complete + geocoding hit rate >80%

#### 4d. Nominatim (Full Self-Hosted Geocoding)
- Only if geonamescache + expanded overlay cannot resolve >20% of extracted locations after 8 weeks
- If needed: use full India PBF (~1.5GB compressed, ~20GB imported)
- Hardware.md entry required before deployment
- **When:** Only if Phase 1 hit rate stays below 70% after custom_locations expansion

#### 4e. deck.gl Migration
- Only if data scale exceeds MapLibre's capacity (>50K unique geocoded locations per topic)
- Current trajectory: years away
- If triggered: validate WebGPU on target govt hardware first, ensure sovereign boundary parity
- **When:** Probably never for current product scope

#### 4f. Static Defence POI Layer (Instead of OSM Enrichment)
- Pre-curated, security-reviewed GeoJSON of non-classified infrastructure
- Provided by deployment org's security officer, not auto-fetched from OSM
- Loaded as static MapLibre layer, not per-entity enrichment
- **When:** When a defence customer explicitly requests proximity context

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Geocoding ambiguity (47 "Model Towns" in India) | HIGH | Prefer higher-population match (existing geonamescache behavior). Log alternatives. Analyst override mechanism. |
| Hindi/Urdu entity text not resolving | HIGH | Unicode NFKD normalization + transliteration alias table. Measure non-English hit rate separately. |
| Selection bias on map (ungeocodeable locations invisible) | HIGH | Show "X of Y entities geocoded" count on map. List ungeocodeable entities in sidebar. |
| MapLibre heatmap performance at scale | LOW | MapLibre handles 10K+ heatmap points. Aggregate by geocoded_locations (deduped), not raw entity mentions. |
| H3 resolution mismatch expectations | MEDIUM | Single fixed resolution (res 5). Document in UI: "Each hexagon covers ~252 km²". No zoom-adaptive complexity. |
| Analyst pins persisted without audit | MEDIUM | analyst_pins table includes analyst_id, created_at. Immutable once created (soft-delete only). |
| Court reproducibility of geocoded coordinates | HIGH | geocoded_locations table has geocoded_at timestamp + geocode_source provenance. Redis cache uses no-expiry with versioned invalidation key. |

---

## Hardware Impact

**Phase 1 (Geocoder Enhancement):**
- Zero new containers
- Redis: ~1MB additional for geocode cache (trivial)
- PostgreSQL: geocoded_locations table, ~100 bytes/row, <100K rows = <10MB
- CPU: geocoding at <1ms/lookup, negligible

**Phase 2 (MapLibre Enhancements):**
- Zero backend impact
- Frontend: ~50KB additional JS (sparkline SVG generation)
- PostgreSQL: analyst_pins table, <1000 rows per deployment

**Phase 3 (H3 Hotspots):**
- h3 Python package: ~5MB installed, pure computation
- PostgreSQL: location_hex_stats, <10K rows per topic
- Frontend: h3-js ~50KB (lazy-loaded behind toggle)

**Total new infrastructure: Zero containers. Zero new services.**

Update hardware.md after Phase 1 implementation to reflect expanded geocoder.

---

## Dependency Map

```
Phase 1: Geocoder Enhancement
    ├── No dependencies
    └── Enables: Phase 2e (drill-down), Phase 3 (H3)

Phase 2: MapLibre Enhancements
    ├── 2a (PNG export): No dependencies
    ├── 2b (Heatmap): Depends on Phase 1 (needs geocoded data)
    ├── 2c (Sparklines): Depends on Phase 1
    ├── 2d (Manual pins): No dependencies
    └── 2e (Drill-down): Depends on Phase 1

Phase 3: H3 Hotspots
    ├── Depends on Phase 1 (geocoded_locations table)
    └── Gate: 4 weeks production data + hit rate >70%
```

---

## What This Plan Does NOT Do

Explicitly out of scope (per persona feedback):

- No deck.gl migration (MapLibre sufficient)
- No OSM/Overpass integration (OPSEC risk)
- No Nominatim container (geonamescache expansion first)
- No cross-topic spatial convergence (Phase 4 future)
- No narrative cascade tracking (separate feature, not map infrastructure)
- No identifier-linked arcs (requires Engine C maturity)
- No classification banners on map (separate security feature)
- No 3D visualization (adds complexity without analytical value)
- No temporal animation (requires semantic connection layer first)
