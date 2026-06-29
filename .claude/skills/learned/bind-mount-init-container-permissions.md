# Bind Mount Permissions for Init Containers + Observability

## Confidence: HIGH (crashed init containers in production 2026-06-29)

Docker bind mounts inherit host directory permissions. Containers running as non-root
(UID 1000, or tool-specific UIDs) get `PermissionError` on freshly created host dirs
(owned by root:root, mode 755).

## Init Containers (model downloaders)

`analyse-init` and `analyse-vision-init` download ML models to `/app/models`.
Container runs as UID 1000 but host dir `/data/models` is root-owned.

Fix: `chmod -R 777 /data/models /data/vision-models` before first run.
Init containers are one-shot downloaders — broad permissions acceptable.

## Observability Stack UIDs

Each tool runs as a specific UID inside its container:

| Tool | Container UID | Host chown command |
|------|--------------|-------------------|
| Prometheus | 65534 (nobody) | `chown -R 65534:65534 /data/prometheus` |
| Loki | 10001 | `chown -R 10001:10001 /data/loki` |
| Grafana | 472 | `chown -R 472:472 /data/grafana` |

Must set BEFORE first `docker compose up`.

## Rule

When switching from Docker named volumes to bind mounts (production overlay):
1. List every service with a volume mount
2. Check what UID the container process runs as (`docker inspect <image> --format='{{.Config.User}}'`)
3. Set host dir ownership to match
4. For init containers: use 777 (they write once and exit)

## See also
- `volume-mounted-models-silent-failure.md` — empty volume = silent 0.0 scores
