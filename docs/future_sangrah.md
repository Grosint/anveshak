# Sangrah: Standalone OSINT Data Collection Platform

**Status:** Future plan. Deferred — Anveshak works standalone today.
**Trigger:** Build Sangrah when Drishti deployment is imminent and multi-product source sharing becomes necessary.
**Immediate alternative:** Add ADS-B/AIS/thermal as native Anveshak adapters using existing `SourceAdapterBase` pattern.

---

## Context

Anveshak and Drishti both ingest from the same raw OSINT sources independently. Drishti already has ADS-B/AIS connectors that Anveshak wants. Rather than duplicate acquisition code, we build **Sangrah** — a standalone OSINT data collection service that both products (and future apps) consume from.

Sangrah is **invisible infrastructure**. Analysts never see it. They work in Anveshak (or Drishti). When they add a source in Anveshak's UI, Anveshak silently syncs that target to Sangrah, which starts collecting and delivering data back.

## Core Principles

1. **Sangrah is never client-facing** — downstream apps expose the UI
2. **No knowledge of downstream architecture** — Sangrah doesn't know about topics, entities, ARQ, Redpanda
3. **Clean wall** — no cross-product imports, no shared databases
4. **Multi-tenant** — projects (anveshak, drishti, future apps) get isolated API keys and filtered delivery
5. **content_hash is the universal correlation key** across all systems
6. **Same coding standards as Anveshak** — Python 3.12, FastAPI, Pydantic v2 strict, structlog, Prometheus
7. **TDD everywhere** — RED → GREEN → REFACTOR for every component
8. **Graceful degradation** — downstream apps can fall back to local adapters if Sangrah is unreachable

## Architecture

Sangrah has **two output tiers**. The analytics layer converts raw sensor data into
textual derived events that downstream apps like Anveshak can embed, cluster, and signal on.

```
                         SANGRAH (standalone service)
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  Connectors (collection)                                     │
  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
  │  │AISStream│ │ OpenSky │ │ Reddit  │ │ FIRMS   │  ...      │
  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          │
  │       │            │           │           │               │
  │  ┌─────────┐ ┌─────────┐ ┌──────────────────────┐         │
  │  │Telegram │ │ Bluesky │ │ Web Scraper (stateful)│         │
  │  └────┬────┘ └────┬────┘ └──────────┬───────────┘         │
  │       └─────┬──────┴──────┬──────────┘                     │
  │             v             v                                │
  │  ┌──────────────────────────────────────────────┐          │
  │  │              Connector Runner                 │          │
  │  │  auth, circuit breaker (per-source), dedup    │          │
  │  │  Target resolution (handle/geo/url)           │          │
  │  └───────────────┬──────────────────────────────┘          │
  │                  v                                         │
  │  ┌──────────────────────┐  ┌───────────────────┐          │
  │  │  PostgreSQL + PostGIS │  │      MinIO         │          │
  │  │  collected_records    │  │  raw payloads      │          │
  │  │  derived_events       │  │  (gzip compressed) │          │
  │  │  projects / targets   │  │  NEVER presigned   │          │
  │  └──────────┬───────────┘  └────────────────────┘          │
  │             │                                              │
  │             ├─── Tier 1: Raw records ─────────────────┐    │
  │             │    (social text, sensor positions,       │    │
  │             │     web content — as collected)          │    │
  │             │                                         │    │
  │             └─── Tier 2: Derived events ──────────┐   │    │
  │                  (textual summaries produced by    │   │    │
  │                   the Analytics Layer)             │   │    │
  │                                                   │   │    │
  │  ┌──────────────────────────────────────────────┐ │   │    │
  │  │         Analytics Layer (per domain)          │ │   │    │
  │  │                                              │ │   │    │
  │  │  maritime_analytics/                         │ │   │    │
  │  │    gap_detector      → AIS gap events        │ │   │    │
  │  │    zone_alerts       → entry/exit events     │ │   │    │
  │  │    concentration     → vessel clustering     │ │   │    │
  │  │                                              │ │   │    │
  │  │  aviation_analytics/                         │ │   │    │
  │  │    orbit_detector    → surveillance patterns │ │   │    │
  │  │    zone_alerts       → restricted zone entry │ │   │    │
  │  │    concentration     → aircraft clustering   │ │   │    │
  │  │                                              │ │   │    │
  │  │  thermal_analytics/                          │ │   │    │
  │  │    anomaly_detector  → high FRP near infra   │ │   │    │
  │  │    correlation       → hotspot + news match  │ │   │    │
  │  │                                              │ │   │    │
  │  │  State: Redis (last-seen, sliding windows)   │ │   │    │
  │  │  Reference: static GeoJSON (infrastructure)  │ │   │    │
  │  └──────────────────────────────────────────────┘ │   │    │
  │                                                   │   │    │
  │  ┌──────────────────────────────────────────────┐ │   │    │
  │  │           Delivery Layer                      │ │   │    │
  │  │  /projects/{id}/records → Tier 1 (raw)  ─────┘   │    │
  │  │  /projects/{id}/events  → Tier 2 (derived) ──┘        │
  │  │  REST (pull) │ Webhook (push) │ WebSocket              │
  │  │  API proxies payload from MinIO internally             │
  │  └──────┬───────┴───────┬────────┴───────┬──────┘         │
  │         │               │                │                 │
  │  Cron: retention purge, orphan cleanup, delivery alerting  │
  │  Admin UI: project CRUD, connector status (DevOps only)    │
  │  Observability: own Prometheus + Grafana + Loki            │
  └──────────────────────────────────────────────────────────────┘
           │               │                │
           v               v                v
      ┌────────┐      ┌────────┐      ┌────────┐
      │ANVESHAK│      │DRISHTI │      │FUTURE  │
      │ Tier 2 │      │ Tier 1 │      │  APP   │
      │(events)│      │ (raw)  │      │either  │
      │ text → │      │ raw →  │      │ tier   │
      │embed → │      │MinIO → │      │        │
      │cluster │      │Redpanka│      │        │
      │→signal │      │→entity │      │        │
      └────────┘      └────────┘      └────────┘
```

## Two-Tier Delivery Model

Projects subscribe to connectors at a specific tier:

```
POST /api/v1/project-connectors
Authorization: Bearer sk_anv_...
{
    "connector_id": "aisstream-v1",
    "subscription_tier": "derived"     // Anveshak wants text events, not 2.4M positions/day
}

POST /api/v1/project-connectors
Authorization: Bearer sk_dri_...
{
    "connector_id": "aisstream-v1",
    "subscription_tier": "raw"         // Drishti wants raw positions for entity resolution
}
```

| Tier | What | Volume | Consumer | Endpoint |
|------|------|--------|----------|----------|
| **Tier 1: Raw** | Exact records as collected | 2.4M/day (AIS), varies | Drishti (entity resolution) | `/projects/{id}/records` |
| **Tier 2: Derived** | Textual event summaries | ~50-200/day | Anveshak (signals pipeline) | `/projects/{id}/events` |

Social/web connectors only have Tier 1 (text is already signal-ready). Sensor connectors
(AIS, ADS-B, thermal) have both tiers — Tier 2 is produced by the analytics layer.

## Analytics Layer (Sensor → Text Events)

The analytics layer converts raw sensor data into textual derived events. It runs **inside
Sangrah** because it's source-domain knowledge (how AIS works, what an orbit pattern looks
like), not consumer-domain knowledge.

### Why Sangrah Owns This (Not Anveshak, Not Drishti)

- **Sangrah has the raw data** — it sees all positions in real time
- **It's source-domain logic** — "AIS gap detection" is about AIS, not about Anveshak's topics
- **Consumer-agnostic** — the same derived events are useful to any downstream app
- **Simple, stateless rules** — not ML, not graph queries, just Redis state + geometry

### Analytics per Domain

#### Maritime Analytics (`maritime_analytics/`)

| Analytic | Input | Output (text event) | State |
|----------|-------|---------------------|-------|
| **AIS gap** | No position for MMSI X in N hours | "Vessel MMSI 419000003 (bulk carrier) AIS gap: 6 hours in Strait of Hormuz. Last position 26.1°N 56.3°E, speed 12kn, heading 270°. Resumed at 25.8°N 55.9°E." | Redis hash: `sangrah:ais:last_seen:{mmsi}` → `{lat, lon, ts, speed, heading}` |
| **Zone entry/exit** | Position crosses geofence | "Vessel MMSI 419000003 entered Strait of Hormuz zone at 26.5°N 56.0°E. Flag: India. Type: Bulk Carrier." | Redis hash: `sangrah:ais:zone_state:{mmsi}` → `{current_zones}` |
| **Concentration** | N vessels in R radius within T minutes | "Unusual vessel concentration: 8 vessels within 5nm of 25.0°N 55.0°E. Types: 3 tankers, 2 cargo, 3 unknown. Detected over 45 minutes." | Redis sorted set: `sangrah:ais:grid:{h3_cell}` → positions with timestamp scores |

#### Aviation Analytics (`aviation_analytics/`)

| Analytic | Input | Output (text event) | State |
|----------|-------|---------------------|-------|
| **Orbit detection** | Aircraft makes N loops in same area | "Aircraft ICAO24 abc123 (callsign RECON1) circling at 25°N 66°E, altitude 25000ft. Pattern: surveillance orbit, 5 loops over 3 hours. Zone: Arabian Sea." | Redis list: `sangrah:adsb:track:{icao24}` → last N positions |
| **Zone entry** | Military aircraft enters monitored zone | "Military aircraft ICAO24 def456 entered IOR monitoring zone at 18.9°N 72.8°E. Altitude 35000ft, speed 450kn, heading 270°." | Redis hash: `sangrah:adsb:zone_state:{icao24}` |
| **Concentration** | N aircraft in R radius | "Unusual military aircraft concentration: 5 aircraft within 50nm of 25°N 66°E. Detected over 2 hours." | Redis sorted set |

#### Thermal Analytics (`thermal_analytics/`)

| Analytic | Input | Output (text event) | State |
|----------|-------|---------------------|-------|
| **Infrastructure anomaly** | High FRP hotspot near known facility | "Thermal anomaly detected at 26.3°N 56.1°E, FRP 450 MW. Within 2km of Bandar Abbas refinery (capacity: 320kbpd). Satellite: VIIRS SNPP." | Static GeoJSON: known infrastructure locations |
| **Cluster anomaly** | Multiple hotspots in unusual area | "Thermal cluster: 12 hotspots within 5km of 24.1°N 54.5°E over 6 hours. No known industrial facility. Possible military activity or large fire." | Redis sorted set |

### Analytics Configuration

```python
# sangrah/analytics/config.py
class MaritimeAnalyticsConfig(BaseSettings):
    ais_gap_threshold_hours: int = 6          # hours without position = gap event
    ais_gap_check_interval_s: int = 300       # check every 5 min
    zone_alert_enabled: bool = True
    concentration_radius_nm: float = 5.0
    concentration_min_vessels: int = 5
    concentration_window_minutes: int = 60
    model_config = {"env_prefix": "MARITIME_ANALYTICS_"}

class AviationAnalyticsConfig(BaseSettings):
    orbit_min_loops: int = 3
    orbit_radius_nm: float = 20.0
    orbit_check_interval_s: int = 600         # check every 10 min
    concentration_radius_nm: float = 50.0
    concentration_min_aircraft: int = 3
    model_config = {"env_prefix": "AVIATION_ANALYTICS_"}

class ThermalAnalyticsConfig(BaseSettings):
    frp_anomaly_threshold_mw: float = 100.0
    infrastructure_proximity_km: float = 5.0
    cluster_radius_km: float = 5.0
    cluster_min_hotspots: int = 5
    model_config = {"env_prefix": "THERMAL_ANALYTICS_"}
```

### Derived Events Table

```sql
CREATE TABLE derived_events (
    event_id        TEXT PRIMARY KEY,           -- UUID v7
    connector_id    TEXT NOT NULL,              -- which connector produced the raw data
    event_type      TEXT NOT NULL,              -- "ais_gap", "zone_entry", "concentration", "orbit", "thermal_anomaly"
    event_text      TEXT NOT NULL,              -- human-readable text summary (THIS is what Anveshak ingests)
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    severity        TEXT NOT NULL DEFAULT 'info',  -- info | warning | critical
    raw_record_ids  TEXT[] NOT NULL DEFAULT '{}',  -- references to collected_records that triggered this
    metadata        JSONB DEFAULT '{}',         -- structured event data (mmsi, icao24, frp, etc.)
    labels          JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_derived_events_type ON derived_events(event_type, created_at);
CREATE INDEX idx_derived_events_connector ON derived_events(connector_id, created_at);
```

### How Anveshak Consumes Derived Events

```
Anveshak consumer polls: GET /api/v1/projects/{id}/events?after=cursor&limit=100

Response:
{
    "events": [
        {
            "event_id": "evt_019abc...",
            "connector_id": "aisstream-v1",
            "event_type": "ais_gap",
            "event_text": "Vessel MMSI 419000003 (bulk carrier) AIS gap: 6 hours...",
            "latitude": 26.1,
            "longitude": 56.3,
            "severity": "warning",
            "metadata": {"mmsi": 419000003, "gap_hours": 6, "zone": "Hormuz"},
            "created_at": "2026-05-27T14:30:00Z"
        }
    ],
    "next_cursor": "evt_019abc...",
    "has_more": false
}

Anveshak maps to RawItem:
    raw_text = event["event_text"]       ← THIS IS TEXT — embeds, clusters, signals
    url = f"sangrah://events/{event_id}"
    platform = "sangrah"                  ← new platform value
    captured_at = event["created_at"]
    source_handle = event["connector_id"]

→ ingest_raw_item() → content_items → embedding → clustering
→ "AIS gap in Hormuz" clusters with Telegram post about "suspicious vessel activity near Iran"
→ independent_source_count = 2 (sangrah + telegram) → SIGNAL FIRES
```

**This is the signal value.** Not the raw position. The derived event combined with other
OSINT sources about the same incident.

### Analytics Metrics

```
sangrah_analytics_events_total{connector_id, event_type, severity}
sangrah_analytics_processing_seconds{domain}
sangrah_analytics_state_keys{domain}           -- Redis key count per domain
sangrah_analytics_false_positive_rate{event_type}  -- if feedback loop exists
```

## Sync Model: Downstream → Sangrah

```
Analyst in Anveshak UI:
  "Add Telegram channel @DefenceAlert to topic IOR Monitoring"
      │
      ▼
Anveshak (immediate push + periodic reconciliation fallback):
  1. Saves source in own DB (sources table)
  2. POST sangrah-api:8010/api/v1/targets
     { "connector_id": "telegram-v1", "handle": "@DefenceAlert",
       "config": {"keywords": ["naval", "maritime"]} }
  3. Reconciliation cron every 5 min:
     diff Anveshak sources vs Sangrah targets, sync gaps
     Also serves as Sangrah heartbeat check
      │
      ▼
Sangrah:
  4. Merges target across all projects that requested it
  5. Connector collects from @DefenceAlert (fetched once even if 3 projects want it)
  6. Tags records → delivers to each requesting project
      │
      ▼
Anveshak (thin consumer):
  7. Polls GET /api/v1/projects/{id}/records?after=cursor (or receives webhook)
  8. GET /api/v1/projects/{id}/records/{id}/payload (authenticated, API proxies from MinIO)
  9. Maps to RawItem → ingest_raw_item() → PG → ARQ analyse_content
  10. ACKs cursor
  11. Analyst sees the data in their topic
```

**Graceful degradation:** If Sangrah is unreachable and `SANGRAH_FALLBACK_TO_LOCAL=true`, Anveshak activates its local adapters for sources it still has code for.

## Multi-Tenant Model

```sql
-- Projects (tenants)
CREATE TABLE projects (
    project_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    api_key_hash    TEXT NOT NULL,             -- bcrypt of API key
    is_active       BOOLEAN DEFAULT TRUE,
    retention_days  INTEGER NOT NULL DEFAULT 30,  -- data retention per project
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    labels          JSONB NOT NULL
);

-- Which connectors a project subscribes to
CREATE TABLE project_connectors (
    project_id      TEXT REFERENCES projects(project_id),
    connector_id    TEXT NOT NULL,
    enabled         BOOLEAN DEFAULT TRUE,
    config          JSONB DEFAULT '{}',         -- project-level credential overrides, quotas
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (project_id, connector_id)
);

-- Collection targets — WHAT to fetch (pushed by downstream apps)
CREATE TABLE collection_targets (
    target_id       TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(project_id),
    connector_id    TEXT NOT NULL,
    target_type     TEXT NOT NULL,               -- "channel", "subreddit", "zone", "url", "rss"
    target_handle   TEXT NOT NULL,               -- "@DefenceAlert", "r/osint"
    target_config   JSONB DEFAULT '{}',          -- keywords, follow_links, bbox, crawl_depth
    zone_geom       GEOMETRY(POLYGON, 4326),     -- PostGIS geometry for geo targets (ADS-B, AIS)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    labels          JSONB NOT NULL
);

-- Effective targets view (only targets with active projects)
CREATE VIEW active_targets AS
SELECT DISTINCT ct.target_handle, ct.connector_id, ct.target_type,
       ct.target_config, ct.zone_geom
FROM collection_targets ct
JOIN projects p ON ct.project_id = p.project_id
WHERE ct.is_active = TRUE AND p.is_active = TRUE;

-- Core records table
CREATE TABLE collected_records (
    record_id         TEXT PRIMARY KEY,          -- UUID v7 (time-sortable)
    connector_id      TEXT NOT NULL,
    connector_version TEXT NOT NULL,
    schema_hint       TEXT NOT NULL,             -- "ais.position_report", "social.reddit.post"
    capture_ts        TIMESTAMPTZ NOT NULL,
    ingest_ts         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_hash      TEXT NOT NULL,             -- SHA-256 dedup key
    evidence_ref      TEXT NOT NULL,             -- MinIO path (internal only, never exposed)
    latitude          DOUBLE PRECISION,          -- for geo-tagged records (ADS-B, AIS, thermal)
    longitude         DOUBLE PRECISION,          -- enables PostGIS point-in-polygon target resolution
    metadata          JSONB DEFAULT '{}',        -- connector-specific hints
    labels            JSONB NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_records_content_hash ON collected_records(content_hash);
CREATE INDEX idx_records_connector_ts ON collected_records(connector_id, capture_ts);
CREATE INDEX idx_records_ingest_ts ON collected_records(ingest_ts);
CREATE INDEX idx_records_geo ON collected_records USING gist (
    ST_MakePoint(longitude, latitude)
) WHERE latitude IS NOT NULL;

-- Raw payloads in MinIO (not PostgreSQL BYTEA)
-- Path: sangrah-data/{connector_id}/{YYYY}/{MM}/{DD}/{content_hash}.json.gz

-- Cursor-based delivery tracking (NOT per-record — scales to millions)
CREATE TABLE delivery_cursors (
    project_id      TEXT REFERENCES projects(project_id) PRIMARY KEY,
    last_record_id  TEXT,                       -- last record_id delivered/polled
    last_seen_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Webhook retry queue (only for failed webhook deliveries, not for pull consumers)
CREATE TABLE webhook_failures (
    failure_id      TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(project_id),
    record_id       TEXT REFERENCES collected_records(record_id),
    attempt_count   INTEGER NOT NULL DEFAULT 1,
    next_retry_at   TIMESTAMPTZ NOT NULL,
    last_error      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Delivery config per project
CREATE TABLE delivery_config (
    project_id          TEXT REFERENCES projects(project_id) PRIMARY KEY,
    method              TEXT NOT NULL CHECK (method IN ('pull', 'webhook', 'websocket')),
    webhook_url         TEXT,
    webhook_secret_hash TEXT,
    poll_interval_hint_s INTEGER DEFAULT 30
);

-- Record-to-project mapping (which projects should receive which records)
CREATE TABLE record_projects (
    record_id       TEXT REFERENCES collected_records(record_id),
    project_id      TEXT REFERENCES projects(project_id),
    target_id       TEXT REFERENCES collection_targets(target_id),
    PRIMARY KEY (record_id, project_id)
);
```

## Target Multiplexing & Resolution

```
Anveshak registered: @DefenceAlert, @MilWatchIOR
Drishti registered:  @DefenceAlert, @NavyWatch

Sangrah collects from: @DefenceAlert, @MilWatchIOR, @NavyWatch
                       (3 channels, not 4 — dedup at target level)

Record from @DefenceAlert → record_projects rows for BOTH anveshak AND drishti
Record from @MilWatchIOR  → record_projects row for ONLY anveshak
Record from @NavyWatch    → record_projects row for ONLY drishti
```

**Resolution strategy per connector type:**

| Connector type | Target resolution | How |
|---------------|-------------------|-----|
| Social (Telegram, Reddit, Bluesky, X) | Exact handle match | record.source_handle == target.target_handle |
| Geo (ADS-B, AIS, thermal) | Point-in-polygon | ST_Contains(target.zone_geom, ST_MakePoint(record.lon, record.lat)) |
| Web/RSS | Exact URL match | record.source_url == target.target_handle |

```python
# Runner pseudo-code for target resolution
async def resolve_projects(record: CollectedRecord, connector: SangrahConnectorBase) -> list[str]:
    if connector.resolution_mode == "handle":
        return await db.fetch_column("""
            SELECT DISTINCT ct.project_id FROM collection_targets ct
            JOIN projects p ON ct.project_id = p.project_id
            WHERE ct.connector_id = $1 AND ct.target_handle = $2
            AND ct.is_active = TRUE AND p.is_active = TRUE
        """, connector.connector_id, record.source_handle)

    elif connector.resolution_mode == "geo":
        return await db.fetch_column("""
            SELECT DISTINCT ct.project_id FROM collection_targets ct
            JOIN projects p ON ct.project_id = p.project_id
            WHERE ct.connector_id = $1
            AND ST_Contains(ct.zone_geom, ST_MakePoint($2, $3))
            AND ct.is_active = TRUE AND p.is_active = TRUE
        """, connector.connector_id, record.longitude, record.latitude)
```

## Target Lifecycle

| Event | Sangrah behavior |
|-------|-----------------|
| Anveshak adds source | Sangrah creates target. If target_handle already exists for another project, collection continues (shared). |
| Anveshak removes source | Sangrah marks target inactive for that project. If no active project has that target, orphan cleanup cron deactivates it. |
| All projects deactivate | Orphan cleanup cron (every 15 min) marks target is_active=false. Runner skips it. |
| Target re-added later | New target row created, collection resumes. |

## Storage & Security

```
Sangrah owns:
├── PostgreSQL + PostGIS  → metadata, targets, delivery tracking, geo queries
├── MinIO                 → raw payloads (NEVER exposed via presigned URLs)
└── Redis                 → circuit breakers, rate limiters, URL dedup (web scraper)
```

**Security: No presigned MinIO URLs.** Intelligence data never gets a public URL. Sangrah API proxies all payload access:

```
GET /api/v1/projects/{project_id}/records/{record_id}/payload
Authorization: Bearer sk_anv_...
→ API authenticates, fetches from MinIO internally, streams to consumer
```

**Retention:** Per-project `retention_days` (default 30). Cron job purges records + MinIO objects older than retention. Records still needed by other projects are NOT purged.

## Delivery Layer (no Redpanda, no Kafka)

All delivery is through Sangrah's authenticated API. No presigned URLs.

### Pull (primary for Anveshak)
```
GET /api/v1/projects/{id}/records?after={cursor}&limit=100&connector=aisstream-v1
Authorization: Bearer sk_anv_...

Response:
{
    "records": [...metadata...],
    "next_cursor": "rec_019...",
    "has_more": true
}

# Fetch raw payload (API proxies from MinIO):
GET /api/v1/projects/{id}/records/{record_id}/payload
→ streams gzip-compressed raw bytes

# ACK after processing:
POST /api/v1/projects/{id}/records/ack
{ "cursor": "rec_019..." }
```

### Webhook (push)
```
POST https://anveshak:8000/api/v1/sangrah-ingest
X-Sangrah-Signature: HMAC-SHA256(body, secret)
Body: { record metadata }
# Consumer fetches payload separately via GET .../payload
```
Retry: 3 attempts, exponential backoff (5s, 30s, 180s). Failures queryable via pull as fallback.

### WebSocket (real-time push)
```
WS /api/v1/projects/{id}/stream?connector=aisstream-v1
Authorization: Bearer sk_anv_...
```

### Backpressure
No active backpressure — retention policy prevents unbounded growth. Consumer must catch up within retention window or lose data. Prometheus alerts on high delivery lag.

## Connector Interface

```python
class SangrahConnectorBase(ABC):
    connector_id: ClassVar[str]           # "aisstream-v1"
    connector_version: ClassVar[str]      # semver
    domain: ClassVar[str]                 # "maritime", "aviation", "social", "web"
    poll_mode: ClassVar[str]              # "stream" | "poll"
    target_types: ClassVar[list[str]]     # ["channel","group"] | ["zone"] | ["subreddit"]
    resolution_mode: ClassVar[str]        # "handle" | "geo"

    @abstractmethod
    async def authenticate(self) -> None: ...

    @abstractmethod
    async def acquire(self, targets: list[Target]) -> AsyncIterator[CollectedRecord]: ...

    @abstractmethod
    async def health(self) -> ConnectorHealth: ...
```

**Web scraper is special.** Owns additional state: Redis URL dedup, crawl depth, quality gates, trafilatura extraction. All other connectors are pure stateless generators.

## Credentials

- Default connector credentials in Sangrah's `.env`
- Projects CAN provide their own via `project_connectors.config` JSONB
- Vault optional when `VAULT_ADDR` is set
- **Telegram hard constraint:** single-instance only (Telethon session)

## Observability

### Sangrah Metrics
```
sangrah_records_collected_total{connector_id, domain}
sangrah_records_stored_total{connector_id, status}
sangrah_records_delivered_total{project_id, connector_id, method}
sangrah_delivery_pending_count{project_id}
sangrah_delivery_lag_seconds{project_id}
sangrah_delivery_failures_total{project_id, method}
sangrah_connector_health{connector_id, status}
sangrah_connector_errors_total{connector_id, error_type}
sangrah_circuit_breaker_state{connector_id, source_handle}
sangrah_dedup_hits_total{connector_id}
sangrah_target_count{connector_id, project_id}
sangrah_retention_purged_total{project_id}
sangrah_minio_storage_bytes{connector_id}
sangrah_api_auth_failures_total{project_id}
```

### Grafana Dashboards (4)
1. **Connector Health** — per-connector status, collection rate, error rate, circuit breaker states
2. **Project Delivery** — per-project: delivered/pending/failed, lag, ACK rate, retention usage
3. **Pipeline Funnel** — collected → stored → delivered → ACKed (per project)
4. **Target Overview** — active targets per connector, multiplexing ratio, orphan count

### Cross-product view (optional)
Shared Grafana scrapes all Prometheus instances. Traces via content_hash. No product depends on it.

### Admin UI (minimal, DevOps only)
- Project CRUD, API key rotation
- Connector status, per-project delivery stats
- Collection target list, retention status

## Anveshak Changes (when Sangrah is built)

```
anveshak/
├── CLAUDE.md                                    # UPDATE: Sangrah integration rules
├── .env.example                                 # UPDATE: add SANGRAH_* vars
├── infra/compose.yml                            # UPDATE: add SANGRAH vars to api service env
├── services/api/anveshak/api/
│   ├── sangrah_sync.py                          # NEW: push + reconciliation sync
│   ├── sangrah_consumer.py                      # NEW: thin consumer (poll/webhook)
│   ├── sangrah_settings.py                      # NEW: SANGRAH_API_URL, API_KEY, ENABLED, FALLBACK
│   └── routes/sources.py                        # UPDATE: on source CRUD, call sangrah_sync
```

### Graceful Degradation
```python
SANGRAH_ENABLED = True
SANGRAH_FALLBACK_TO_LOCAL = True      # if Sangrah unreachable, use local adapters
SANGRAH_HEALTH_CHECK_INTERVAL_S = 60
```

## Phased Implementation (TDD throughout)

### Phase 0: Bootstrap
- Git tag Anveshak: `git tag v1.0-pre-sangrah`
- Create `../sangrah/` repo (CLAUDE.md, pyproject.toml, Makefile, skills)

### Phase 1: Core + 3 sensor connectors + Tier 1 delivery
ADS-B, AIS, thermal collection. Raw records stored. REST API for Tier 1 delivery.
Drishti can consume raw records immediately.
TDD: conformance suite → models → schema → storage → runner → API → connectors → e2e

### Phase 2: Analytics layer + Tier 2 delivery
Maritime analytics (AIS gap, zone alerts, concentration).
Aviation analytics (orbit detection, zone alerts).
Thermal analytics (infrastructure anomaly).
Derived events table + `/events` endpoint.
Anveshak consumer pulls Tier 2 events as text → signals pipeline.
TDD: analytics rules → derived events → delivery → Anveshak integration → e2e

### Phase 3: Migrate Reddit (validate the adapter migration pattern)
Extract from Anveshak, validate content_hash parity, delete from Anveshak.

### Phase 4: Migrate remaining social (Telegram, Bluesky, X)
One at a time. Telegram: hard stop Anveshak adapter first (session constraint).

### Phase 5: Migrate web scraper + RSS
Stateful connector with own crawl state. Anveshak scraper becomes thin consumer.

### Phase 6: Drishti integration
Drishti SangrahBridge consumer (polls Tier 1 REST, writes to own MinIO + Redpanda).

### Phase 7: New sources + analytics refinement
Prediction markets, webhook receiver, additional platforms.
Analytics tuning based on real data (thresholds, false positive rates).

## Architectural Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | MinIO for raw payloads, not PostgreSQL BYTEA | AIS at ~1000 rec/min generates TBs |
| 2 | No presigned MinIO URLs | Defence/LEA: intelligence data never gets public URL |
| 3 | Cursor-based delivery, not per-record tracking | Per-record at 1000/min × N projects = table explosion |
| 4 | PostGIS for geo target resolution | Bbox matching needs point-in-polygon |
| 5 | Web scraper is stateful connector | Crawl state, URL dedup, quality gates don't fit pure generator |
| 6 | Keywords in target_config | Sangrah filters at source, doesn't know about downstream topics |
| 7 | Telegram is single-instance | Telethon session string constraint |
| 8 | Per-project retention_days | Prevents unbounded MinIO growth |
| 9 | Graceful degradation (FALLBACK_TO_LOCAL) | Sangrah SPOF mitigated during migration |
| 10 | No Redpanda/Kafka in Sangrah | Clean wall. Consumers adapt on their side |
| 11 | record_projects for multiplexing | Lightweight mapping, purged with retention |
| 12 | Two-tier delivery (raw + derived) | Raw sensor data (2.4M AIS/day) can't produce signals in Anveshak — no text to embed/cluster. Analytics layer converts raw → textual events (~50-200/day) that Anveshak can use. |
| 13 | Analytics in Sangrah, not consumers | Source-domain knowledge (AIS gap = no position for N hours) belongs with the data, not with Anveshak or Drishti. Consumer-agnostic. |
| 14 | Redis state for analytics, not PostgreSQL | Last-seen hashes, sliding windows, position tracks — ephemeral state, not audit trail. Fast writes, auto-expire via TTL. |
| 15 | Static GeoJSON for infrastructure reference | Known refineries, ports, military bases. Loaded at startup, refreshed daily. Not in PostgreSQL — small, read-only, in-memory. |

## Key Files — Sangrah Repo Structure

```
sangrah/                              # ../sangrah/ (sibling to anveshak/)
├── CLAUDE.md
├── hardware.md
├── pyproject.toml
├── Makefile
├── .env.example
├── .claude/
│   ├── rules/
│   └── skills/
├── sangrah/
│   ├── models/                       # CollectedRecord, DerivedEvent, SangrahLabels, Target, Project
│   ├── connector/                    # SangrahConnectorBase, Runner, CircuitBreaker
│   ├── analytics/                    # Sensor → text event analytics layer
│   │   ├── base.py                   # AnalyticBase ABC (process_record, flush)
│   │   ├── config.py                 # Per-domain analytics config (thresholds, intervals)
│   │   ├── maritime/
│   │   │   ├── gap_detector.py       # AIS gap detection (Redis last-seen per MMSI)
│   │   │   ├── zone_alerts.py        # Vessel enters/exits geofence
│   │   │   └── concentration.py      # Unusual vessel clustering (H3 grid + sliding window)
│   │   ├── aviation/
│   │   │   ├── orbit_detector.py     # Surveillance orbit patterns (last N positions per ICAO24)
│   │   │   ├── zone_alerts.py        # Aircraft in monitored zone
│   │   │   └── concentration.py      # Unusual aircraft clustering
│   │   └── thermal/
│   │       ├── anomaly_detector.py   # High FRP near known infrastructure (static GeoJSON)
│   │       └── cluster_detector.py   # Multiple hotspots in unusual area
│   ├── storage/                      # PostgreSQL + PostGIS, MinIO
│   ├── delivery/                     # REST, Webhook, WebSocket (Tier 1 + Tier 2 endpoints)
│   ├── admin/                        # Project CRUD, minimal UI
│   ├── cron/                         # Retention, orphan cleanup, alerting
│   ├── connectors/                   # aisstream, opensky, adsb_exchange, firms, ...
│   ├── auth.py
│   ├── secrets.py
│   ├── settings.py
│   └── metrics.py
├── infra/
│   ├── compose.yml
│   ├── grafana/
│   └── prometheus/
├── tests/
│   ├── conformance/
│   ├── unit/
│   └── integration/
└── migrations/
```
