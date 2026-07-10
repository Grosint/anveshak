# Anveshak Intelligence Appliance — Product Strategy

## Core Insight

Indian government buys hardware, not software. Sell a box, bundle software.
"₹10L hardware purchase" clears finance. "₹3L/year software subscription" gets stuck.

## Product Tiers

| SKU | Hardware | Capability | Sell Price | Cost | Margin |
|-----|----------|-----------|-----------|------|--------|
| **AIA-100** | Mini PC, no GPU | Web scraping + NLP + reports (CPU mode) | ₹5L | ~₹1.5L | ~70% |
| **AIA-200** | Custom build + RTX 4060 Ti 16GB | Full stack + vision + fast LLM | ₹10L | ~₹2L | ~80% |
| **AIA-500** | Rack server + L4/T4 | Full stack + multi-user + video analysis | ₹25L | ~₹5-6L | ~76% |

## Hardware Specs

### AIA-100 (CPU-only, entry level)

- Intel i5/i7 or AMD Ryzen 7 mini PC
- 32-64GB DDR5 RAM
- 1-2TB NVMe SSD
- No GPU
- `VISION_DEVICE=cpu`, `OLLAMA_MODEL=qwen3:8b`
- Use case: single analyst, text-only OSINT, web scraping + reports

### AIA-200 (GPU, recommended)

Custom x86 build:

| Component | Spec | Cost |
|-----------|------|------|
| CPU | Intel i7-14700 / AMD Ryzen 7 7700X | ₹35,000 |
| GPU | RTX 4060 Ti 16GB | ₹45,000 |
| RAM | 64GB DDR5 | ₹15,000 |
| Storage | 2TB NVMe SSD | ₹12,000 |
| PSU | 750W 80+ Gold | ₹8,000 |
| Case | Server/tower case | ₹5,000 |
| Motherboard | B760/X670 | ₹15,000 |
| **Total** | | **~₹1,35,000** |

- `VISION_DEVICE=cuda`, `OLLAMA_MODEL=qwen3:14b`
- Full stack: scraping + NLP + vision + LLM reports
- Use case: 1-3 analysts, full OSINT capability

### AIA-500 (Rack server, enterprise)

- Dell PowerEdge R760xs / Supermicro equivalent
- 16-32 vCPU, 128GB RAM
- NVIDIA L4 24GB or T4 16GB
- 4TB RAID storage
- `OLLAMA_MODEL=qwen3:32b`
- Use case: 5+ analysts, heavy video analysis, multi-topic monitoring

## Why x86 Custom Build, Not Jetson

| Factor | Jetson AGX Orin | Custom x86 + RTX |
|--------|----------------|-------------------|
| Code changes | Many (ARM Docker rebuild) | **Zero** |
| Docker images | All need rebuild | **Use production images** |
| Performance | 3-4x slower | **Same as cloud** |
| GPU VRAM | Shared with system RAM | **Dedicated** |
| Repairability | Proprietary board | **Off-the-shelf parts** |
| India availability | Import, long lead | **Buy today** |
| Equivalent price | ₹1.5L (64GB Orin) | **₹1.35L (RTX 4060 Ti)** |

Jetson only makes sense for tactical/field deployment where size matters.

## Procurement Quote Template

```
ANVESHAK INTELLIGENCE APPLIANCE — AIA-200

1. Hardware Unit                                    ₹8,00,000
   - Intel Core i7 Workstation
   - 64GB ECC RAM
   - NVIDIA GPU Accelerator (16GB VRAM)
   - 2TB NVMe Storage
   - Pre-loaded Anveshak AI-OSINT Suite

2. Installation & Commissioning                     ₹1,00,000
   - On-site deployment
   - Network configuration
   - Source onboarding (up to 50 sources)

3. Training (5 days, on-site)                       ₹1,00,000
   - Analyst workbench training
   - Source management
   - Report generation
   - Basic troubleshooting

4. Annual Maintenance Contract (Year 1 included)    Included

   TOTAL:                                          ₹10,00,000

5. AMC Year 2 onwards:                             ₹3,00,000/year
   - Software updates & model upgrades
   - Remote support (business hours)
   - Hardware warranty pass-through
```

## Revenue Model

- Hardware sale: one-time ₹5-25L (covers hardware cost + deployment)
- AMC: ₹2-5L/year recurring (pure margin — software updates + remote support)
- Training: ₹1L per engagement (optional repeat)

## Deployment Workflow

1. Assemble/procure hardware (1-2 weeks)
2. Install Ubuntu 22.04/24.04
3. Run `scripts/bootstrap-vm.sh` (installs Docker, NVIDIA drivers, firewall)
4. Clone repo, configure `.env`
5. `docker compose -p anveshak --env-file .env -f infra/compose.yml up -d`
6. Run migrations + seed data
7. Ship to client site
8. On-site: plug in power + LAN, verify health, train analysts

## Software Additions Needed

1. **First-boot wizard** — browser-based setup (org name, admin account, initial sources)
2. **Hardware health dashboard** — CPU temp, GPU util, disk space, service status
3. **Auto-update mechanism** — admin panel trigger or USB-based update
4. **Branding** — boot splash, login page, case label/sticker

Estimate: 2-3 days development on top of current codebase.

## Assembly Partners (India)

- Local system integrators — assemble to spec, apply branding
- Jetwing (Bangalore) — custom GPU servers
- Acer/Wipro — white-label workstations (brand name for tenders)
- BEL — defence credibility, system integrator partnership

## Jetson as Future "Tactical Edition"

Reserve for specific use case: air-gapped field deployment, vehicle-mounted, drone ground station.
Requires ARM Docker image rebuild effort. Only pursue when a contract demands it.
AGX Orin 64GB (₹1.5L) with stripped stack (no NLLB, smaller LLM).
