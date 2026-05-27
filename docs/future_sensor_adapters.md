# Future: ADS-B, AIS, and Thermal Sensor Adapters for Anveshak

**Status:** Deferred. Adapter designs are complete but NOT implemented.

**Reason for deferral:** Raw sensor data (2.4M AIS records/day) doesn't produce signals
in Anveshak's current pipeline. No text to embed, no narratives to cluster, no independent
sources for signal firing. The content_items table would be overwhelmed with data that
skips the entire analyst pipeline (NLP, embedding, clustering, reports).

**When to build:** Either:
1. When Sangrah (see `docs/future_sangrah.md`) provides a derived-events layer that converts
   raw positions into textual events ("vessel went dark in Hormuz") — those events ARE text
   and produce signals naturally.
2. When Anveshak adds a separate geo-alerting system (geo_alerts table + map overlay)
   that doesn't go through content_items.

---

## Context

DeltaSweep validated that ADS-B, AIS, and satellite thermal data are valuable OSINT sources.
Drishti already has working API client logic for OpenSky, ADS-B Exchange, and AISStream.
This document captures complete adapter designs for when they become viable.

See also: `docs/future_sangrah.md` for the multi-product shared collection approach.

## What Changes

### New files (6)
```
services/social/anveshak/social/adapters/adsb.py         # OpenSky + ADS-B Exchange adapter
services/social/anveshak/social/adapters/ais.py           # AISStream adapter
services/social/anveshak/social/adapters/thermal.py       # NASA FIRMS adapter
tests/unit/test_adsb_adapter.py                           # Conformance + unit tests
tests/unit/test_ais_adapter.py                            # Conformance + unit tests
tests/unit/test_thermal_adapter.py                        # Conformance + unit tests
```

### Modified files (6)
```
services/social/anveshak/social/settings.py               # Add adapter settings
services/social/anveshak/social/jobs.py                   # Register adapters in _REQUIRED_CREDENTIALS + adapter_configs
services/social/pyproject.toml                            # Add websockets dependency
tests/unit/test_social_conformance.py                     # Add new platforms to allowed set
infra/compose.yml                                         # Add env vars to social service
.env.example                                              # Document new env vars
```

### Migration (1)
```
services/api/migrations/versions/NNN_add_sensor_columns.py  # Add latitude, longitude to content_items
```

## Design Decisions

### 1. Sensor data as raw_text (JSON string)

ADS-B/AIS/thermal records aren't prose — they're structured sensor readings. We store them as:
```python
raw_text = json.dumps(aircraft_state)  # e.g. {"icao24":"ab1c2d","lat":18.93,"lon":72.82,...}
```

This works because:
- `content_hash = SHA-256(normalize(raw_text))` — dedup works on JSON strings
- `ingest_raw_item()` doesn't care what raw_text contains
- The analyst pipeline detects `platform in ("adsb","ais","thermal")` and skips NLP/embedding
- Clustering/signals still work on source diversity (`independent_source_count`)

### 2. Add latitude/longitude to content_items

New nullable columns. Populated at ingest time for geo-tagged records. Enables future geo queries without schema redesign.

```sql
ALTER TABLE content_items ADD COLUMN latitude DOUBLE PRECISION;
ALTER TABLE content_items ADD COLUMN longitude DOUBLE PRECISION;
CREATE INDEX idx_content_items_geo ON content_items(latitude, longitude)
    WHERE latitude IS NOT NULL;
```

### 3. AIS stream → poll-style batching

AISStream is WebSocket (always-on), but Anveshak's social service polls adapters on a schedule. AIS adapter:
- Connects to WebSocket on each `collect()` call
- Reads messages for `AISSTREAM_BATCH_DURATION_S` (default 30s)
- Yields batch, disconnects
- Next poll cycle reconnects

This fits the existing architecture without adding a background process. Not ideal for real-time but sufficient for monitoring use cases. True streaming can come with Sangrah later.

### 4. One adapter per data domain, not per API provider

```
adsb.py    — wraps BOTH OpenSky (free) and ADS-B Exchange (paid, RapidAPI)
             Tries OpenSky first, falls back to ADS-B Exchange if quota exhausted
ais.py     — wraps AISStream (single provider)
thermal.py — wraps NASA FIRMS (free, API key required)
```

This matches how an analyst thinks: "I want aircraft data" not "I want OpenSky data."

### 5. Platform values

Add to conformance suite allowed set:
```python
{"telegram", "reddit", "bluesky", "twitter", "web", "adsb", "ais", "thermal"}
```

### 6. Zone/bbox as source_handles

For geo adapters, `sources.url_or_handle` stores a JSON bbox string:
```
{"lat_min": 0, "lon_min": 40, "lat_max": 30, "lon_max": 100, "name": "IOR"}
```

The adapter parses this in `collect()`. This avoids schema changes to the sources table — url_or_handle is already TEXT. The analyst creates a source with platform="adsb" and this bbox as the handle.

## Adapter Designs

### ADS-B Adapter (`adsb.py`)

```python
class ADSBAdapter(SourceAdapterBase):
    adapter_id = "adsb-v1"
    platform = "adsb"
    adapter_version = "1.0.0"

    async def authenticate(self) -> None:
        # Try OpenSky (free, Basic Auth)
        if settings.opensky_username and settings.opensky_password:
            self._opensky_client = httpx.AsyncClient(
                base_url="https://opensky-network.org/api",
                auth=(settings.opensky_username, settings.opensky_password),
                timeout=httpx.Timeout(15.0, read=30.0),
            )
        # Try ADS-B Exchange (paid, RapidAPI)
        if settings.adsb_exchange_api_key:
            self._adsbx_client = httpx.AsyncClient(
                base_url="https://adsbexchange-com1.p.rapidapi.com/v2/",
                headers={
                    "X-RapidAPI-Key": settings.adsb_exchange_api_key,
                    "X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com",
                },
                timeout=httpx.Timeout(15.0, read=30.0),
            )
        if not self._opensky_client and not self._adsbx_client:
            raise AdapterAuthError("No ADS-B credentials configured")

    async def collect(self, topic_keywords, source_handles, topic_id) -> AsyncIterator[RawItem]:
        for handle in source_handles:
            zone = json.loads(handle)  # {"lat_min":..., "lon_min":..., ...}
            aircraft = await self._poll_zone(zone)
            for ac in aircraft:
                yield RawItem(
                    raw_text=json.dumps(ac),
                    url=f"https://opensky-network.org/api/states?icao24={ac.get('icao24','')}",
                    platform=self.platform,
                    captured_at=datetime.now(UTC),
                    source_handle=handle,
                )

    async def _poll_zone(self, zone: dict) -> list[dict]:
        # Try OpenSky first (free)
        if self._opensky_client:
            try:
                return await self._poll_opensky(zone)
            except AdapterRateLimitError:
                log.info("adsb.opensky_quota_exhausted_fallback_to_adsbx")

        # Fall back to ADS-B Exchange (paid)
        if self._adsbx_client:
            return await self._poll_adsbx(zone)

        return []

    async def _poll_opensky(self, zone: dict) -> list[dict]:
        # Rate limit: sliding window, max 10 req/min
        # GET /states/all?lamin=...&lomin=...&lamax=...&lomax=...
        # Parse state vector array (17 fields by index)
        # Return list of dicts with icao24, callsign, lat, lon, altitude, velocity, etc.
        ...

    async def _poll_adsbx(self, zone: dict) -> list[dict]:
        # Rate limit: 0.6s between requests
        # Convert bbox to center + radius (Drishti's _bbox_center_and_radius)
        # GET /lat/{lat}/lon/{lon}/dist/{radius}/
        # Parse data.ac array
        # Return list of dicts with normalized field names
        ...
```

### AIS Adapter (`ais.py`)

```python
class AISAdapter(SourceAdapterBase):
    adapter_id = "ais-v1"
    platform = "ais"
    adapter_version = "1.0.0"

    async def authenticate(self) -> None:
        if not settings.aisstream_api_key:
            raise AdapterAuthError("Missing AISSTREAM_API_KEY")
        self._api_key = settings.aisstream_api_key

    async def collect(self, topic_keywords, source_handles, topic_id) -> AsyncIterator[RawItem]:
        # Parse all bboxes from source_handles
        bboxes = [json.loads(h) for h in source_handles]
        if not bboxes:
            return

        # Build merged bounding box (union of all zones)
        merged = self._merge_bboxes(bboxes)

        # Connect to WebSocket, collect for BATCH_DURATION_S, yield batch
        subscription = {
            "APIKey": self._api_key,
            "BoundingBoxes": [[
                [merged["lat_min"], merged["lon_min"]],
                [merged["lat_max"], merged["lon_max"]],
            ]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData", "StandardClassBPositionReport"],
        }

        try:
            async with websockets.connect(
                settings.aisstream_ws_url,
                ping_interval=20, ping_timeout=10, open_timeout=30,
            ) as ws:
                await ws.send(json.dumps(subscription))
                deadline = time.monotonic() + settings.aisstream_batch_duration_s

                async for raw_msg in ws:
                    if time.monotonic() > deadline:
                        break

                    msg = json.loads(raw_msg if isinstance(raw_msg, str) else raw_msg.decode())
                    msg_type = msg.get("MessageType", "")
                    if msg_type not in _CAPTURED_MSG_TYPES:
                        continue

                    metadata = msg.get("MetaData", {})
                    lat = metadata.get("latitude")
                    lon = metadata.get("longitude")

                    # Check which source_handle bbox contains this point
                    matching_handle = self._find_containing_bbox(lat, lon, bboxes, source_handles)
                    if not matching_handle:
                        continue

                    yield RawItem(
                        raw_text=json.dumps(msg),
                        url=f"https://www.marinetraffic.com/en/ais/details/ships/{metadata.get('MMSI','')}",
                        platform=self.platform,
                        captured_at=self._parse_capture_ts(metadata),
                        source_handle=matching_handle,
                    )
        except (ConnectionClosed, InvalidHandshake, OSError) as exc:
            raise AdapterDegradedError(f"AISStream connection error: {exc}")
```

### Thermal Adapter (`thermal.py`)

```python
class ThermalAdapter(SourceAdapterBase):
    adapter_id = "thermal-v1"
    platform = "thermal"
    adapter_version = "1.0.0"

    async def authenticate(self) -> None:
        if not settings.firms_api_key:
            raise AdapterAuthError("Missing FIRMS_API_KEY")
        self._client = httpx.AsyncClient(
            base_url="https://firms.modaps.eosdis.nasa.gov/api",
            timeout=httpx.Timeout(15.0, read=60.0),
        )

    async def collect(self, topic_keywords, source_handles, topic_id) -> AsyncIterator[RawItem]:
        for handle in source_handles:
            zone = json.loads(handle)
            hotspots = await self._fetch_hotspots(zone)
            for hs in hotspots:
                yield RawItem(
                    raw_text=json.dumps(hs),
                    url=f"https://firms.modaps.eosdis.nasa.gov/map/#{hs.get('latitude','')},{hs.get('longitude','')}",
                    platform=self.platform,
                    captured_at=self._parse_acq_datetime(hs),
                    source_handle=handle,
                )

    async def _fetch_hotspots(self, zone: dict) -> list[dict]:
        # GET /area/csv/{api_key}/VIIRS_SNPP_NRT/{bbox}/{days}
        # Parse CSV response (latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, frp)
        # Return list of dicts
        ...
```

## Migration: Add Geo Columns

```python
# services/api/migrations/versions/NNN_add_sensor_columns.py
"""Add latitude/longitude to content_items for geo-tagged sensor data."""

async def upgrade(conn):
    await conn.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION")
    await conn.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION")
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_items_geo
        ON content_items(latitude, longitude)
        WHERE latitude IS NOT NULL
    """)

async def downgrade(conn):
    await conn.execute("DROP INDEX IF EXISTS idx_content_items_geo")
    await conn.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS longitude")
    await conn.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS latitude")
```

Update `ingest_raw_item()` to populate lat/lon when available (check raw_text JSON for latitude/longitude keys).

## Settings Additions

```python
# services/social/anveshak/social/settings.py — add these fields:

# ADS-B (OpenSky)
opensky_username: Optional[str] = None
opensky_password: Optional[str] = None
opensky_max_requests_per_minute: int = 10

# ADS-B (ADS-B Exchange — paid fallback)
adsb_exchange_api_key: Optional[str] = None
adsb_exchange_max_requests_per_minute: int = 100

# ADS-B adapter master switch
adsb_adapter_enabled: bool = False

# AIS (AISStream)
aisstream_api_key: Optional[str] = None
aisstream_ws_url: str = "wss://stream.aisstream.io/v0/stream"
aisstream_batch_duration_s: int = 30
ais_adapter_enabled: bool = False

# Thermal (NASA FIRMS)
firms_api_key: Optional[str] = None
firms_lookback_days: int = 1
thermal_adapter_enabled: bool = False
```

## Registration in jobs.py

```python
# Add to _REQUIRED_CREDENTIALS:
"adsb": [],  # empty — at least one of opensky or adsbx checked in authenticate()
"ais": [("aisstream_api_key", "AISSTREAM_API_KEY")],
"thermal": [("firms_api_key", "FIRMS_API_KEY")],

# Add to adapter_configs list:
(settings.adsb_adapter_enabled, "adsb", lambda: ADSBAdapter()),
(settings.ais_adapter_enabled, "ais", lambda: AISAdapter()),
(settings.thermal_adapter_enabled, "thermal", lambda: ThermalAdapter()),
```

## Analyst Pipeline Changes

The analyst `analyse_content` job currently runs NLP, embedding, translation on all content. Sensor data (JSON payloads) should skip text analysis but still participate in signal detection.

In `services/analyst/anveshak/analyst/jobs.py`, add early check:

```python
SENSOR_PLATFORMS = {"adsb", "ais", "thermal"}

async def analyse_content(ctx, content_item_id):
    row = await fetch_content_item(...)

    # Sensor data: extract lat/lon, skip NLP/embedding
    if row["platform"] in SENSOR_PLATFORMS:
        await _process_sensor_item(row)
        return

    # Existing text analysis pipeline continues...
```

`_process_sensor_item()` extracts lat/lon from raw_text JSON, updates the row, but skips embedding/NER/translation. The item still participates in the signals engine via source diversity counting.

## TDD Sequence

```
Phase 1: Foundation
  1. RED:  Conformance test for ADSBAdapter (6 assertions including new platform "adsb")
     GREEN: Implement ADSBAdapter skeleton (authenticate raises, collect yields nothing)

  2. RED:  Conformance test for AISAdapter (platform "ais")
     GREEN: Implement AISAdapter skeleton

  3. RED:  Conformance test for ThermalAdapter (platform "thermal")
     GREEN: Implement ThermalAdapter skeleton

  4. RED:  Test that new platforms are in conformance allowed set
     GREEN: Update test_social_conformance.py allowed set

Phase 2: ADS-B Adapter (most complex — two providers)
  5. RED:  Test OpenSky rate limiter (sliding window, 10 req/min)
     GREEN: Implement _enforce_rate_limit()

  6. RED:  Test OpenSky zone polling with recorded HTTP fixture
     GREEN: Implement _poll_opensky() — parse state vector array by field index

  7. RED:  Test ADS-B Exchange bbox-to-center conversion (exact math from Drishti)
     GREEN: Implement _bbox_center_and_radius()

  8. RED:  Test ADS-B Exchange polling with recorded HTTP fixture
     GREEN: Implement _poll_adsbx()

  9. RED:  Test fallback logic (OpenSky 429 → ADS-B Exchange)
     GREEN: Implement _poll_zone() with fallback

  10. RED: Test RawItem fields (content_hash deterministic on JSON, url format, captured_at TZ-aware)
      GREEN: Wire up collect() to yield RawItems

Phase 3: AIS Adapter
  11. RED: Test WebSocket subscription message format
      GREEN: Implement subscription builder

  12. RED: Test message type filtering (only PositionReport, ShipStaticData, StandardClassBPositionReport)
      GREEN: Implement message filter

  13. RED: Test batch duration timeout (collect returns after N seconds)
      GREEN: Implement deadline-based collection loop

  14. RED: Test bbox containment check (point in which source_handle zone)
      GREEN: Implement _find_containing_bbox()

  15. RED: Test timestamp parsing (MetaData.time_utc format)
      GREEN: Implement _parse_capture_ts()

Phase 4: Thermal Adapter
  16. RED: Test FIRMS API URL construction (bbox, API key, days)
      GREEN: Implement _fetch_hotspots()

  17. RED: Test CSV response parsing (latitude, longitude, brightness, confidence, frp)
      GREEN: Implement CSV parser

  18. RED: Test RawItem yield with proper fields
      GREEN: Wire up collect()

Phase 5: Integration
  19. RED: Migration test (lat/lon columns exist after upgrade)
      GREEN: Write migration

  20. RED: Test ingest_raw_item() with sensor RawItem (JSON raw_text, lat/lon populated)
      GREEN: Update ingest.py to extract lat/lon from sensor platforms

  21. RED: Test analyse_content skips NLP for sensor platforms
      GREEN: Add SENSOR_PLATFORMS check in analyst jobs.py

  22. RED: Test adapter registration (all 3 appear in _ADAPTERS after startup with creds)
      GREEN: Update jobs.py registration

  23. RED: Test compose env vars forwarded (settings reads from env)
      GREEN: Update compose.yml and .env.example

  24. REFACTOR: Review all adapter code, simplify, ensure conformance passes
```

## Verification

```bash
# Unit tests (all adapters)
make test-unit  # includes conformance suite for adsb, ais, thermal

# Integration test (requires Docker Compose)
make test-integration  # ingest_raw_item with sensor data, lat/lon populated

# Manual smoke test
# 1. Set ADSB_ADAPTER_ENABLED=true + OPENSKY_USERNAME/PASSWORD in .env
# 2. Create source: platform=adsb, url_or_handle='{"lat_min":0,"lon_min":40,"lat_max":30,"lon_max":100,"name":"IOR"}'
# 3. Link source to topic
# 4. Wait for poll cycle (15 min or trigger manually)
# 5. Check content_items: SELECT count(*) FROM content_items WHERE source_id = '<adsb-source-id>'
```

## Dependencies

```toml
# services/social/pyproject.toml — add:
websockets = ">=12.0"  # for AISStream WebSocket
```

`httpx` is already a dependency (used by Bluesky adapter). No new HTTP client needed.

## Files Summary

| File | Action | What |
|------|--------|------|
| `services/social/anveshak/social/adapters/adsb.py` | CREATE | OpenSky + ADS-B Exchange adapter |
| `services/social/anveshak/social/adapters/ais.py` | CREATE | AISStream WebSocket adapter |
| `services/social/anveshak/social/adapters/thermal.py` | CREATE | NASA FIRMS adapter |
| `services/social/anveshak/social/settings.py` | EDIT | Add 12 new settings fields |
| `services/social/anveshak/social/jobs.py` | EDIT | Register 3 adapters in credentials + configs |
| `services/social/pyproject.toml` | EDIT | Add websockets dependency |
| `services/social/anveshak/social/ingest.py` | EDIT | Extract lat/lon from sensor JSON into new columns |
| `services/analyst/anveshak/analyst/jobs.py` | EDIT | Skip NLP/embedding for sensor platforms |
| `services/api/migrations/versions/NNN_add_sensor_columns.py` | CREATE | Add latitude, longitude columns |
| `tests/unit/test_social_conformance.py` | EDIT | Add adsb, ais, thermal to allowed platforms |
| `tests/unit/test_adsb_adapter.py` | CREATE | Conformance + rate limiter + zone polling + fallback tests |
| `tests/unit/test_ais_adapter.py` | CREATE | Conformance + WebSocket + batching + bbox tests |
| `tests/unit/test_thermal_adapter.py` | CREATE | Conformance + API + CSV parsing tests |
| `infra/compose.yml` | EDIT | Add env vars to social service |
| `.env.example` | EDIT | Document new env vars |
