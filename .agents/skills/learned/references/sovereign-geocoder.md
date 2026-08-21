# Sovereign Offline Geocoder (3-Layer)

## When to load: any feature that needs lat/lon for location names without a network call

---

## The Problem

Anveshak is a sovereign deployment — no data leaves the network boundary (CLAUDE.md rule 10).
Standard geocoding APIs (Google Maps, Nominatim, Pelias) require outbound HTTP.
geonamescache alone misses multi-word regions, provinces, abbreviations, and defence-specific locations.

---

## The Solution: 3-Layer Geocoding

### Layer 1: NER entities from analyst pipeline (primary, highest quality)

The analyst service already runs spaCy NER on every content item and stores GPE/LOC/FACILITY
entities in `extracted_entities`. Query these instead of re-extracting from text:

```python
SQL_FETCH_TOPIC_LOCATION_ENTITIES = """
    SELECT DISTINCT ee.entity_text
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND ee.entity_type IN ('GPE', 'LOC', 'FACILITY')
      AND ee.confidence >= 0.8
"""
```

Zero extra ML cost — entities already exist in DB.

### Layer 2: Regex extraction from LLM output (fallback)

Catches locations the LLM synthesises that weren't in any single source
(e.g. "India-China border" inferred from context):

```python
_CAPS_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
```

Filter against known locations (geonamescache + custom overlay).

### Layer 3: Custom locations overlay (defence-specific)

`infra/configs/geocoder/custom_locations.json` — loaded at startup:

```json
{
  "Andaman Islands": [11.74, 92.65],
  "Line of Actual Control": [34.0, 78.0],
  "LAC": [34.0, 78.0],
  "PoK": [34.0, 74.0],
  "INS Kadamba": [14.79, 74.10]
}
```

Editable config file — analyst can add locations without code changes.

---

## Merging Results (dedup by lowercase key)

```python
ner_entities = await db.fetch_topic_location_entities(pool, topic_id)
regex_names = extract_locations_from_text(combined_text)

seen_lower: set[str] = set()
location_names: list[str] = []
for name in ner_entities + regex_names:
    key = name.lower().strip()
    if key not in seen_lower:
        seen_lower.add(key)
        location_names.append(name)

locations = geocode_locations(location_names)  # checks custom → cities → countries
```

---

## Lookup Priority in geocode_locations()

1. Custom overlay (`_CUSTOM_LOCATIONS`) — defence-specific, highest priority
2. geonamescache cities (`_CITIES_BY_NAME`) — 25K cities by population
3. geonamescache countries (`_COUNTRIES_BY_NAME`) — resolved to capital coords

---

## Custom Overlay Loading Pattern

```python
def _load_custom_locations() -> None:
    candidates = [
        Path("/app/infra/configs/geocoder/custom_locations.json"),  # Docker
        Path(__file__).resolve().parents[5] / "infra" / "configs" / "geocoder" / "custom_locations.json",  # dev
    ]
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text())
            for name, coords in data.items():
                _CUSTOM_LOCATIONS[name.lower()] = (float(coords[0]), float(coords[1]))
            return
```

---

## GeoJSON — RFC 7946 coordinate order

**CRITICAL:** GeoJSON uses `[longitude, latitude]`, not `[latitude, longitude]`.

---

## Known Limitations

- geonamescache resolves country to capital city (misleading for border regions)
- Regex can't catch non-capitalised locations or non-Latin scripts
- Custom overlay must be manually maintained
- NER entities only available for content that has been through the analyst pipeline

---

## Hardware note

Zero hardware dependency. No GPU, no model download. Works on smallest VM.

---

## Implementation reference
- `services/reporter/anveshak/reporter/geocoder.py`
- `services/reporter/anveshak/reporter/worker.py` (step 7)
- `services/reporter/anveshak/reporter/db/__init__.py` (SQL_FETCH_TOPIC_LOCATION_ENTITIES)
- `infra/configs/geocoder/custom_locations.json`
