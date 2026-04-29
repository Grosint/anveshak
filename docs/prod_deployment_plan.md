# Production Deployment Plan (k3s)

## Current State

### Dev Stack (Docker Compose) — COMPLETE
- `infra/compose.yml` — full 19-container stack, all healthy
- `infra/compose.vision.yml` — GPU overlay (NVIDIA passthrough)
- `infra/compose.bridge.yml` — optional Drishti integration
- Makefile targets: `make up`, `make down`, `make fresh`, `make backup`, `make restore`

### Production Stack (k3s) — ~35% COMPLETE

**Done:**
| Manifest | File | Notes |
|----------|------|-------|
| Namespace | `infra/k3s/namespace.yml` | `anveshak` namespace |
| Kustomization | `infra/k3s/kustomization.yml` | Orchestrator, common labels |
| Secrets | `infra/k3s/secrets-template.yml` | Manual inject via `kubectl create secret` |
| PostgreSQL | `infra/k3s/postgres.yml` | pgvector:pg16, 20Gi PVC, resource limits |
| Redis | `infra/k3s/redis.yml` | redis:7-alpine, 512Mi limit |
| API | `infra/k3s/api.yml` | Port 8000, health probes, env from secrets |
| Analyst | `infra/k3s/analyst.yml` | 4Gi request / 6Gi limit (NLP models) |

**Missing:**
| Service | Priority | Notes |
|---------|----------|-------|
| Ollama | HIGH | 8GB memory limit, model volume mount, health probe |
| Scraper + Worker | HIGH | Crawl4AI, needs outbound network access |
| Reporter + Worker | HIGH | Depends on Ollama, ARQ queue |
| Social | MEDIUM | Platform adapters, optional credentials |
| Vision + Worker | MEDIUM | Large memory, optional GPU node selector |
| Frontend | MEDIUM | Static React build, nginx sidecar or separate pod |
| Ingress | HIGH | External access for analysts (frontend + API) |
| Observability | LOW | Prometheus, Grafana, Loki — can defer to Helm charts |
| ConfigMap | MEDIUM | Non-secret env vars (model names, timeouts, feature flags) |
| NetworkPolicy | LOW | Restrict inter-pod communication |

---

## PostgreSQL Production Strategy

The current `postgres.yml` is a single pod with Recreate strategy — unacceptable for production (downtime on restart, no failover, no PITR).

### Recommended: CloudNativePG Operator

CloudNativePG runs entirely in-cluster, no cloud dependency. Fits sovereign/air-gap requirement.

**What it gives us:**
- Primary + 1 streaming replica (automatic failover)
- Continuous WAL archiving (point-in-time recovery)
- Scheduled full backups (pg_basebackup)
- Automatic minor-version upgrades
- Monitoring endpoints (Prometheus-compatible)
- Single CRD replaces our hand-written postgres.yml

**Manifest sketch:**
```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: anveshak-pg
  namespace: anveshak
spec:
  instances: 2                     # 1 primary + 1 standby
  imageName: ghcr.io/cloudnative-pg/postgresql:16

  postgresql:
    shared_preload_libraries:
      - vectors                    # pgvector extension
    parameters:
      max_connections: "200"
      shared_buffers: "512MB"
      effective_cache_size: "1536MB"

  storage:
    size: 50Gi                     # production: more headroom than dev 20Gi
    storageClass: local-path       # k3s default; swap for NFS/Longhorn in HA

  backup:
    barmanObjectStore:
      destinationPath: "s3://anveshak-backups/pg/"  # or local MinIO
      # For air-gap: use local MinIO instance inside cluster
      s3Credentials:
        accessKeyId:
          name: backup-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: backup-creds
          key: SECRET_ACCESS_KEY
    retentionPolicy: "30d"

  scheduledBackups:
    - name: daily-backup
      schedule: "0 2 * * *"        # 02:00 daily
      backupOwnerReference: self

  monitoring:
    enablePodMonitor: true         # Prometheus scraping

  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2"
```

**Alternative approaches (if CloudNativePG feels too heavy):**

| Approach | Pros | Cons |
|----------|------|------|
| CronJob pg_dump to PVC | Simple, no operator needed | No failover, no PITR, backup gap = data loss |
| Patroni + etcd | Battle-tested HA | Complex setup, overkill for single-node k3s |
| CloudNativePG | Best balance, CRD-native | Requires installing operator (one-time `kubectl apply`) |

**Decision:** Go with CloudNativePG. Install is one manifest. Fits air-gap (operator image can be pre-pulled).

### Backup Storage for Air-Gap

Since we can't use cloud S3, options:
1. **MinIO in-cluster** — S3-compatible object store, single pod, dedicated PVC
2. **Local PVC** — barman backup to a volume (simpler but less resilient)
3. **NFS mount** — external NAS mounted into cluster (best for real production)

Recommendation: MinIO for demo/eval tier, NFS mount for IAF production.

---

## Hardware Tiers (from hardware.md)

| Tier | GPU | RAM | Storage | Throughput |
|------|-----|-----|---------|-----------|
| CPU-only (dev) | None | 32GB | 512GB NVMe | ~50 articles/day |
| Demo/eval | RTX 3080 (10GB) | 32GB | 1TB NVMe | ~2K articles/day |
| IAF production | RTX 4090 (24GB) | 64GB | 2TB NVMe | ~10K articles/day |

### Resource Budget (k3s pods, IAF tier):

| Service | CPU Request | Memory Request | Memory Limit |
|---------|-------------|----------------|--------------|
| PostgreSQL (primary) | 500m | 1Gi | 2Gi |
| PostgreSQL (standby) | 500m | 1Gi | 2Gi |
| Redis | 100m | 128Mi | 512Mi |
| Ollama | 1000m | 4Gi | 8Gi |
| API | 200m | 256Mi | 512Mi |
| Scraper | 200m | 256Mi | 512Mi |
| Scraper Worker | 200m | 256Mi | 512Mi |
| Social | 200m | 256Mi | 512Mi |
| Analyst | 500m | 4Gi | 6Gi |
| Vision | 500m | 2Gi | 4Gi |
| Vision Worker | 500m | 2Gi | 4Gi |
| Reporter | 200m | 256Mi | 512Mi |
| Reporter Worker | 200m | 512Mi | 1Gi |
| Frontend | 100m | 128Mi | 256Mi |
| **TOTAL** | ~5000m | ~17Gi | ~31Gi |

Fits comfortably on 64GB/16-core IAF production machine with headroom for OS + GPU driver.

---

## Deployment Sequence (Production)

### Phase 1: Infrastructure
1. Install k3s on target machine
2. Install CloudNativePG operator
3. Deploy MinIO (or configure NFS) for backup storage
4. Deploy PostgreSQL Cluster (primary + standby)
5. Deploy Redis
6. Run migrations (k8s Job)
7. Deploy Ollama + pull models (init container or Job)

### Phase 2: Application Services
8. Deploy API
9. Deploy Scraper + Worker
10. Deploy Analyst
11. Deploy Social
12. Deploy Vision + Worker (with GPU nodeSelector if available)
13. Deploy Reporter + Worker

### Phase 3: Frontend & Access
14. Deploy Frontend (nginx serving React build)
15. Deploy Ingress (Traefik, k3s default) — TLS termination
16. Configure NetworkPolicies

### Phase 4: Observability
17. Deploy Prometheus (or use k3s monitoring stack)
18. Deploy Grafana with pre-built dashboards
19. Deploy Loki + Promtail
20. Verify all dashboards show data

### Phase 5: Validation
21. `make demo-check` equivalent (k8s Job)
22. Verify backup runs and can restore
23. Test failover (kill primary PG pod, verify standby promotes)
24. Load test at expected throughput

---

## Makefile Targets (existing)

```
make k3s-deploy      # kubectl apply -k infra/k3s/
make k3s-teardown    # kubectl delete namespace anveshak
make backup          # pg_dump + redis + media (Docker Compose)
make restore         # full restore from backup dir
make syscheck        # hardware validation script
```

### Targets to add:
```
make k3s-build       # build + tag images for k3s (importimage or local registry)
make k3s-backup      # trigger CloudNativePG on-demand backup
make k3s-restore     # restore from barman backup
make k3s-status      # kubectl get all -n anveshak
make k3s-logs SVC=x  # kubectl logs -n anveshak deploy/x --tail=100
```

---

## Open Questions

- [ ] Image registry: local k3s import (`k3s ctr images import`) or private registry?
- [ ] TLS certificates: self-signed, internal CA, or Let's Encrypt (if internet-facing)?
- [ ] Ingress: Traefik (k3s default) or nginx-ingress?
- [ ] Persistent storage: local-path (single node) or Longhorn (multi-node future)?
- [ ] Monitoring: reuse our Grafana dashboards as-is or adapt for k8s metrics?
- [ ] Backup retention: 30 days? Configurable per deployment?
- [ ] Should vision service always have GPU, or support mixed CPU/GPU scheduling?

---

## Files to Create (remaining k3s manifests)

```
infra/k3s/
├── kustomization.yml        ✅ exists
├── namespace.yml            ✅ exists
├── secrets-template.yml     ✅ exists
├── configmap.yml            ❌ TODO — non-secret env vars
├── postgres.yml             ✅ exists (replace with CloudNativePG Cluster CRD)
├── redis.yml                ✅ exists
├── ollama.yml               ❌ TODO
├── api.yml                  ✅ exists
├── scraper.yml              ❌ TODO
├── social.yml               ❌ TODO
├── analyst.yml              ✅ exists
├── vision.yml               ❌ TODO
├── reporter.yml             ❌ TODO
├── frontend.yml             ❌ TODO
├── ingress.yml              ❌ TODO
├── minio.yml                ❌ TODO (backup storage)
├── pg-cluster.yml           ❌ TODO (CloudNativePG CRD, replaces postgres.yml)
├── migrate-job.yml          ❌ TODO (one-shot migration)
└── pull-models-job.yml      ❌ TODO (ollama model pull)
```
