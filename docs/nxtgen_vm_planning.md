# NxtGen VM Planning

## Current: Single VM (Phase 1)

Single VM handles everything. Split only when client load demands it.

### Recommended Spec

| Resource | Spec |
|----------|------|
| vCPU | 8-16 |
| RAM | 32-64 GB |
| GPU | L4 24GB (preferred) or T4 16GB |
| Boot disk | 50 GB SSD |
| Data disk | 250 GB NVMe/SSD |
| OS | Ubuntu 22.04 or 24.04 |
| Network | 1 Gbps, static public IP |
| Ports | 22, 80, 443 (public); rest internal |

### VRAM Budget (L4 24GB)

| Model | VRAM |
|-------|------|
| Ollama qwen3:32b | ~22 GB |
| YOLOv8 medium | ~0.5 GB |
| CLIP | ~0.5 GB |
| Deepfake (DIRE) | ~0.3 GB |
| sentence-transformers | ~0.5 GB |
| **Peak total** | **~24 GB** |

If tight, use qwen3:14b (~11GB) or qwen2.5:14b (~10GB) for 12GB+ headroom.

### T4 Fallback (16GB VRAM)

Use qwen2.5:14b (~10GB). Vision models (~1.8GB). Fits with ~4GB headroom.
No qwen3:32b on T4.

### CPU-Only Fallback

Everything runs on CPU if no GPU available:
- Set `VISION_DEVICE=cpu`
- YOLO/CLIP: 5-10x slower but functional
- Ollama: ~2 tokens/sec (reports take 4-5 min instead of 12 sec)

---

## Future: Two VM Split (Phase 2 — only when needed)

Trigger: multiple concurrent clients, or GPU contention visible in monitoring.

```
VM 1: Core (CPU-only)              VM 2: GPU workloads
─────────────────────              ─────────────────────
nginx, frontend, API               Ollama (qwen3:32b)
PostgreSQL, Redis                   Vision (YOLO+CLIP+DIRE)
Scraper, Social workers             sentence-transformers
8 vCPU, 32GB, 250GB SSD            8 vCPU, 32GB + L4, 250GB SSD
```

Wire change: `OLLAMA_BASE_URL=http://<vm2-private-ip>:11434`
Vision services: move to VM 2 compose, expose via private network.

Requirements: same private VLAN, no public IP on VM 2.

### Three VM Split (Phase 3 — 5+ clients)

```
VM 1: Core       VM 2: Ollama       VM 3: Vision
CPU, 32GB        L4 GPU, 16GB       T4 GPU, 16GB
API/DB/Redis     qwen3:32b          YOLO+CLIP+DIRE+embeddings
```

---

## NxtGen Checklist

### Ask Before Signing

- [ ] GPU availability: T4 or L4? Dedicated or shared (vGPU)?
- [ ] Separate data volume mountable at `/data`?
- [ ] S3-compatible object storage? (backup scripts)
- [ ] Private VLAN between VMs? (for Phase 2)
- [ ] Static public IP included?
- [ ] MeitY empanelment? (government procurement)
- [ ] Data center location in India? Which city?
- [ ] Data sovereignty / ISO 27001 / SOC 2?
- [ ] SSH root access + console access?
- [ ] SLA / uptime guarantee?
- [ ] Reserved pricing (1yr) vs pay-as-you-go?
- [ ] NVIDIA driver support or self-install?
- [ ] RAM overcommit ratio?

### Migration Steps (from GCP)

1. Provision VM
2. Run `scripts/bootstrap-vm.sh`
3. Clone repo, copy `.env`, update domain
4. `docker compose -p anveshak --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d`
5. Restore from GCS backup OR seed fresh
6. Update DNS A record (anveshak.grosint.in → new IP)
7. `certbot --nginx -d anveshak.grosint.in`
8. Swap backup script from gsutil to rclone/s3cmd (~10 line change)

### Pricing Reference

- GCP T4 VM (16 vCPU, 60GB): ~₹50-80K/month
- NxtGen target: 40-60% less
- Volume play: each client deployment = one VM
