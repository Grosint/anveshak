"""Geocoding utilities for the analyst pipeline.

Pure-function text normalization + geocode lookup.
Uses geonamescache (bundled offline data — no network calls).
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import geonamescache
import structlog

log = structlog.get_logger(__name__)

# Entity types that represent locations (used to filter NER output for geocoding)
LOCATION_ENTITY_TYPES: frozenset[str] = frozenset({"GPE", "LOC", "FAC"})

# ---------------------------------------------------------------------------
# City name aliases — colonial/historical → modern canonical
# ---------------------------------------------------------------------------
_CITY_ALIASES: dict[str, str] = {
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "madras": "chennai",
    "bangalore": "bengaluru",
    "baroda": "vadodara",
    "trivandrum": "thiruvananthapuram",
    "cochin": "kochi",
    "pondicherry": "puducherry",
    "benares": "varanasi",
    "banaras": "varanasi",
    "poona": "pune",
    "simla": "shimla",
    "ooty": "udhagamandalam",
    "cawnpore": "kanpur",
    "allahabad": "prayagraj",
    "jubbulpore": "jabalpur",
    "tanjore": "thanjavur",
    "tuticorin": "thoothukudi",
    "mangalore": "mangaluru",
    "calicut": "kozhikode",
    "vizag": "visakhapatnam",
    "waltair": "visakhapatnam",
}

# Country/region aliases
_COUNTRY_ALIASES: dict[str, str] = {
    "us": "united states",
    "usa": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "the united states": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "britain": "united kingdom",
    "great britain": "united kingdom",
    "uae": "united arab emirates",
    "u.a.e.": "united arab emirates",
    "burma": "myanmar",
    "ceylon": "sri lanka",
    "persia": "iran",
    "siam": "thailand",
    "formosa": "taiwan",
    "rhodesia": "zimbabwe",
    "east pakistan": "bangladesh",
    "prc": "china",
    "rok": "south korea",
    "dprk": "north korea",
}

# Hindi transliterations of Indian states → English canonical
_HINDI_STATE_ALIASES: dict[str, str] = {
    "उत्तराखंड": "uttarakhand",
    "उत्तर प्रदेश": "uttar pradesh",
    "राजस्थान": "rajasthan",
    "महाराष्ट्र": "maharashtra",
    "मध्य प्रदेश": "madhya pradesh",
    "गुजरात": "gujarat",
    "कर्नाटक": "karnataka",
    "तमिलनाडु": "tamil nadu",
    "केरल": "kerala",
    "आंध्र प्रदेश": "andhra pradesh",
    "तेलंगाना": "telangana",
    "पश्चिम बंगाल": "west bengal",
    "बिहार": "bihar",
    "झारखंड": "jharkhand",
    "ओडिशा": "odisha",
    "छत्तीसगढ़": "chhattisgarh",
    "पंजाब": "punjab",
    "हरियाणा": "haryana",
    "हिमाचल प्रदेश": "himachal pradesh",
    "जम्मू और कश्मीर": "jammu and kashmir",
    "जम्मू कश्मीर": "jammu and kashmir",
    "दिल्ली": "delhi",
    "गोवा": "goa",
    "असम": "assam",
    "मेघालय": "meghalaya",
    "त्रिपुरा": "tripura",
    "मणिपुर": "manipur",
    "मिज़ोरम": "mizoram",
    "नागालैंड": "nagaland",
    "अरुणाचल प्रदेश": "arunachal pradesh",
    "सिक्किम": "sikkim",
    "लद्दाख": "ladakh",
}

# Merge all alias tables into one lookup
_ALL_ALIASES: dict[str, str] = {}
_ALL_ALIASES.update(_CITY_ALIASES)
_ALL_ALIASES.update(_COUNTRY_ALIASES)
# Hindi aliases use original script as key (not lowercased)
for hindi_key, eng_val in _HINDI_STATE_ALIASES.items():
    _ALL_ALIASES[hindi_key] = eng_val
    # Also add NFKD-normalized form
    nfkd = unicodedata.normalize("NFKD", hindi_key)
    if nfkd != hindi_key:
        _ALL_ALIASES[nfkd] = eng_val


def normalize_entity_text(text: str) -> str:
    """Normalize entity text for geocoding lookup.

    Steps:
    1. Strip whitespace
    2. Unicode NFKD normalization
    3. Check Hindi alias table (before lowercasing — Hindi is case-insensitive)
    4. Lowercase
    5. Strip leading "the "
    6. Check English alias table
    """
    if not text:
        return ""

    text = text.strip()
    if not text:
        return ""

    # NFKD normalization for consistent representation
    text = unicodedata.normalize("NFKD", text)

    # Check Hindi aliases before lowercasing (Devanagari has no case)
    if text in _ALL_ALIASES:
        return _ALL_ALIASES[text]

    # Lowercase for English
    lower = text.lower()

    # Strip "the " prefix
    if lower.startswith("the "):
        lower = lower[4:]

    # Check alias table
    if lower in _ALL_ALIASES:
        return _ALL_ALIASES[lower]

    return lower


# ---------------------------------------------------------------------------
# Geonamescache indices (loaded once at import)
# ---------------------------------------------------------------------------
_gc = geonamescache.GeonamesCache()

# Mapping, not dict: geonamescache yields TypedDicts, which are read-compatible
# with Mapping but not assignable to dict[str, Any]. Every read below is a
# lookup, so the covariant type is the accurate one.
_CITIES_BY_NAME: dict[str, Mapping[str, Any]] = {}
_COUNTRIES_BY_NAME: dict[str, Mapping[str, Any]] = {}
_CUSTOM_LOCATIONS: dict[str, tuple[float, float]] = {}


def _build_indices() -> None:
    for _key, city in _gc.get_cities().items():
        name_lower = city["name"].lower()
        existing = _CITIES_BY_NAME.get(name_lower)
        if existing is None or city.get("population", 0) > existing.get("population", 0):
            _CITIES_BY_NAME[name_lower] = city

    for _key, country in _gc.get_countries().items():
        name_lower = country["name"].lower()
        capital = country.get("capital", "")
        _COUNTRIES_BY_NAME[name_lower] = {"name": country["name"], "capital": capital}


def _load_custom_locations() -> None:
    # Find project root by uv.lock marker. AGENTS.md and pyproject.toml both
    # appear in subdirectories, so neither is safe as a root marker.
    project_root = Path(__file__).resolve().parent
    while project_root != project_root.parent:
        if (project_root / "uv.lock").exists():
            break
        project_root = project_root.parent

    candidates = [
        Path("/app/infra/configs/geocoder/custom_locations.json"),
        Path("/workspace/infra/configs/geocoder/custom_locations.json"),
        project_root / "infra" / "configs" / "geocoder" / "custom_locations.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                for name, coords in data.items():
                    _CUSTOM_LOCATIONS[name.lower()] = (float(coords[0]), float(coords[1]))
                log.info("geocoding.custom_locations_loaded", count=len(data), path=str(path))
                return
            except Exception as exc:
                log.warning("geocoding.custom_locations_error", path=str(path), error=str(exc))
    log.debug("geocoding.no_custom_locations_file")


_build_indices()
_load_custom_locations()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def geocode_and_store(
    entities: list[Any],
    db_pool: Any,
    redis: Any | None = None,
) -> int:
    """Geocode location entities and store results in DB + cache.

    Filters entities to LOCATION_ENTITY_TYPES, geocodes, upserts to
    geocoded_locations table, and caches in Redis.

    Returns count of newly geocoded locations.
    """
    from anveshak.analyst.geocoding_cache import geocode_cache_get, geocode_cache_set
    from anveshak.analyst.geocoding_db import upsert_geocoded_location

    location_entities = [e for e in entities if e.entity_type in LOCATION_ENTITY_TYPES]
    if not location_entities:
        return 0

    texts = [e.entity_text for e in location_entities]
    types = [e.entity_type for e in location_entities]

    # Check Redis cache first
    uncached_texts: list[str] = []
    uncached_types: list[str] = []
    cached_count = 0

    for text, etype in zip(texts, types):
        normalized = normalize_entity_text(text)
        if not normalized:
            continue
        if redis:
            cached = await geocode_cache_get(redis, normalized, etype)
            if cached is not None:
                cached_count += 1
                continue
        uncached_texts.append(text)
        uncached_types.append(etype)

    if not uncached_texts:
        log.debug("geocoding.all_cached", cached=cached_count)
        return cached_count

    # Geocode uncached entities
    results = geocode_entities(uncached_texts, uncached_types)

    # Store in DB + cache
    stored = 0
    for entry in results:
        try:
            await upsert_geocoded_location(
                db_pool,
                entity_text_normalized=entry["entity_text_normalized"],
                entity_type=entry["entity_type"],
                latitude=entry["latitude"],
                longitude=entry["longitude"],
                geocode_confidence=entry["geocode_confidence"],
                geocode_source=entry["geocode_source"],
            )
            if redis:
                await geocode_cache_set(
                    redis,
                    entry["entity_text_normalized"],
                    entry["entity_type"],
                    lat=entry["latitude"],
                    lon=entry["longitude"],
                    source=entry["geocode_source"],
                    confidence=entry["geocode_confidence"],
                )
            stored += 1
        except Exception:
            log.warning(
                "geocoding.store_failed",
                entity=entry["entity_text_normalized"],
                exc_info=True,
            )

    log.info(
        "geocoding.completed",
        total=len(texts),
        cached=cached_count,
        geocoded=stored,
        unresolved=len(uncached_texts) - len(results),
    )
    return stored


def geocode_entities(
    entity_texts: list[str],
    entity_types: list[str],
) -> list[dict[str, Any]]:
    """Geocode a list of entity texts, returning resolved locations.

    Returns list of dicts with: entity_text_normalized, entity_type,
    latitude, longitude, geocode_confidence, geocode_source.
    Unknown entities are silently skipped.
    """
    if not entity_texts:
        return []

    results: list[dict[str, Any]] = []
    for text, etype in zip(entity_texts, entity_types):
        normalized = normalize_entity_text(text)
        if not normalized:
            continue

        coords = _resolve_coordinates(normalized)
        if coords is None:
            log.debug("geocoding.unresolved", entity_text=text, normalized=normalized)
            continue

        lat, lon, source, confidence = coords
        results.append(
            {
                "entity_text_normalized": normalized,
                "entity_type": etype,
                "latitude": lat,
                "longitude": lon,
                "geocode_confidence": confidence,
                "geocode_source": source,
            }
        )

    return results


def _resolve_coordinates(
    normalized: str,
) -> tuple[float, float, str, float] | None:
    """Try to resolve normalized text to (lat, lon, source, confidence).

    Priority: custom overlay (1.0) → geonamescache cities (0.9) → countries (0.7).
    """
    if normalized in _CUSTOM_LOCATIONS:
        lat, lon = _CUSTOM_LOCATIONS[normalized]
        return lat, lon, "custom_overlay", 1.0

    if normalized in _CITIES_BY_NAME:
        city = _CITIES_BY_NAME[normalized]
        return float(city["latitude"]), float(city["longitude"]), "geonamescache", 0.9

    if normalized in _COUNTRIES_BY_NAME:
        capital = _COUNTRIES_BY_NAME[normalized].get("capital", "")
        capital_key = capital.lower()
        if capital_key in _CITIES_BY_NAME:
            city = _CITIES_BY_NAME[capital_key]
            return float(city["latitude"]), float(city["longitude"]), "geonamescache", 0.7
        log.debug("geocoding.country_no_capital", name=normalized, capital=capital)

    return None
