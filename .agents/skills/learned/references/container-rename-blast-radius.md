# Container Rename Blast Radius Checklist

## Pattern

Renaming a Docker Compose service touches 8+ files beyond compose.yml.
Missing any one causes silent failures (Prometheus stops scraping, alerts
reference dead services, health checks fail, k3s deploys break).

## Full Checklist

When renaming a service in `infra/compose.yml`, update ALL of:

1. **compose.yml** — service key, depends_on references from other services
2. **compose.*.yml overlays** — compose.vision.yml, compose.bridge.yml
3. **API settings.py** — default service URLs (e.g. `analyst_service_url`)
4. **Other service settings.py** — any service that references another by hostname
5. **Prometheus prometheus.yml** — `static_configs.targets` and `job_name`
6. **Prometheus alert rules** — `expr` job matchers and `description` log queries
7. **Grafana dashboards** — description text referencing container names
8. **Promtail config** — if using explicit service filters (usually auto-discovers)
9. **Makefile** — health checks, integration test `exec` targets, `download-models`
10. **k3s manifests** — Deployment names, Service names, labels, kustomization.yml
11. **k3s NetworkPolicy** — podSelector matchLabels for every renamed service

## Pitfall: Loki Log Queries in Alerts

Prometheus alert `description` fields often contain Loki log query examples like
`{service="analyst-scheduler"} |= "signal"`. These are documentation strings,
not evaluated by Prometheus — but analysts copy-paste them into Grafana.
Stale service names in these strings cause "no logs found" confusion.

## Pitfall: compose.bridge.yml Stale References

Override compose files reference services by name. If the base service is renamed
but the overlay still uses the old name, compose silently creates a NEW service
with no image/build — it just applies the environment overlay to nothing useful.
Always grep all compose*.yml files.

## Pitfall: init Container References

`depends_on: { analyst-init: service_completed_successfully }` — if you rename
the init container, the worker that depends on it will fail to start with
"service analyst-init is not running".

## Search Command

After any rename, run:
```bash
grep -r 'old-name' infra/ services/*/anveshak/*/settings.py Makefile --include='*.yml' --include='*.py' --include='*.json'
```
