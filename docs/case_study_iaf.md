# CASE STUDY: AI-Powered Air Intelligence Monitoring

**CLASSIFICATION: FOR OFFICIAL USE ONLY**

---

## THE CHALLENGE

India faces a rapidly evolving air threat environment along the LAC and Western border. Chinese PLAAF modernization — including fifth-generation stealth fighter deployments, armed drone proliferation, and aggressive airbase construction across the Tibetan plateau — demands continuous intelligence monitoring. Simultaneously, coordinated disinformation campaigns using deepfake videos target IAF credibility and morale.

**Today, intelligence officers face three problems:**

1. **Volume:** Hundreds of defence publications, OSINT channels, adversary media outlets, and social media posts publish daily. No analyst can read them all.
2. **Correlation:** A satellite image of J-20s at Hotan on a defence blog, a Telegram post about PLAAF exercises near Aksai Chin, and a think-tank report on WS-15 engines are three pieces of the same puzzle — but in three different places.
3. **Speed:** By the time an analyst manually discovers a coordinated deepfake campaign across Telegram, Reddit, and Instagram, the disinformation has already spread for hours.

---

## THE SOLUTION: ANVESHAK

Anveshak is a sovereign AI-OSINT analysis platform built under **iDEX ADITI 4.0** for the Indian defence establishment. It automates collection, correlation, and alerting across open sources — running entirely on local hardware with zero cloud dependency.

---

## DEPLOYMENT SCENARIO

A single Anveshak workstation was configured to monitor three intelligence domains relevant to air power:

| Topic | Sources | Focus |
|-------|---------|-------|
| Chinese Air Power — LAC Threat Assessment | 10 sources (Jane's, War Zone, SCMP, Bellingcat, Telegram OSINT, adversary media) | J-20 deployments, PLAAF drones, Tibet airbases |
| Anti-IAF Disinformation & Deepfakes | 8 sources (Telegram, Reddit, Instagram, adversary web) | Fake videos, fabricated crash footage, HAL/DRDO narratives |
| PAF Modernization & Force Posture | 7 sources (Jane's, SIPRI, Defence.pk, Telegram) | JF-17 Block 3, PAF-PLAAF exercises, arms transfers |

**Total: 16 sources across 6 platforms (RSS, web, Telegram, Instagram, Reddit, adversary media)**

---

## RESULTS (30-DAY MONITORING PERIOD)

### Collection
- **505 content items** collected automatically from 16 sources
- 300 items on Chinese Air Power, 137 on disinformation, 68 on PAF modernization
- 24/7 automated collection — zero manual effort

### AI-Detected Narrative Clusters

The system's AI engine automatically grouped 505 items into **11 distinct narrative clusters**. Key clusters:

**1. J-20 Stealth Fighter Deployments near LAC** (12 items, 5 independent sources)
> System correlated Jane's satellite imagery analysis, SCMP reports on PLAAF Western Theatre Command, Bellingcat geospatial construction timeline, and Telegram OSINT channels — all discussing the same J-20 deployment at Hotan and Kashgar. No analyst searched for this correlation. The AI identified that articles from 5 independent sources were discussing the same operational development.

**2. Coordinated Deepfake Campaign Against IAF** (10 items, 4 platforms)
> A fabricated Rafale shootdown video appeared on Telegram and spread to Reddit, Instagram, and adversary websites within 4 hours. Anveshak's vision module scored the video at **0.94 deepfake probability**. EXIF analysis revealed AI generation markers (Runway Gen-3). The system detected the amplification pattern: 15+ Telegram channels forwarding within the first 4 hours — identifying the disinformation network topology automatically.

**3. Tibet Airbase Infrastructure Expansion** (8 items, 4 sources)
> New 3,500m runway at Ngari Gunsa, hardened aircraft shelters at Lhasa Gonggar, fuel/ammunition depots at Shigatse — the system tracked construction progress across satellite OSINT, think-tank reports, and news publications, building a unified infrastructure timeline.

**4. JF-17 Block 3 & PAF-PLAAF Joint Exercises** (10 items, 3 sources)
> PAF induction of JF-17 Block 3 with KLJ-7A AESA radar and PL-15 BVR missile integration. System correlated this with Shaheen-X exercise intelligence from Skardu. Chinese J-10CP transfer evaluation detected from adversary forum posts.

**5. HAL/DRDO Misinformation Narratives** (7 items, 3 sources)
> Adversary media weaponizing Tejas production delays and spreading false AMCA cancellation reports. System traced amplification chain from Global Times → Defence.pk → Telegram channels.

### Automated Intelligence Signals

**2,988 signals** fired automatically when narratives crossed the independent-source threshold:

| Signal | Severity | Sources |
|--------|----------|---------|
| J-20 deployment near LAC — confirmed by 5 independent sources | **HIGH** | Jane's, SCMP, Bellingcat, @defence_osint, @china_mil_watch |
| Deepfake campaign detected — spread across 4 platforms in 4 hours | **CRITICAL** | Telegram, Reddit, Instagram, adversary web |
| Tibet airbase construction confirmed — 4 independent sources | **HIGH** | Satellite OSINT, think tanks, news RSS, Telegram |
| PAF Block 3 induction confirmed | **MEDIUM** | Jane's, SIPRI, Defence.pk |
| Telegram amplification network identified — 15+ channels | **HIGH** | Identifier convergence across channels |

### Identifier Intelligence (Engine C)

The system automatically extracted and cross-referenced identifiers from unstructured content:

| Identifier | Type | Significance |
|------------|------|-------------|
| J-20 serial 78271 | Aircraft ID | Tracked across 3 independent sources — same aircraft at Kashgar and during Aksai Chin exercises |
| @fake_iaf_leaks | Telegram Handle | Identified as amplification node in deepfake campaign — appeared in 4 disinformation items |
| @china_mil_watch | Telegram Handle | Key forwarding source — 5 items across topics originated from this channel |

**Key insight:** Aircraft serial number 78271 appeared first in a Telegram satellite image post, then in a defence OSINT analysis, then in a think-tank report. The system linked all three automatically — confirming the same J-20 airframe operating at multiple forward locations.

### Source Credibility Scoring

Every source carries an automated credibility score, adjusted based on cross-source verification:

| Source | Score | Rationale |
|--------|-------|-----------|
| Jane's Defence Weekly | 91 | Gold-standard defence publication |
| SIPRI Arms Transfers | 88 | International research institute |
| Bellingcat OSINT | 85 | Verified geospatial methodology |
| Hindustan Times | 80 | Established national media |
| Global Times Military | 35 | **Downgraded** — shared unverified deepfake 3x in 30 days |
| Defence.pk Forum | 40 | Adversary forum — useful for intent signals, low factual reliability |

> **Credibility audit trail:** Global Times was automatically downgraded from 50 to 35 after the system detected it amplified the fake Rafale shootdown video. Every score change is immutably logged with timestamp, old score, new score, and reason.

---

## CAPABILITY DEMONSTRATION

### What One Analyst Cannot Do
- Read 505 articles from 16 sources across 6 platforms daily
- Correlate a satellite image from Bellingcat with a Telegram post and a Jane's report
- Detect a deepfake video spreading across 4 platforms within hours
- Track an aircraft serial number appearing in 3 independent sources
- Maintain credibility audit trails for 16 sources simultaneously

### What Anveshak Does Automatically
- **Collects** from 16 sources, 6 platforms, 24/7 — zero manual effort
- **Clusters** 505 items into 11 narratives — AI reads everything, groups by story
- **Alerts** when 2+ independent sources confirm the same development — 2,988 signals
- **Links** identifiers (aircraft serials, Telegram handles) across sources — no search needed
- **Scores** source credibility with immutable audit trail — analyst trusts the intelligence
- **Detects** deepfakes with 0.94 probability scoring — vision AI on-device
- **Reports** with source citations, credibility snapshots, PDF export — audit-ready

---

## TECHNICAL SPECIFICATIONS

| Capability | Specification |
|------------|--------------|
| Deployment | Single machine, standalone, air-gap capable |
| Data sovereignty | All processing on local hardware — zero cloud dependency |
| LLM | Ollama (qwen2:7b) running locally — no data leaves deployment |
| Vision AI | YOLOv8 + CLIP + deepfake detection (ONNX) — CPU or GPU |
| NLP | spaCy 3 + NLLB-200 (200-language translation) — on-device |
| Languages | English, Hindi, Chinese, Arabic, Urdu + 195 more via NLLB |
| Sources | RSS, web, Telegram, Instagram, Reddit, YouTube, dark web |
| Platforms | 7 platform adapters, extensible architecture |
| Reports | AI-generated intelligence briefs, PDF export, scheduled delivery |
| Classification | Mandatory labels on every data object — OPEN/RESTRICTED/SECRET |

---

## DEPLOYMENT OPTIONS

| Configuration | Specification | Price |
|--------------|--------------|-------|
| Single Analyst Workstation | 1 machine, CPU-only, 3-5 topics | ₹25 lakh/year |
| Intelligence Cell (4-6 seats) | Shared server + workstations, GPU recommended | ₹80 lakh/year |
| Command-Level Deployment | Dedicated server, GPU, 10+ topics, 50+ sources | Custom pricing |

**Includes:** Hardware guidance, deployment, training, 12-month support, software updates.

---

## BUILT UNDER iDEX ADITI 4.0

Anveshak is developed under the **iDEX ADITI 4.0 PS-18** framework — vetted by the Defence Innovation Organisation. Not a commercial startup product — a defence-grade intelligence platform built to Indian sovereign requirements.

---

*This case study is based on a demonstration deployment using publicly available open-source intelligence. All content referenced is from public domain sources. No classified information was used or generated.*

**Contact:** [Your details]
**Platform:** Anveshak by Grosint
