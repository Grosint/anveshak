# Anveshak — Maintenance & Support SLA
## Annual Maintenance Contract (AMC) Terms

**Document Classification:** Commercial — Shareable with prospective clients
**Prepared by:** Garud Research & Tech Private Limited
**Version:** 1.0
**Date:** May 2026

---

## Purpose

Address the #1 concern of MoD decision makers: "Who maintains this after delivery?" This document defines clear accountability, response times, and support tiers so the buying unit knows exactly what they get.

---

## Support Philosophy

> **"You operate. We maintain. Your team never needs an ML engineer."**

Anveshak is designed for intelligence officers, not IT staff. The AMC ensures the platform stays operational without requiring the unit to develop internal ML/DevOps capability.

---

## AMC Tiers

### Tier 1: Standard Support (Included in Year 1)

| Parameter | Commitment |
|-----------|-----------|
| **Coverage hours** | 0900–1800 IST, Mon–Sat |
| **Response time (Critical)** | 4 hours |
| **Response time (High)** | 8 hours |
| **Response time (Medium)** | 24 hours |
| **Resolution time (Critical)** | 24 hours |
| **Resolution time (High)** | 72 hours |
| **Software updates** | Quarterly releases (security patches within 48h) |
| **Source adapter updates** | Platform API changes handled within 7 days |
| **LLM model upgrades** | Included — tested & deployed quarterly |
| **Remote support** | Via secure VPN tunnel (unit-approved) |
| **On-site visits** | 2 per year (scheduled) |
| **Training sessions** | 1 initial (2 days) + 1 refresher (1 day) per year |

### Tier 2: Priority Support (AMC Premium)

| Parameter | Commitment |
|-----------|-----------|
| **Coverage hours** | 24/7 (dedicated WhatsApp/Signal hotline) |
| **Response time (Critical)** | 1 hour |
| **Response time (High)** | 4 hours |
| **Response time (Medium)** | 12 hours |
| **Resolution time (Critical)** | 8 hours |
| **Resolution time (High)** | 24 hours |
| **Software updates** | Monthly releases + hotfixes within 24h |
| **Source adapter updates** | Platform API changes handled within 48 hours |
| **LLM model upgrades** | Included — new models tested & deployed monthly |
| **Remote support** | Dedicated secure channel (always-on) |
| **On-site visits** | 4 per year + emergency visits within 48h |
| **Training sessions** | Quarterly (half-day each) + new joinee onboarding |
| **Dedicated account engineer** | Named individual, familiar with unit's configuration |

### Tier 3: Embedded Support (Mission-Critical Deployments)

| Parameter | Commitment |
|-----------|-----------|
| **Coverage hours** | 24/7 with 15-minute acknowledgement |
| **On-site presence** | Resident engineer (full-time or rotating weekly) |
| **Resolution time (Critical)** | 4 hours |
| **Uptime SLA** | 99.5% measured monthly |
| **Custom development** | Up to 40 hours/quarter of custom adapter/feature work |
| **Hardware health monitoring** | Proactive (Grafana alerts → our NOC → your unit informed) |
| **All Tier 2 benefits** | Included |

---

## Severity Definitions

| Severity | Definition | Example |
|----------|-----------|---------|
| **Critical (S1)** | Platform completely non-functional, no workaround | Database corruption, all services down |
| **High (S2)** | Major feature non-functional, workaround exists | Report generation failing, scraping works |
| **Medium (S3)** | Minor feature degraded, no operational impact | One social adapter rate-limited, others working |
| **Low (S4)** | Cosmetic or documentation issue | UI alignment, typo in report template |

---

## What's Included in AMC

### Software Maintenance

| Item | Frequency | Details |
|------|-----------|---------|
| Security patches | As needed (within 48h of CVE) | OS, Python, Node.js, Docker base images |
| Platform updates | Quarterly (Tier 1) / Monthly (Tier 2+) | New features, performance improvements |
| Source adapter fixes | Within 7 days of platform API change | Telegram, Reddit, X, Bluesky, RSS |
| LLM model refresh | Quarterly | Newer/better models tested and deployed |
| Database maintenance | Monthly | Vacuum, index rebuild, backup verification |
| Certificate renewal | As needed | TLS certs for internal services |

### Operational Support

| Item | Details |
|------|---------|
| New topic configuration | Help analyst set up new monitoring topics |
| Source onboarding | Add new Telegram channels, RSS feeds, social handles |
| Threshold tuning | Adjust signal thresholds based on operational feedback |
| Report template customisation | Modify PDF/GIS output format per unit requirements |
| User account management | Add/remove analyst accounts, reset credentials |
| Backup & recovery | Scheduled backups, tested recovery procedures |

### Training & Knowledge Transfer

| Item | Details |
|------|---------|
| Initial training | 2-day hands-on workshop for analyst team (up to 10 people) |
| Refresher training | Annual (Tier 1) / Quarterly (Tier 2+) |
| New joinee onboarding | 4-hour session for new analysts joining the unit |
| Admin training | Separate session for unit IT staff (Docker, backups, logs) |
| Written documentation | Deployment runbook, analyst walkthrough, troubleshooting guide |

---

## What's NOT Included in AMC

| Item | Why | How to Get It |
|------|-----|---------------|
| Hardware procurement | Unit responsibility | We provide specs, you procure |
| Network configuration | Unit IT / NIC responsibility | We provide requirements |
| Internet connectivity | Unit responsibility | Minimum: 10 Mbps for scraping |
| Custom development (beyond Tier 3 quota) | Scoped separately | SOW + quote per engagement |
| Integration with classified systems | Requires separate clearance process | Separate contract |
| Physical security of hardware | Unit responsibility | We advise on placement |

---

## Hardware Requirements (Unit Provides)

### Minimum (up to 20 topics, 200 sources)

| Component | Specification |
|-----------|--------------|
| CPU | 8-core x86_64 (Intel Xeon / AMD EPYC) |
| RAM | 32 GB DDR4 |
| Storage | 500 GB NVMe SSD |
| GPU | Not required (CPU inference) |
| Network | 10 Mbps internet (for scraping) |
| OS | Ubuntu 22.04 LTS / RHEL 9 |

### Recommended (up to 50 topics, 500 sources, faster inference)

| Component | Specification |
|-----------|--------------|
| CPU | 16-core x86_64 |
| RAM | 64 GB DDR4 |
| Storage | 1 TB NVMe SSD |
| GPU | NVIDIA RTX 4090 (24 GB VRAM) |
| Network | 50 Mbps internet |
| OS | Ubuntu 22.04 LTS / RHEL 9 |

### High-Performance (Corps-level, 100+ topics)

| Component | Specification |
|-----------|--------------|
| CPU | 32-core x86_64 |
| RAM | 128 GB DDR4 |
| Storage | 2 TB NVMe SSD (RAID) |
| GPU | 2x NVIDIA A100 (80 GB VRAM) |
| Network | 100 Mbps internet |
| OS | Ubuntu 22.04 LTS / RHEL 9 |
| Deployment | k3s cluster (3-node recommended) |

---

## Uptime & Recovery

| Metric | Tier 1 | Tier 2 | Tier 3 |
|--------|--------|--------|--------|
| Target uptime | 95% | 99% | 99.5% |
| Planned maintenance window | Sunday 0200–0600 IST | Sunday 0200–0400 IST | Coordinated with unit ops |
| Backup frequency | Daily | Every 6 hours | Every 2 hours |
| Recovery Point Objective (RPO) | 24 hours | 6 hours | 2 hours |
| Recovery Time Objective (RTO) | 8 hours | 4 hours | 2 hours |
| Disaster recovery test | Annual | Quarterly | Monthly |

---

## Escalation Matrix

| Level | Contact | Response |
|-------|---------|----------|
| L1 | Support engineer (phone/Signal) | First response, triage, known-fix application |
| L2 | Senior engineer (remote) | Root cause analysis, patch development |
| L3 | CTO / Architect (on-site if needed) | Architecture-level fixes, emergency deployment |
| Management | Account manager | SLA breach escalation, commercial issues |

---

## Pricing Structure

Anveshak is priced as an **annual subscription** (not one-time license). Support is included in the subscription tier:

| Tier | What's Included | Typical Range |
|------|----------------|---------------|
| Tier 1 (Standard) | Platform subscription + standard support | ₹___ Lakh/year |
| Tier 2 (Priority) | Platform subscription + priority 24/7 support | ₹___ Lakh/year |
| Tier 3 (Embedded) | Platform subscription + dedicated on-site engineer | ₹___ Lakh/year |

Multi-year discount: 10% off for 3-year commitment, 15% off for 5-year.

---

## Key Assurances for Decision Makers

1. **No ML engineers needed at unit** — we handle all model updates, retraining, and optimization remotely
2. **No internet required for core operation** — system operates air-gapped; internet only needed for scraping external sources
3. **Source code escrow available** — if Garud ceases operations, unit receives full source code and documentation
4. **Indian company, Indian engineers** — no foreign nationals access your deployment
5. **Technology refresh included** — as better LLM models release, we test and deploy them at no extra cost within AMC
6. **Knowledge transfer guaranteed** — at contract end, full documentation + training ensures unit can operate independently if needed

---

## Contract Terms

| Term | Details |
|------|---------|
| AMC start date | Day after warranty period (Year 1 included in license) |
| Renewal | Annual, with 60-day advance notice for non-renewal |
| Price revision | Maximum 8% annual increase, locked for multi-year |
| Termination | 90-day notice, with knowledge transfer obligation |
| Governing law | Indian law, jurisdiction: Delhi |
| Dispute resolution | Arbitration per Arbitration & Conciliation Act, 1996 |

---

**Document maintained by:** Garud Research & Tech Pvt Ltd
**Last updated:** May 2026
