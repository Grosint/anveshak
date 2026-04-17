# Anveshak & Drishti — Pricing Strategy
## Garud Research & Tech Private Limited

**Created:** 2026-04-17
**Purpose:** Pricing model for Anveshak (standalone), Drishti (standalone), and combined offering
**Classification:** Internal — Do not share externally without sanitisation

---

## Executive Summary

Anveshak is priced as a **sovereign OSINT platform** competing against SaaS-first tools like Recorded Future ($70K–$500K/yr) and Babel Street (~$5,400/seat), but with an on-prem sovereignty premium. Drishti is priced as a **cross-domain fusion platform** competing against Palantir Gotham ($5M+/yr) and Quantexa ($500K–$5M/yr), but at Indian defence budget-appropriate levels.

**Pricing Ratio: Drishti = 2.0–2.5x Anveshak**

> **Note on the 1.8x floor:** The user's instinct that Drishti should be priced significantly higher (≥1.8x) is correct and conservative. Based on market data, **2.0–2.5x is more defensible** because:
> 1. Entity resolution is an order-of-magnitude harder problem than topic monitoring (NP-hard graph matching vs. stream processing)
> 2. Drishti requires 3x more infrastructure (Redpanda cluster, AGE graph DB, Vault, Keycloak) — operational cost to customer is higher
> 3. Market precedent: fusion platforms (Palantir, Quantexa) are priced 10–100x above OSINT tools (Recorded Future, Maltego) — a 2–2.5x ratio is actually very competitive
> 4. Strategic intelligence (Drishti) is consumed by command-level decision makers; tactical OSINT (Anveshak) by wing-level analysts — willingness-to-pay scales with decision authority
> 5. Drishti serves multi-agency deployments (5+ wings/units) vs. Anveshak single-wing — the buyer is a directorate, not a wing
>
> **If you prefer 1.8x,** it works as a market-entry price to drive Drishti adoption, but you'd be underpricing relative to complexity and value. I'd recommend starting at 2x and using 1.8x only as a negotiation floor.

---

## Market Benchmarks

### OSINT Platforms (Anveshak's Competitive Set)

| Platform | Annual Price | Model | Deployment |
|----------|-------------|-------|------------|
| Recorded Future | $27K–$500K (median $70K) | Per-module + seats | SaaS |
| Babel Street (Babel X) | ~$5,400/seat (FBI: 5,000 seats = $27M/5yr) | Per-seat, multi-year | SaaS + on-prem |
| Flashpoint Ignite | $100K–$300K | Tiered subscription | SaaS |
| Maltego | €3,000–€7,500/yr (pro) | Per-seat | Desktop + server |
| DigitalStakeout | $9K–$51K/yr | Per-entity monitored | SaaS |
| Signal (getsignal) | $35K–$60K/yr | Organisation-wide | SaaS |
| Cobwebs Technologies | Custom (govt-focused) | Platform license | On-prem + cloud |

**Key insight:** No single competitor offers Anveshak's full stack (web + social + vision + deepfake + sovereign LLM reports + credibility audit). Customers typically stitch 2–3 tools at $150K–$500K combined.

### Fusion / Entity Resolution Platforms (Drishti's Competitive Set)

| Platform | Annual Price | Model |
|----------|-------------|-------|
| Palantir Gotham/Foundry | $5M–$100M+ (top 20 clients avg $64.6M/yr) | Multi-year deployment |
| Quantexa | $500K–$5M+ | Enterprise license |
| Senzing | Free tier (250K records); production per-record | Usage-based |
| BAE Systems (GEOINT) | $36M–$70M/yr equivalent | Multi-year programme |

**Key insight:** The gap between OSINT tools ($50K–$500K) and fusion platforms ($5M–$100M) is enormous. Drishti sits in the whitespace: fusion-level capability at Indian defence budget-appropriate pricing.

### Indian Defence Software Context

| Reference Point | Value |
|-----------------|-------|
| iDEX ADITI per-project grant | Up to ₹25 crore |
| iDEX average procurement order | ~₹55–60 crore |
| GeM software purchases | ₹5–50 lakh/yr (COTS tools) |
| Custom intelligence platforms (iDEX scale) | ₹10–100 crore total contract |
| India defence budget 2026-27 | ₹7.85 lakh crore |
| DRDO allocation | ₹29,100 crore |

---

## Understanding the Tiers: Wing → Command → Enterprise

### Who Is the Buyer?

| | **Wing** | **Command** | **Enterprise** |
|---|---|---|---|
| **Buyer** | Single IAF wing intelligence cell | Regional command / directorate | Air HQ / multi-command |
| **Decision maker** | Wing Commander (intelligence) | Air Officer Commanding | ACAS (Ops/Intel) or equivalent |
| **Scale** | 1 unit, 1 location | 1 unit, full capability | Up to 5 locations, centralised oversight |
| **Analysts** | 5 | 15 | 50 |
| **Topics** | 20 | 50 | Unlimited |
| **Targets (POI)** | — | 50 | 200 |

### What Modules Are Included?

| Module | Wing | Command | Enterprise |
|--------|:----:|:-------:|:----------:|
| M1 — Source Credibility Engine | ✅ | ✅ | ✅ |
| M2 — Open-Web Analysis + NLP | ✅ | ✅ | ✅ |
| M3 — Social Media Monitoring | ✅ | ✅ | ✅ |
| M4 — Vision + Deepfake Detection | ❌ | ✅ | ✅ |
| M5 — LLM Report Generation | ✅ | ✅ | ✅ |
| M6 — Target-Centric Monitoring | ❌ | ✅ | ✅ |
| Multi-site deployment | ❌ | ❌ | ✅ (up to 5) |
| Training programme included | ❌ | ❌ | ✅ (40 hrs) |

### Why This Tiering?

- **Wing** is the **land deal** — gets Anveshak inside the door at low risk. No GPU required, no vision, no target monitoring. Prove value with web + social + reports.
- **Command** is the **real product** — everything included. This is what we pitch to every serious buyer. GPU required but it's ₹3–4L (rounding error on defence budgets).
- **Enterprise** is **Command × 5 sites** — for when a directorate wants to deploy across multiple wings with centralised observability. The 40-hour training programme is included because at this scale, institutional adoption matters.

### Typical Use Cases Per Tier

| Tier | Example Use Case |
|------|-----------------|
| **Wing** | "Monitor Pakistan Twitter narratives and Chinese military forums for our wing. Generate weekly briefs." |
| **Command** | "Full OSINT + track 50 POIs across Telegram/X + detect deepfake imagery + behavioural anomaly alerts for our command." |
| **Enterprise** | "Deploy at 5 wings across Western Air Command. I see consolidated signals and reports from Air HQ." |

---

## Infrastructure & Hardware: What's Included, What's Not

### Software License = Software Only

**All prices in this document are software license fees. Hardware is customer-provided.**

### Why Hardware Is Separate

1. **Defence buyers prefer it** — they procure hardware through DGS&D/GeM channels, often at negotiated rates
2. **Existing IT infra** — many wings have servers allocated but underutilised
3. **GeM L1 clarity** — bundling hardware inflates the software price, making L1 comparison harder against SaaS competitors
4. **Clean renewals** — hardware depreciates (3–5 year cycle), software doesn't. Separating them keeps Year 2+ renewal pricing clean

### Hardware Requirements Per Tier

| Tier | Minimum Hardware | Recommended Hardware | Approx. Cost |
|------|-----------------|---------------------|--------------|
| **Wing** | 16-core CPU, 32GB RAM, 512GB NVMe | Same (CPU-only is sufficient) | **₹80K–1.5L** |
| **Command** | 16-core CPU, 64GB RAM, 1TB NVMe, RTX 4090 (24GB) | Same + 2TB NVMe for media storage | **₹3–4L** |
| **Enterprise** | 5× Command-spec servers + network switch | Same + central observability server | **₹15–20L** |

**Key point:** Hardware cost is 0.5–2% of the software license — a rounding error for defence procurement.

### All-In Pricing (Software + Hardware + Services)

For buyers who want one number:

#### Anveshak — All-In Year 1

| Component | Wing | Command | Enterprise |
|-----------|------|---------|------------|
| Software license | ₹50L | ₹1.5Cr | ₹4Cr |
| Hardware (customer-procured) | ₹1.5L | ₹4L | ₹20L |
| Deployment engineering | ₹2L (remote) | ₹5L (on-site, 1 week) | ₹10L (on-site, 2 weeks) |
| GPU consultation + setup | — | ₹3L | ₹3L (per site) |
| Training | ₹5L (optional) | ₹5L (optional) | Included |
| **Year 1 Total** | **₹58.5L** | **₹1.67Cr** | **₹4.48Cr** |
| **Year 2+ Renewal** | **₹50L/yr** | **₹1.5Cr/yr** | **₹4Cr/yr** |

#### Drishti — All-In Year 1

| Component | Directorate | Joint Command | Strategic |
|-----------|-------------|---------------|----------|
| Software license | ₹3Cr | ₹7Cr | ₹15Cr |
| Hardware (3–5 node cluster) | ₹12–20L | ₹25–40L | ₹50L–1Cr |
| Deployment engineering | ₹10L (2 weeks on-site) | ₹20L (4 weeks) | ₹40L (8 weeks) |
| Keycloak SSO setup | ₹5L | ₹5L | Included |
| Classified network hardening | — | ₹20L (if needed) | Included |
| **Year 1 Total** | **₹3.27–3.35Cr** | **₹7.7–7.85Cr** | **₹16–16.5Cr** |
| **Year 2+ Renewal** | **₹3Cr/yr** | **₹7Cr/yr** | **₹15Cr/yr** |

#### Anveshak + Drishti Bundle — All-In Year 1

| Bundle | Software (bundled) | Hardware + Services | Year 1 Total | Year 2+ |
|--------|-------------------|--------------------|--------------| --------|
| **Command + Directorate** | ₹3.75Cr | ₹40L | **₹4.15Cr** | **₹3.75Cr/yr** |
| **Enterprise + Joint** | ₹9Cr | ₹85L | **₹9.85Cr** | **₹9Cr/yr** |
| **Full Stack** | ₹15Cr | ₹1.5Cr | **₹16.5Cr** | **₹15Cr/yr** |

### Infrastructure Responsibility Matrix

| Component | Who Provides | Who Manages | Notes |
|-----------|-------------|-------------|-------|
| Server hardware | Customer | Customer IT | We provide specs, customer procures via GeM/DGS&D |
| GPU cards (RTX 4090) | Customer | Garud (initial setup) | We configure, benchmark, optimise |
| Network (LAN/WAN) | Customer | Customer IT | Standard 1Gbps sufficient |
| Docker/k3s runtime | Garud (deployed) | Garud (maintained) | Included in license |
| Anveshak software | Garud | Garud | Updates included in license |
| Ollama + ML models | Garud (deployed) | Garud | Model updates included |
| X/Twitter API costs | Customer (direct) | Garud (monitoring) | Customer buys API credits; we manage spend caps |
| Electricity / cooling | Customer | Customer | GPU server draws ~500W under load |
| Physical security | Customer | Customer | Standard server room |

---

## Pricing Model: Anveshak (Standalone)

### Pricing Dimensions

| Dimension | Metric | Rationale |
|-----------|--------|-----------|
| **Primary:** Deployment license | Per-installation, annual | Defence buyers prefer predictable annual costs; matches GeM procurement |
| **Secondary:** Analyst seats | Per-seat tier (5/15/50) | Scales with team size; comparable to Babel Street model |
| **Optional:** Module add-ons | Vision (M4) as separate tier | Vision requires GPU hardware; not all buyers need deepfake |
| **Not recommended:** Per-entity or per-API-call | — | Creates unpredictable costs; bad for defence procurement |

### Anveshak Pricing Tiers

#### Tier 1: Wing (Single Unit Deployment)

| Component | Specification |
|-----------|--------------|
| Analysts | Up to 5 concurrent |
| Modules | M1 (credibility) + M2 (web + NLP) + M3 (social) + M5 (reports) |
| Topics | Up to 20 monitored topics |
| Hardware | Customer-provided (CPU-only capable, GPU recommended) |
| Deployment | Single-machine Docker Compose / k3s |
| Support | Email + remote, 5×8 business hours |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹50 lakh** | **₹42 lakh** (16% saving) |
| **$ (USD equiv.)** | ~$60,000 | ~$50,000 |

**Positioning:** Below Recorded Future median ($70K), above Maltego Enterprise. Justified by sovereignty + full-stack.

#### Tier 2: Command (Multi-Unit / Full Capability)

| Component | Specification |
|-----------|--------------|
| Analysts | Up to 15 concurrent |
| Modules | M1 + M2 + M3 + M4 (vision/deepfake) + M5 + M6 (target monitoring) |
| Topics | Up to 50 monitored topics |
| Targets (POI) | Up to 50 persons of interest |
| Hardware | Customer-provided (GPU required for vision + target monitoring at scale) |
| Deployment | k3s production with observability stack |
| Support | Dedicated Slack/Teams channel, 5×12 |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹1.5 crore** | **₹1.25 crore** (17% saving) |
| **$ (USD equiv.)** | ~$180,000 | ~$150,000 |

**Positioning:** Competitive with Recorded Future enterprise ($250K–$500K) at significantly lower price, but with sovereign on-prem + vision + target monitoring (none offer this combo).

#### Tier 3: Enterprise (Multi-Site / Strategic)

| Component | Specification |
|-----------|--------------|
| Analysts | Up to 50 concurrent |
| Modules | All modules (M1–M6) |
| Topics | Unlimited |
| Targets (POI) | Up to 200 persons of interest |
| Multi-site | Up to 5 installations (same organisation) |
| Hardware | Customer-provided (GPU per site) |
| Deployment | k3s with federated observability |
| Support | On-site engineering (2 visits/yr), dedicated engineer, 7×12 |
| Training | Included: 40-hour analyst training programme |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹4 crore** | **₹3.5 crore** (12.5% saving) |
| **$ (USD equiv.)** | ~$480,000 | ~$420,000 |

**Positioning:** Below Flashpoint enterprise ($500K+), dramatically below Palantir ($5M+). Multi-site license is the key differentiator — 5 wings for the price of one Palantir seat.

### Anveshak Add-Ons (à la carte)

| Add-On | Annual Price | Notes |
|--------|-------------|-------|
| Additional analyst seats (per 5-pack) | ₹8 lakh | Volume discount at 25+ |
| X/Twitter API budget (per ₹1L API credits) | ₹1.5 lakh | Marked up from direct API cost to cover adapter maintenance |
| GPU hardware consultation + setup | ₹3 lakh (one-time) | RTX 4090 config, model optimisation, benchmark |
| Custom source adapter development | ₹5–10 lakh (one-time) | New platform integration (e.g., WeChat, VK) |
| Defence object detection fine-tuning | ₹8 lakh (one-time) | Custom YOLO model trained on customer-provided imagery |
| On-site deployment engineering | ₹2 lakh/visit | 3-day on-site, travel included (India) |
| Extended support (7×24 with SLA) | ₹12 lakh/yr add-on | 4-hour response SLA |

---

## Pricing Model: Drishti (Standalone)

### Why Drishti Commands a Premium

| Factor | Anveshak | Drishti | Price Implication |
|--------|----------|---------|-------------------|
| **Problem complexity** | Stream processing (O(n)) | Entity resolution (NP-hard graph matching) | 2x+ engineering value |
| **Infrastructure** | PostgreSQL + Redis + Ollama | + Redpanda cluster + AGE graph DB + Vault + Keycloak | 2–3x infra cost |
| **Deployment** | Single machine | Multi-node distributed | Higher ops overhead |
| **Buyer level** | Wing intelligence officer | Directorate / joint command | Higher budget authority |
| **Decision impact** | Tactical (hours/days) | Strategic (weeks/months) | Higher value of correct decisions |
| **Data sensitivity** | Open-source only | OSINT + classified fusion | Higher compliance burden |
| **Alternative cost** | 2–3 OSINT SaaS tools ($200K) | Palantir ($5M+) or manual fusion | Much higher displacement value |

### Drishti Pricing Tiers

#### Tier 1: Directorate (Single Command)

| Component | Specification |
|-----------|--------------|
| Analysts | Up to 10 concurrent |
| Entity resolution | Up to 500K entity records |
| Graph queries | Unlimited |
| Anveshak feeds | Up to 3 Anveshak instances bridged |
| Infrastructure | Customer-provided (3-node minimum for HA) |
| Support | Dedicated channel, 5×12 |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹3 crore** | **₹2.5 crore** (17% saving) |
| **$ (USD equiv.)** | ~$360,000 | ~$300,000 |

**Ratio to Anveshak Command:** 2.0x (₹3 crore vs ₹1.5 crore)

#### Tier 2: Joint Command (Multi-Service Integration)

| Component | Specification |
|-----------|--------------|
| Analysts | Up to 30 concurrent |
| Entity resolution | Up to 5M entity records |
| Graph queries | Unlimited with audit trail |
| Anveshak feeds | Up to 10 Anveshak instances bridged |
| Cross-domain | OSINT + structured intelligence feeds |
| Infrastructure | Customer-provided (5-node cluster) |
| RBAC | Full Keycloak SSO integration |
| Support | On-site engineering (quarterly), dedicated team, 7×12 |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹7 crore** | **₹6 crore** (14% saving) |
| **$ (USD equiv.)** | ~$840,000 | ~$720,000 |

**Ratio to Anveshak Enterprise:** 1.75x (₹7 crore vs ₹4 crore) — slightly below 2x at this tier because the enterprise buyer is buying volume

#### Tier 3: Strategic (National-Level / Multi-Agency)

| Component | Specification |
|-----------|--------------|
| Analysts | Unlimited |
| Entity resolution | Unlimited records |
| Cross-domain | Full multi-agency fusion (OSINT + HUMINT + SIGINT feeds) |
| Anveshak feeds | Unlimited instances |
| Multi-tenant | Agency-level data isolation with cross-agency correlation |
| Infrastructure | Customer-provided (dedicated cluster per agency + central fusion) |
| Compliance | NCIIPC-ready, classified network deployment support |
| Support | Embedded engineering team, 7×24 |

| | Annual License | 3-Year Contract (per year) |
|---|---|---|
| **₹ (INR)** | **₹15 crore** | **₹12.5 crore** (17% saving) |
| **$ (USD equiv.)** | ~$1.8M | ~$1.5M |

**Context:** Palantir's smallest govt contracts are $5M+. This is 70% cheaper for comparable fusion capability, purpose-built for Indian defence.

### Drishti Add-Ons

| Add-On | Annual Price | Notes |
|--------|-------------|-------|
| Additional Anveshak bridge (per instance) | ₹10 lakh/yr | Covers Redpanda topic + schema maintenance |
| Custom intelligence feed connector | ₹15–25 lakh (one-time) | Structured data ingestion from non-Anveshak sources |
| Graph algorithm customisation | ₹10 lakh (one-time) | Custom centrality, community detection, path analysis |
| Keycloak SSO federation setup | ₹5 lakh (one-time) | Integration with govt identity systems |
| Classified network deployment | ₹20 lakh (one-time) | Airgap config, mTLS, security hardening for classified infra |

---

## Combined Pricing: Anveshak + Drishti Bundle

### Why Bundle?

1. **For the buyer:** Single vendor, integrated stack, one support contract, proven bridge
2. **For Garud:** Higher ACV, stickier contracts, harder to displace
3. **Strategic:** "Start with Anveshak, grow into Drishti" is the sales motion — bundling locks in the upgrade path

### Bundle Discount Structure

| Bundle | Components | List Price | Bundle Price | Discount |
|--------|-----------|------------|--------------|----------|
| **Wing + Directorate** | Anveshak Wing + Drishti Directorate | ₹3.5 crore/yr | **₹3 crore/yr** | 14% |
| **Command + Directorate** | Anveshak Command + Drishti Directorate | ₹4.5 crore/yr | **₹3.75 crore/yr** | 17% |
| **Enterprise + Joint** | Anveshak Enterprise + Drishti Joint | ₹11 crore/yr | **₹9 crore/yr** | 18% |
| **Full Stack** | Anveshak Enterprise + Drishti Strategic | ₹19 crore/yr | **₹15 crore/yr** | 21% |

### Recommended Entry Deal: "IAF Starter"

The most likely first commercial deal post-iDEX:

| Component | Detail |
|-----------|--------|
| Anveshak Command (1 wing) | 15 analysts, all modules |
| Drishti Directorate license | Ready to activate when IAF wants fusion |
| GPU hardware bundle | 2× RTX 4090 servers (Anveshak + Drishti) |
| On-site deployment | 2 weeks engineering |
| Training | 40-hour analyst programme |
| Support | 12-month dedicated, 7×12 |

| | Year 1 (setup + license) | Year 2+ (license + support) |
|---|---|---|
| **₹ (INR)** | **₹4.5 crore** | **₹3.25 crore/yr** |

**3-year total: ₹11 crore** — well within a single iDEX procurement order (~₹55 crore average).

---

## Pricing Comparison Matrix

| | Anveshak Wing | Anveshak Command | Anveshak Enterprise | Drishti Directorate | Drishti Joint | Drishti Strategic |
|---|---|---|---|---|---|---|
| **Annual (INR)** | ₹50L | ₹1.5Cr | ₹4Cr | ₹3Cr | ₹7Cr | ₹15Cr |
| **Annual (USD)** | $60K | $180K | $480K | $360K | $840K | $1.8M |
| **Analysts** | 5 | 15 | 50 | 10 | 30 | Unlimited |
| **Ratio (to Anveshak equiv.)** | 1.0x | 1.0x | 1.0x | **2.0x** (vs Command) | **1.75x** (vs Enterprise) | **~3.75x** (vs Enterprise) |

### Drishti-to-Anveshak Ratio Summary

| Tier Comparison | Ratio | Justification |
|-----------------|-------|---------------|
| Drishti Directorate / Anveshak Command | **2.0x** | Core comparison; entity resolution + graph + infra premium |
| Drishti Joint / Anveshak Enterprise | **1.75x** | Enterprise volume discount softens ratio |
| Drishti Strategic / Anveshak Enterprise | **3.75x** | National-level = entirely different buyer (directorate → ministry) |
| **Weighted average across tiers** | **~2.0–2.5x** | Consistent with infrastructure cost and value multiplier |

---

## Revenue Projections (Conservative)

### Year 1 Post-iDEX (M10–M21)

| Deal | Product | Value |
|------|---------|-------|
| IAF wing deployment (iDEX procurement) | Anveshak Command + Drishti Directorate | ₹4.5 crore |
| State police (2 deployments via GrosINT upsell) | Anveshak Wing × 2 | ₹1 crore |
| Navy/MI inquiry (pilot) | Anveshak Wing | ₹50 lakh |
| **Year 1 Total** | | **₹6 crore** |

### Year 2

| Deal | Product | Value |
|------|---------|-------|
| IAF expansion (3 more wings) | Anveshak Command × 3 | ₹4.5 crore |
| IAF command-level Drishti upgrade | Drishti Joint | ₹7 crore |
| Navy deployment | Anveshak Command | ₹1.5 crore |
| State police renewals + new | Anveshak Wing × 5 | ₹2.5 crore |
| **Year 2 Total** | | **₹15.5 crore** |

### Year 3

| Deal | Product | Value |
|------|---------|-------|
| Multi-service Drishti | Drishti Strategic | ₹15 crore |
| Anveshak renewals (all) | Enterprise + Command × 4 + Wing × 5 | ₹12.5 crore |
| International (friendly nation pilot) | Anveshak Enterprise | ₹4 crore |
| **Year 3 Total** | | **₹31.5 crore** |

---

## GeM Listing Strategy

### GeM Product Listings

| Listing | Category | MRP (GeM ceiling) |
|---------|----------|-------------------|
| Anveshak OSINT Platform — Wing License | AI/ML Software, Cybersecurity | ₹55 lakh/yr |
| Anveshak OSINT Platform — Command License | AI/ML Software, Cybersecurity | ₹1.6 crore/yr |
| Anveshak OSINT Platform — Enterprise License | AI/ML Software, Cybersecurity | ₹4.25 crore/yr |
| Anveshak GPU Server Bundle (pre-configured) | IT Hardware + Software | ₹8 lakh (one-time) |

**Note:** GeM uses L1 or QCBS. Set MRP slightly above target price to allow 5–10% GeM negotiation discount while hitting target revenue.

**Drishti:** Not listed on GeM initially. Sold via direct procurement (RFP/single-source) given complexity and classification requirements.

---

## Competitive Positioning Summary

| Competitor | Their Price | Anveshak/Drishti Advantage |
|------------|------------|---------------------------|
| Recorded Future | ₹60L–₹4Cr/yr (SaaS) | Anveshak: Same price, sovereign on-prem, includes vision + deepfake |
| Babel Street | ~₹4.5L/seat × seats | Anveshak: Full platform (not per-seat), includes LLM reports |
| Palantir Gotham | ₹4Cr–₹80Cr+/yr | Drishti: 70–90% cheaper, purpose-built for Indian defence, no US dependency |
| Maltego | ₹2.5L–₹6L/yr | Anveshak: Automated pipeline (Maltego is analyst-driven manual investigation) |
| Flashpoint | ₹80L–₹2.5Cr/yr | Anveshak: Sovereign + vision + credibility audit trail |

### Anveshak's Unique Pricing Advantage

No competitor offers all of this in one license:
1. ✅ Sovereign on-prem (zero cloud dependency)
2. ✅ Web + Social + Vision + LLM Reports (typically 3 separate tools)
3. ✅ Deepfake detection (not available in any OSINT platform)
4. ✅ Source credibility with immutable audit trail (court-admissible)
5. ✅ Target-centric behavioral monitoring (typically a separate product)
6. ✅ Zero recurring API/cloud costs (Ollama local inference)

**TCO advantage:** Customer avoids $50K–$200K/yr in cloud LLM API costs, $20K–$50K/yr in data feed subscriptions, and $30K–$50K/yr in multiple tool licenses.

---

## Negotiation Guidelines

### Floor Prices (Never Go Below)

| Product | Floor | Rationale |
|---------|-------|-----------|
| Anveshak Wing | ₹35 lakh/yr | Below this, support costs exceed margin |
| Anveshak Command | ₹1 crore/yr | GPU + engineering support baseline |
| Anveshak Enterprise | ₹3 crore/yr | Multi-site support costs |
| Drishti Directorate | ₹2 crore/yr | Infrastructure complexity floor |
| Drishti Joint | ₹5 crore/yr | Multi-service integration costs |

### Discount Levers (What to Offer Instead of Price Cuts)

| Instead of... | Offer... |
|---------------|----------|
| 20% discount | 3-year lock-in at 15% discount |
| Lower annual price | Free first-year training programme (₹10L value) |
| Per-seat price reduction | Additional 5 seats free (maintains per-seat rate) |
| Price match to competitor | Free GPU hardware consultation + setup (₹3L value) |
| Drishti discount | Free Anveshak-Drishti bridge setup + first year bridge maintenance |

---

## Action Items

- [ ] Validate pricing with 2–3 friendly defence contacts (informal feedback)
- [ ] Build GeM listing drafts with pricing tiers
- [ ] Prepare 1-page pricing sheet (sanitised, no floor prices) for external use
- [ ] Model unit economics at each tier (engineering hours/customer, infra costs)
- [ ] Prepare ROI calculator for defence buyers ("Anveshak replaces 3 tools at 40% lower TCO")
