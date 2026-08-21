# GCP GPU Quota — Two-Layer Meta-Quota + Zone Exhaustion

## Confidence: HIGH (blocked production deploy for hours, 2026-06-29)

GCP has TWO layers of GPU quota. Both must be >= 1 to create a GPU VM.

| Layer | Metric | Default | Check Command |
|-------|--------|---------|---------------|
| Per-region | `NVIDIA_T4_GPUS` | 1 | `gcloud compute regions describe REGION --format=json` |
| Global | `GPUS_ALL_REGIONS` | **0** | Same command, look for GPUS_ALL_REGIONS |

Per-region quota of 1 looks fine but global quota of 0 blocks everything.
`min(regional=1, global=0) = 0` → "Quota GPUS_ALL_REGIONS exceeded. Limit: 0.0"

## Fix

Request `GPUS_ALL_REGIONS` increase FIRST. Takes 24-48h for approval.
Contact GCP rep directly if you have one — faster than console request.

## Zone Exhaustion

Even with quota, specific zones run out of GPU capacity:
`ZONE_RESOURCE_POOL_EXHAUSTED` — no T4s available in that zone.

Fix sequence:
1. Try all zones in region (asia-south1-a, -b, -c)
2. Try L4 instead of T4 (different machine family, often more available)
3. Try different region (asia-south2)

## Admin Commands — Local Not VM

VM service account has limited scopes. These fail on VM:
- `gcloud storage buckets create` → needs storage.buckets.create
- `gcloud compute resource-policies create` → needs compute admin scope
- Any IAM changes

Run all admin GCP commands from local machine with owner access.
VM only runs Docker + application + backup scripts.
