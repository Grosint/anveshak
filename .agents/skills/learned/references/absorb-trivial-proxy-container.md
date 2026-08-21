# Absorb Trivial Proxy Containers Into Gateway

## Pattern

When a container exists only to receive bytes, do trivial I/O, and return metadata
(no ML models, no heavy deps), absorb its logic into the API gateway instead of
proxying via httpx. Saves a full container + network hop.

## Criteria for Absorption

A container is absorb-able when ALL of:
1. No ML model loading (PyTorch, ONNX, spaCy, etc.)
2. No unique heavy dependencies the gateway doesn't already have
3. Core logic is < 30 lines (hash, write, classify, return)
4. Workers that consume the output are decoupled via ARQ queues (not via the absorbed service)

## Criteria to Keep Separate

Keep a container separate when ANY of:
1. It loads ML models (vision-worker: 6GB, analyst-worker: 6GB)
2. It has unique system deps (Playwright/Chromium, Telethon sessions)
3. It needs independent horizontal scaling
4. Different poll cadences or scheduling patterns

## Applied

- **vision container (4GB)**: received file uploads → hashed → wrote to disk → returned metadata.
  ~20 lines of logic. Absorbed into API gateway. Saved 4GB RAM + port 8003.
- **reporter container (512MB)**: CRUD routes were already duplicated in API gateway.
  PDF download added as FileResponse from shared volume. Saved 512MB + port 8005.
- Workers (vision-worker, reporter-worker) stayed separate — they do heavy work.

## Anti-Pattern

Don't absorb schedulers with different dependency trees (scraper has Playwright,
social has Telethon). Merging images bloats both. Different poll intervals
become harder to manage. Savings (~256MB) not worth the coupling.

## Checklist When Absorbing

1. Move logic into API route (replace httpx proxy with direct implementation)
2. Add volume mounts to API container in compose.yml
3. Add settings to API settings.py (media_storage_root, max_size, etc.)
4. Remove old service from compose.yml
5. Remove old service URL env var from API
6. Update Prometheus scrape targets (remove old job)
7. Update alert rules referencing old job/service names
8. Update Makefile health checks and test targets
9. Update k3s manifests + network policies
