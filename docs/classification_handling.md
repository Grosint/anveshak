# Anveshak — Classification Handling & Data Boundary Policy
## What Goes In, What Stays Out, What Comes Out

**Document Classification:** Internal — Shareable with prospective clients under NDA
**Prepared by:** Garud Research & Tech Private Limited
**Version:** 1.0
**Date:** May 2026

---

## Purpose

MoD decision makers need absolute clarity on one question: **"Can Anveshak handle classified inputs, and what classification level does its output carry?"**

This document defines Anveshak's data classification boundaries, ingestion policy, output classification, and deployment modes for different security environments.

---

## Core Principle

> **Anveshak is an OPEN SOURCE intelligence platform. It ingests UNCLASSIFIED/OPEN data and produces RESTRICTED-level output through AI-driven analysis and correlation.**

The value is not in accessing secrets — it's in finding what's hidden in plain sight.

---

## Classification Framework (Indian System)

| Level | Definition | Anveshak Relationship |
|-------|-----------|----------------------|
| **Top Secret** | Exceptionally grave damage to national security | NEVER ingested, NEVER stored, NEVER processed |
| **Secret** | Serious damage to national security | NEVER ingested, NEVER stored, NEVER processed |
| **Confidential** | Damage to national security | NOT ingested as source data (see exception below) |
| **Restricted** | Undesirable disclosure | Anveshak OUTPUT may be classified at this level |
| **Unclassified / Open** | Publicly available information | ALL Anveshak INPUT is at this level |

---

## What Anveshak INGESTS (Input Boundary)

### Permitted Sources (Unclassified / Open)

| Source Type | Examples | Classification |
|-------------|----------|---------------|
| Public news websites | NDTV, ANI, Reuters, Al Jazeera, Xinhua | Open |
| RSS feeds | Government press releases, news aggregators | Open |
| Social media (public) | Public Telegram channels, Reddit, Bluesky, X | Open |
| Academic / research | SIPRI, IISS, university publications | Open |
| Government gazettes | MoD press releases, PIB, Gazette of India | Open |
| Satellite imagery (commercial) | Planet, Maxar (publicly purchasable) | Open |
| Court records | Public judicial filings | Open |
| Dark web forums (public-facing) | Indexed surfaces of .onion sites | Open (debatable — see note below) |

### NOT Permitted as Input

| Source Type | Why Not | What To Do Instead |
|-------------|---------|-------------------|
| Classified intelligence reports | Anveshak has no clearance infrastructure | Use Anveshak output to supplement classified analysis |
| SIGINT intercepts | Different classification domain entirely | Separate system, separate network |
| HUMINT source reports | Compromise risk, need-to-know violation | Analyst can manually cross-reference |
| Classified satellite imagery (NRO/NGIO) | Requires separate handling procedures | Use commercial imagery only |
| Internal MoD communications | Classification level too high | Never input to any OSINT tool |

### Grey Area: Analyst-Provided Context

| Scenario | Permitted? | Guidance |
|----------|-----------|----------|
| Analyst types topic keywords | Yes | Keywords like "Aksai Chin movement" are not classified |
| Analyst provides a specific name to monitor | Yes, if name is publicly known | Don't input code names or cover identities |
| Analyst uploads an image for deepfake check | Yes, if image is from open sources | Don't upload classified surveillance imagery |
| Analyst configures a Telegram channel to monitor | Yes | Channel must be publicly joinable |
| Analyst pastes a paragraph from a classified report to "find more like this" | **NO** | Never input classified text as search context |

---

## What Anveshak PRODUCES (Output Classification)

### Why Output May Be Classified Higher Than Input

Raw open-source data is unclassified. But **correlation, aggregation, and analysis** of open data can produce insights that warrant classification:

| Scenario | Input Classification | Output Classification | Reason |
|----------|---------------------|----------------------|--------|
| Single news article about troop movement | Open | Open | One article = public knowledge |
| 15 correlated sources showing pattern of movement over 3 weeks | Open | **Restricted** | Aggregation reveals operational pattern |
| Deepfake detection on propaganda video | Open | Open | Technical analysis of public content |
| Signal: 5 independent sources confirm asset repositioning | Open | **Restricted** | Analyst judgement needed on classification |
| Generated report correlating cross-border activity across 50 sources | Open | **Restricted** | Mosaic effect — sum greater than parts |

### The Mosaic Effect

> Individual tiles are unclassified. The assembled mosaic may reveal a classified picture.

**Anveshak's reports should be treated as RESTRICTED by default** because:
1. They aggregate hundreds of data points that individually are open
2. Correlation may reveal patterns not intended to be public
3. The analyst's topic configuration itself may reveal intelligence priorities
4. Signal alerts indicate what the unit considers operationally significant

### Output Classification Guidance

| Output Type | Default Classification | Handling |
|-------------|----------------------|----------|
| Raw content items (individual) | Unclassified | Can be stored on unclassified network |
| Narrative clusters | Restricted | Pattern reveals analytical interest |
| Signals (multi-source alerts) | Restricted | Reveals what unit considers significant |
| Generated reports | Restricted | Aggregation + analysis = mosaic risk |
| Source credibility scores | Restricted | Reveals intelligence methodology |
| Topic configurations | Restricted | Reveals collection priorities |
| System logs (operational) | Unclassified | Content hashes only, no raw text |

---

## Deployment Modes by Security Environment

### Mode 1: Unclassified Network (Internet-Connected)

```
┌─────────────────────────────────────────────┐
│  UNCLASSIFIED NETWORK                        │
│                                              │
│  ┌──────────┐     ┌──────────────────────┐  │
│  │ Internet │────▶│     ANVESHAK         │  │
│  │ (scraping)│     │  (all services)      │  │
│  └──────────┘     └──────────────────────┘  │
│                                              │
│  Analyst access: Direct                      │
│  Output: Print/export to classified net      │
└─────────────────────────────────────────────┘
```

**Use case:** Units with internet access on their unclassified segment
**Restriction:** Output reports must be manually classified before moving to classified network
**Advantage:** Full real-time scraping capability

### Mode 2: Air-Gapped (Data Diode / Sneakernet)

```
┌──────────────────┐         ┌─────────────────────────────┐
│ INTERNET SEGMENT │         │  CLASSIFIED / AIR-GAPPED     │
│                  │         │                              │
│ ┌──────────────┐ │  USB/   │  ┌──────────────────────┐   │
│ │ Scraper-only │ │──Diode─▶│  │   ANVESHAK (Analysis)│   │
│ │ instance     │ │         │  │   No internet access │   │
│ └──────────────┘ │         │  └──────────────────────┘   │
│                  │         │                              │
│ Collects only    │         │  Analyses, correlates,       │
│ raw content      │         │  generates reports           │
└──────────────────┘         └─────────────────────────────┘
```

**Use case:** High-security environments where analysis must happen on classified network
**How it works:**
1. Scraper instance runs on internet-connected unclassified machine
2. Raw content exported to encrypted USB / data diode (one-way transfer)
3. Analysis instance (analyst, reporter, vision) runs air-gapped
4. No data ever flows back to internet-connected segment

**Restriction:** Not real-time (batch delay = transfer frequency)
**Advantage:** Analysis and reports never touch internet-connected hardware

### Mode 3: Hybrid (Split Deployment)

```
┌──────────────────────────────┐
│  UNCLASSIFIED SEGMENT        │
│  ┌────────┐  ┌────────────┐  │
│  │Scraper │  │  Social    │  │
│  │        │  │  Adapters  │  │
│  └───┬────┘  └─────┬──────┘  │
│      │              │         │
│      ▼              ▼         │
│  ┌────────────────────────┐  │
│  │   Redis Queue (export) │  │        ┌──────────────────────┐
│  └───────────┬────────────┘  │        │  RESTRICTED SEGMENT  │
│              │               │        │                      │
└──────────────┼───────────────┘        │  ┌────────────────┐  │
               │  One-way data flow      │  │  Analyst       │  │
               └────────────────────────▶│  │  Reporter      │  │
                                         │  │  Vision        │  │
                                         │  │  PostgreSQL    │  │
                                         │  └────────────────┘  │
                                         │                      │
                                         │  Analyst access here │
                                         └──────────────────────┘
```

**Use case:** Optimal balance — real-time collection, restricted analysis
**How it works:** Scraper/social on unclassified net → one-way push to restricted net
**Advantage:** Near real-time + classified analysis environment

---

## Handling Procedures

### For the Analyst

| Action | Procedure |
|--------|-----------|
| Configuring topics | No classified keywords as topic names. Use general terms. |
| Reviewing signals | Signals are RESTRICTED. Don't screenshot to personal device. |
| Exporting reports | PDF export = RESTRICTED. Handle per unit SOPs. |
| Sharing findings | Route through unit intelligence officer for classification review |
| Adding sources | Only publicly accessible sources. Never input agent handles. |

### For the Unit IT Administrator

| Action | Procedure |
|--------|-----------|
| Backups | Encrypted, stored per RESTRICTED data handling rules |
| Log access | System logs are UNCLASSIFIED (no content, only hashes) |
| User management | Follow unit access control policies |
| USB/media | Export media treated as RESTRICTED |
| Decommissioning | Full disk wipe per MoD data destruction policy |

### For Garud Support Engineers (AMC)

| Action | Procedure |
|--------|-----------|
| Remote access | Only via unit-approved secure VPN, logged |
| Data visibility | Support engineers see system health only, NOT content/reports |
| Log review | Can access operational logs (no intelligence content in logs) |
| On-site visits | Escorted, no personal devices, per unit visitor policy |
| No data extraction | Support staff NEVER export content, reports, or configurations |

---

## Compliance with MoD Information Security Policies

| Requirement | How Anveshak Complies |
|-------------|----------------------|
| MoD Data Classification Policy (2015) | Output classified as RESTRICTED by default |
| IT Act Section 69 (interception) | Not applicable — Anveshak does not intercept; it reads publicly available data |
| Personal Data Protection Act (2023) | No Indian citizen PII stored unless publicly posted by themselves |
| CERT-In reporting | Unit IT to report any breach per standard procedure |
| CDA (Official Secrets Act) | System never processes classified inputs; output classification per analyst judgement |

---

## Frequently Asked Questions

**Q: Can I paste a classified report into Anveshak to find related open-source information?**
A: NO. Never input classified content. Instead, extract unclassified keywords and use those as topic/search terms.

**Q: If Anveshak finds something sensitive, does it automatically classify it?**
A: No. Anveshak flags significance (via signals). The analyst applies classification based on operational context and unit SOPs.

**Q: Can enemy actors see what we're monitoring?**
A: No. Anveshak's scraping uses standard HTTP requests indistinguishable from normal browsing. Topic configurations never leave the machine.

**Q: What if an analyst accidentally inputs classified data?**
A: Immediately notify unit security officer. Garud support can assist with targeted data deletion from PostgreSQL. Incident handled per unit breach protocol.

**Q: Does Anveshak's AI "learn" from classified context over time?**
A: No. The LLM (Ollama) has no persistent memory between requests. Each analysis is stateless. No fine-tuning on operational data occurs.

**Q: Can we use Anveshak output in official intelligence assessments?**
A: Yes — with appropriate classification marking. Anveshak reports include full source citations for traceability. Mark as RESTRICTED (minimum) in official documents.

---

## Summary for Decision Makers

| Question | Answer |
|----------|--------|
| What goes IN? | Only publicly available, unclassified open-source data |
| What comes OUT? | Correlated intelligence — classify as RESTRICTED (minimum) |
| Can it handle classified inputs? | NO — by design, not by limitation |
| Is that a weakness? | No — it's a deployment advantage (no SAPCC needed, no special accreditation) |
| Where does it sit on the network? | Unclassified segment (Mode 1), air-gapped (Mode 2), or split (Mode 3) |
| Who classifies the output? | The analyst, per unit SOPs — not the machine |

**The key insight:** Because Anveshak ONLY processes open-source data, it can be deployed WITHOUT the multi-year accreditation process required for classified systems. Your unit can be operational in weeks, not years.

---

**Document maintained by:** Garud Research & Tech Pvt Ltd
**Last updated:** May 2026
