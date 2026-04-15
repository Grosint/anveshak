"""Geocoding helpers for the reporter service.

Uses geonamescache (bundled offline data — no network calls, no API key required).
CLAUDE.md hardware independence: no ML model here.
"""
from __future__ import annotations

import re
from typing import Any

import geonamescache
import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level geonamescache instance (loaded once)
# ---------------------------------------------------------------------------
_gc = geonamescache.GeonamesCache()

# Pre-build lookup indices for fast case-insensitive matching
_CITIES_BY_NAME: dict[str, dict[str, Any]] = {}
_COUNTRIES_BY_NAME: dict[str, dict[str, Any]] = {}


def _build_indices() -> None:
    """Build lowercase lookup dicts from geonamescache data."""
    for _key, city in _gc.get_cities().items():
        name_lower = city["name"].lower()
        # Prefer the higher-population city when names collide
        existing = _CITIES_BY_NAME.get(name_lower)
        if existing is None or city.get("population", 0) > existing.get("population", 0):
            _CITIES_BY_NAME[name_lower] = city

    for _key, country in _gc.get_countries().items():
        name_lower = country["name"].lower()
        # Country records in geonamescache don't carry lat/lon directly.
        # We look up the capital city to get coordinates.
        capital = country.get("capital", "")
        _COUNTRIES_BY_NAME[name_lower] = {"name": country["name"], "capital": capital}


_build_indices()

# Capitalised word / phrase pattern for candidate extraction
_CAPS_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def geocode_locations(location_names: list[str]) -> dict[str, tuple[float, float]]:
    """Return {name: (lat, lon)} for each recognised location.

    Matching is case-insensitive. Unknown locations are silently skipped.
    """
    result: dict[str, tuple[float, float]] = {}
    for name in location_names:
        key = name.lower().strip()
        if key in _CITIES_BY_NAME:
            city = _CITIES_BY_NAME[key]
            result[name] = (float(city["latitude"]), float(city["longitude"]))
        elif key in _COUNTRIES_BY_NAME:
            # Resolve country → capital city coordinates
            capital = _COUNTRIES_BY_NAME[key].get("capital", "")
            capital_key = capital.lower()
            if capital_key in _CITIES_BY_NAME:
                city = _CITIES_BY_NAME[capital_key]
                result[name] = (float(city["latitude"]), float(city["longitude"]))
            else:
                log.debug("geocoder.country_no_capital_coords", name=name, capital=capital)
        else:
            log.debug("geocoder.unknown_location", name=name)
    return result


def build_geojson(locations: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Convert {name: (lat, lon)} to a GeoJSON FeatureCollection.

    GeoJSON coordinate order is [longitude, latitude] per RFC 7946.
    """
    features: list[dict[str, Any]] = []
    for name, (lat, lon) in locations.items():
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],  # [lon, lat] — GeoJSON spec
                },
                "properties": {"name": name},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def extract_locations_from_text(text: str) -> list[str]:
    """Best-effort extraction of location names from free text.

    Strategy:
    1. Find all capitalised words/phrases via regex.
    2. Filter to those known in geonamescache (city or country).

    This is a lightweight heuristic — not NER-quality, but sufficient for the
    reporter service which does not have spaCy available.
    """
    if not text:
        return []

    candidates = _CAPS_PATTERN.findall(text)
    found: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        key = candidate.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        if key in _CITIES_BY_NAME or key in _COUNTRIES_BY_NAME:
            found.append(candidate)

    return found
