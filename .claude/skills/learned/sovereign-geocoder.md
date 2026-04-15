# Sovereign Offline Geocoder

## When to load: any feature that needs lat/lon for location names without a network call

---

## The Problem

Anveshak is a sovereign deployment — no data leaves the network boundary (CLAUDE.md rule 10).
Standard geocoding APIs (Google Maps, Nominatim, Pelias) require outbound HTTP.
`geopy` defaults to Nominatim which calls `nominatim.openstreetmap.org` — a violation.

---

## The Solution: geonamescache

`geonamescache` is a pure Python library with ~25k cities and all countries bundled
as JSON inside the package. Zero network calls, zero API keys, ~2MB footprint.

```toml
# pyproject.toml
dependencies = [
    "geonamescache>=1.7",
    # NOT geopy — geopy's default backend requires network
]
```

---

## Implementation Pattern

### Module-level pre-built indices (loaded once at import time)

```python
import geonamescache

_gc = geonamescache.GeonamesCache()
_CITIES_BY_NAME: dict[str, dict] = {}
_COUNTRIES_BY_NAME: dict[str, dict] = {}

def _build_indices() -> None:
    for _key, city in _gc.get_cities().items():
        name_lower = city["name"].lower()
        existing = _CITIES_BY_NAME.get(name_lower)
        # Prefer higher-population city when names collide
        if existing is None or city.get("population", 0) > existing.get("population", 0):
            _CITIES_BY_NAME[name_lower] = city
    for _key, country in _gc.get_countries().items():
        _COUNTRIES_BY_NAME[country["name"].lower()] = {
            "name": country["name"],
            "capital": country.get("capital", ""),
        }

_build_indices()  # runs once at import
```

### Geocode function — unknown locations silently skipped

```python
def geocode_locations(location_names: list[str]) -> dict[str, tuple[float, float]]:
    """Return {name: (lat, lon)}. Unknown locations silently skipped."""
    result = {}
    for name in location_names:
        key = name.lower().strip()
        if key in _CITIES_BY_NAME:
            city = _CITIES_BY_NAME[key]
            result[name] = (float(city["latitude"]), float(city["longitude"]))
        elif key in _COUNTRIES_BY_NAME:
            # Resolve country → capital coordinates
            capital_key = _COUNTRIES_BY_NAME[key].get("capital", "").lower()
            if capital_key in _CITIES_BY_NAME:
                city = _CITIES_BY_NAME[capital_key]
                result[name] = (float(city["latitude"]), float(city["longitude"]))
    return result
```

### GeoJSON builder — RFC 7946 coordinate order [lon, lat]

```python
def build_geojson(locations: dict[str, tuple[float, float]]) -> dict:
    """GeoJSON FeatureCollection from {name: (lat, lon)}.

    CRITICAL: GeoJSON spec (RFC 7946) uses [longitude, latitude] order,
    not [latitude, longitude]. Easy to get backwards.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],   # [lon, lat] — NOT [lat, lon]
                },
                "properties": {"name": name},
            }
            for name, (lat, lon) in locations.items()
        ],
    }
```

### Best-effort location extraction from text (no spaCy required)

```python
_CAPS_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

def extract_locations_from_text(text: str) -> list[str]:
    """Find capitalised phrases that match known city/country names."""
    if not text:
        return []
    candidates = _CAPS_PATTERN.findall(text)
    seen: set[str] = set()
    found: list[str] = []
    for candidate in candidates:
        key = candidate.lower().strip()
        if key not in seen and (key in _CITIES_BY_NAME or key in _COUNTRIES_BY_NAME):
            seen.add(key)
            found.append(candidate)
    return found
```

---

## Known Limitations

- City name collisions resolved by population (largest wins)
- Obscure towns, villages, and sub-city districts are not in the dataset
- Country lookup resolves to capital city, not geographic centroid
- `extract_locations_from_text` is regex-based, not NER — false positives possible
  (e.g. "The United" might match). Use spaCy LOC entities if the analyst service
  is available as a dependency.

---

## Hardware note

Zero hardware dependency. No GPU, no model download. Works on the smallest VM.

---

## Implementation reference
`services/reporter/src/anveshak/reporter/geocoder.py`
`tests/unit/test_reporter_geocoder.py`
