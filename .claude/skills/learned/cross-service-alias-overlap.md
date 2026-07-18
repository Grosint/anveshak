# Cross-Service Alias Table Overlap

## Problem

Three separate alias tables exist for location normalization:
1. `services/analyst/anveshak/analyst/geocoding.py` — `_ALL_ALIASES` (city + country + Hindi state aliases)
2. `services/api/anveshak/api/routes/intelligence.py` — `_LOCATION_ALIASES` (US→united states, Bombay→mumbai)
3. `services/reporter/anveshak/reporter/geocoder.py` — no aliases (geonamescache only)

When frontend switched from v1 (`location-map`) to v2 (`location-map-v2`), v1's alias logic (`_normalize_location`) became dead code but wasn't removed.

## Rule

When building a new service-level module that replaces functionality from another service:
1. Document which old code becomes dead (in implementation notes)
2. Plan removal as explicit task (don't leave orphaned code)
3. If both services need aliases, extract to SDK shared module (not duplicate)

In Anveshak: services are isolated uv workspace packages. Analyst can't import from API or reporter. Shared code → `sdk/anveshak-sdk/`. But aliases are deployment-specific (not worth SDK extraction for ~40 lines).

## Current State

v1 endpoint + its alias code still in `intelligence.py`. Frontend uses v2. Remove v1 when v2 validated in production.

## See Also
- `rules/dependency-patterns.md` (SDK: no DB/ARQ dependencies)
