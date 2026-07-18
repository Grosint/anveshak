# Dockerfile Must COPY Shared Config Files

## Problem

Analyst service's `geocoding.py` loads `custom_locations.json` at import time. File exists on host at `infra/configs/geocoder/custom_locations.json`. API Dockerfile already COPYs it — but analyst Dockerfile didn't.

Container logs: `geocoding.no_custom_locations_file` (INFO, not ERROR) — feature silently disabled. 601 custom locations lost. Only geonamescache cities resolve.

## Solution

Add explicit COPY in each Dockerfile that needs the file:
```dockerfile
# Geocoder custom locations overlay (shared with reporter service)
COPY infra/configs/geocoder/custom_locations.json /workspace/infra/configs/geocoder/custom_locations.json
```

Python code adds container-specific path as candidate:
```python
candidates = [
    Path("/app/infra/configs/geocoder/custom_locations.json"),
    Path("/workspace/infra/configs/geocoder/custom_locations.json"),
    project_root / "infra" / "configs" / "geocoder" / "custom_locations.json",
]
```

## Rule

When a new service uses a shared config file:
1. Check if Dockerfile copies it — `grep custom_locations services/*/Dockerfile`
2. Add COPY if missing
3. Add container-aware path candidates in loader code
4. Verify with `docker compose exec <service> ls /path/to/file`

Silent failure: module loads, logs debug message, returns empty data. No crash, no error.

## See Also
- `rules/silent-failures.md` (silent feature disable)
- `learned/migration-not-visible-in-container.md` (same pattern: host files invisible in container)
