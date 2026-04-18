# Compose Overlay — Core Feature Trap

## When to load: any task involving Docker Compose file structure, adding new services, or debugging "service unavailable" errors

---

### Problem

Putting a core user-facing feature (vision/deepfake detection) in a compose **overlay** file (`compose.vision.yml`) instead of the base `compose.yml` means `make up` silently skips it. Users see the feature in the UI but it always fails — the API returns 503, the frontend shows "service unavailable."

### When overlays are appropriate vs not

**Overlay (separate compose file):**
- GPU device reservations (nvidia runtime)
- Optional integrations (Drishti bridge)
- Development-only services (debug tools, profilers)
- Services that genuinely don't apply to all deployments

**Base compose (must always start):**
- Any service the UI exposes to the user
- Any service the API proxies to
- Any service with a health check in `make health`

### The trap

1. Vision overlay was created because "it's heavy (4GB RAM, ML models)"
2. Developer uses `make up` → everything works except deepfake
3. UI has an "Image Analysis" page that calls `/api/v1/vision/analyse`
4. API catches `httpx.HTTPError` → returns 503 → "Vision service unavailable"
5. User thinks the platform is broken; actual fix is `make up-vision`

### Fix

Move the service to base compose. Keep the overlay for **GPU-only additions** (nvidia device reservation). The memory cost is justified — if the feature exists in the UI, it must run with `make up`.

### Pattern: overlay ≠ optional

If a service is referenced by the API's environment (`VISION_SERVICE_URL`), it's not optional — it's a dependency. Dependencies go in the base compose file.

### Checklist when adding a new service

- [ ] Is there a UI page that calls it? → must be in base compose
- [ ] Does the API proxy to it? → must be in base compose
- [ ] Is it in `make health`? → must be in base compose
- [ ] Is it GPU-only? → base compose for CPU mode, overlay for GPU device reservation
