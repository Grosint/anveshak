# ANVESHAK — iDEX ADITI 4.0 PS-18 Application
## Garud Research & Tech Private Limited

---

## 1. Brief Summary of the Proposed Solution

Indian Air Force intelligence officers currently lack a unified, sovereign platform to collect, analyse, and report on open-source intelligence (OSINT) from the web and social media. Existing tools are either cloud-dependent (compromising data sovereignty), fragmented across multiple systems, or unable to process multilingual and multimedia content at operational tempo.

**Anveshak** is an AI-powered OSINT analysis and monitoring platform that we have already built and validated as a fully functional prototype — self-funded and operational — covering all five PS-18 modules. Its design is grounded in three years of operating GrosINT, our OSINT platform currently serving ~300 defence and law enforcement users including IAF, Navy, MI, and ED analysts. The platform runs entirely on a single machine with zero cloud dependencies, continuously collecting content from open websites, RSS feeds, and four social media platforms (Telegram, Reddit, Bluesky, X/Twitter). It processes content through a multilingual NLP pipeline (English, Russian, Chinese), detects manipulated imagery using deepfake probability scoring, identifies objects of intelligence value (vehicles, aircraft, personnel) via computer vision with a roadmap to defence-specific model fine-tuning, and clusters corroborated narratives from independent sources to surface real-time intelligence signals.

**Key innovations include:** (a) a sovereign LLM-powered report generator producing sourced intelligence briefs entirely on local hardware; (b) a multi-platform signal corroboration engine that eliminates single-source noise; and (c) an automated source credibility scoring system with an immutable audit trail.

**The 9-month programme** funds the journey from validated prototype to IAF-deployed operational system: security hardening, GPU hardware procurement, deployment at an IAF wing, analyst training, and development of an advanced target-centric monitoring capability for tracking persons of interest with behavioral anomaly detection.

*(250 words)*

---

## 2. Key Technologies Used

1. **Sovereign Local LLM Inference** (Ollama + RAG pipeline)
2. **Multilingual NLP** (spaCy + NLLB-200 machine translation)
3. **AI Deepfake Detection** (Facetorch + DIRE + EfficientNet)
4. **Computer Vision** (YOLOv8 object detection + CLIP semantic classification)
5. **Vector Similarity Search** (PostgreSQL pgvector + HDBSCAN clustering)
6. **Real-Time Signal Corroboration** (multi-platform independent source engine)

---

## 3. Deliverables

| S. No | Deliverable Name | Brief Description |
|-------|-----------------|-------------------|
| 1 | **Validated OSINT Platform (M1-M5)** | Production-hardened platform with all five PS-18 modules: source credibility engine, open-web analysis with multilingual NLP, social media monitoring (Telegram/Reddit/Bluesky/X), image & video intelligence (deepfake/YOLO/CLIP/EXIF), and sovereign LLM report generation with PDF/GIS export. Currently operational as a self-funded prototype. |
| 2 | **Target-Centric Monitoring Module (M6)** | Advanced person-of-interest tracking across social platforms with behavioral baseline computation, anomaly detection (activity spikes, topic shifts, schedule changes), and multi-target coordination detection for identifying information operations. |
| 3 | **Security-Certified Deployment Package** | ISO 27001:2022 certified, STQC tested, GeM-listed, airgap-ready deployment with GPU-optimised inference, classified-network-compatible configuration, and single-command installation for IAF wing infrastructure. |
| 4 | **Analyst Training Programme & SOPs** | Comprehensive training curriculum for IAF intelligence officers, operational SOPs, and 12-month post-deployment support with on-site engineering during initial deployment. |

---

## 4. Proposed Timeline (9 Months)

| Phase | Month | Deliverable | Exit Criteria |
|-------|-------|-------------|---------------|
| **Stage 1: Hardening & Advanced R&D** | M1-M3 | Security audit and remediation; ISO 27001:2022 and STQC certification; GPU hardware procurement and optimisation; fine-tuning object detection models on defence-relevant imagery (military vehicles, aircraft types, weapons systems); scale testing with production-volume data (100K+ items); target-centric monitoring module — data model, collection adapters, behavioral baseline engine; MeitY/GeM empanelment initiated | Security audit completed with zero critical findings; ISO 27001:2022 and STQC certification obtained; Anveshak listed on GeM portal; MeitY empanelment completed; platform operational on GPU hardware; object detection fine-tuned and validated on defence imagery dataset; target monitoring collecting and analysing POI activities across Telegram and X/Twitter |
| **Stage 2: Field Deployment** | M4-M6 | IAF wing installation and network integration; analyst training programme delivery; iterative UI refinement based on real analyst workflows; multi-target correlation engine (coordination detection, information flow analysis); airgap/classified-adjacent deployment configuration | Platform deployed and operational at IAF wing; analysts trained and using the system on real intelligence requirements; target correlation matrix detecting coordinated activity across monitored POIs |
| **Stage 3: Acceptance & Validation** | M7-M9 | Full PS-18 acceptance testing against all criteria; performance tuning on production hardware; advanced target monitoring features (behavioral synchronisation, shared amplification network detection); documentation and SOP finalisation; 12-month support handover | All PS-18 acceptance criteria met and signed off; target monitoring operational with 50+ POIs; analyst-validated workflows documented; support framework operational |

---

## 5. Proposed Technical Solution (Detailed)

### 5.1 Technical Architecture & Approach

Anveshak is a microservices platform deployed as 17 containers on a single machine via Docker Compose (development) or k3s (production). All services communicate through PostgreSQL and Redis — no inter-service HTTP coupling — allowing any service to restart independently without cascade failures. The architecture is directly informed by three years of operating GrosINT for Indian defence and law enforcement agencies, where we learned that intelligence officers need a system that is self-contained, requires no internet dependency for core analysis, and produces auditable output.

**System Architecture:**

```
+======================================================================+
|                           INTERNET                                    |
|    Websites   RSS Feeds   Telegram   Reddit   Bluesky   X/Twitter    |
+=======+===========================================+==================+
        |                                           |
  +-----v------+                             +------v-------+
  |  SCRAPER   |  Crawl4AI + trafilatura     |   SOCIAL     |  Telethon, PRAW,
  |  (M2)      |  web pages + RSS feeds      |   (M3)       |  atproto, tweepy
  +-----+------+                             +------+-------+
        |         content_items                      |
        +-------------------+------------------------+
                            | SHA-256 deduplication
                     +------v------+
                     | PostgreSQL  |  pgvector (384-dim embeddings)
                     | + pgvector  |  12 tables, content-hash dedup
                     +------+------+
                            |
         +------------------+----------------------+
         |                  |                      |
   +-----v------+    +-----v------+       +-------v--------+
   |  ANALYST   |    |  VISION    |       |   REPORTER     |
   |  (M1+M2)   |    |  (M4)      |       |   (M5)         |
   | NLP+Signals|    | Deepfake   |       | RAG + LLM      |
   | Clustering |    | YOLO+CLIP  |       | PDF + GeoJSON  |
   +-----+------+    +------------+       +-------+--------+
         |                                        |
         +------------------+---------------------+
                     +------v------+
                     |  API + WS   |  FastAPI gateway, JWT auth
                     +------+------+
                     +------v------+
                     |  FRONTEND   |  React analyst workbench + MapLibre
                     +-------------+

   +-------------+    +-------------+    +----------------------+
   |   Ollama    |    |   Redis     |    |  Observability       |
   |  Local LLM  |    |  ARQ Queue  |    |  Prometheus+Grafana  |
   |  Sovereign  |    |             |    |  Loki+Promtail       |
   +-------------+    +-------------+    +----------------------+
```

**How It Works for the Analyst:**

An IAF intelligence officer logs into the analyst workbench, creates a monitoring topic (e.g., "J-20 stealth fighter deployments") with keywords and a signal threshold. From that point, the platform works autonomously:

1. **Collects** — Web sources and social media are scanned continuously. Duplicate content is eliminated automatically.
2. **Understands** — Content is translated (Russian, Chinese to English), entities are extracted (people, organisations, locations), and each item is semantically indexed.
3. **Clusters** — Related content from different sources is grouped into narrative clusters. The system tracks how many independent platforms are reporting each narrative.
4. **Alerts** — When a narrative is corroborated by enough independent sources (e.g., Telegram + Reddit + a news website), a real-time signal appears in the analyst's inbox. Single-source noise is suppressed.
5. **Verifies** — Images and videos are checked for manipulation. Deepfake probability scores (not binary yes/no) let the analyst apply operational judgement. Sources that share manipulated content are automatically downgraded.
6. **Reports** — The analyst requests an intelligence brief. The system retrieves the most relevant content, generates a structured report using a local LLM (no cloud), validates every claim against sources, and produces a PDF with map visualisation. The report is immutable — a court-admissible point-in-time snapshot.

**Data Sovereignty Guarantee:** All LLM inference, NLP processing, and data storage occurs on the local machine or internal Docker network. No intelligence data leaves the deployment boundary under any operational scenario. No cloud API keys are required or used.

---

### 5.2 Innovation

**a) Sovereign LLM Intelligence Reports**

Unlike cloud-dependent solutions, Anveshak generates RAG-grounded intelligence briefs entirely on local hardware using Ollama. The report pipeline retrieves relevant content via vector similarity search, enriches it with source credibility scores and dates, and generates a structured brief with source citations. An anti-hallucination framework ensures the LLM only cites facts present in the provided context — claims without source backing are rejected during automated validation. Reports are immutable once generated, with credibility scores frozen at generation time, producing tamper-evident intelligence products. This is, to our knowledge, the first sovereign OSINT report generator purpose-built for Indian defence use.

**b) Multi-Platform Signal Corroboration**

Existing OSINT tools alert on volume — many posts trigger an alert. Anveshak alerts on **corroboration**, counting distinct platforms contributing to a narrative cluster, not raw item count. A single Telegram channel posting the same message 50 times is noise. But when Telegram, Reddit, and a news website independently report the same narrative, that is a signal worth investigating. This approach, refined through three years of operating GrosINT for Indian defence and LE users, dramatically reduces false positives.

**c) Immutable Evidence Chain**

Every report captures a source snapshot — credibility scores frozen at generation time. If a source is later downgraded, a warning is attached to the report, but the report itself is never modified. Combined with the append-only credibility audit log, this produces a complete evidence chain from raw source to finished report — suitable for intelligence review and legal proceedings.

**d) Target-Centric Behavioral Monitoring (Stage 1 R&D)**

The planned M6 module introduces person-of-interest tracking with behavioral baseline computation. After 14 days of collection, the system builds a statistical fingerprint of normal activity per target — posting frequency, active hours, topic distribution, sentiment, platform preference. Deviations trigger anomaly signals: activity spikes, sudden topic shifts, schedule changes, or cross-platform coordination bursts. A multi-target correlation engine detects coordinated inauthentic behavior — synchronized posting, shared amplification networks, and information flow directionality (identifying who originates narratives and who amplifies them).

**e) Zero-Code Hardware Scaling**

Every ML model name, device configuration, batch size, and inference parameter is read from environment variables. Upgrading from CPU to GPU, or from a 7-billion to 72-billion parameter LLM, requires only configuration changes — no code modifications, no redeployment of application logic. This ensures Anveshak scales with IAF hardware investment without ongoing engineering overhead.

---

### 5.3 Implementation & Feasibility

**Current State:** The prototype is fully operational with 267 unit tests and 20 end-to-end tests passing on CPU hardware. All five PS-18 modules are implemented, integrated, and live-tested with real OSINT sources producing 148 content items, 8 narrative clusters, 5 signals, and 2 generated reports.

**Deployment Strategy:**

| Environment | Method | Target |
|-------------|--------|--------|
| Development | Docker Compose (single command) | Developer machines |
| Evaluation | Docker Compose + GPU passthrough | Demo/eval server |
| Production (IAF) | k3s (single-node Kubernetes) | IAF wing server room |
| Airgap variant | Pre-built images + offline model weights | Classified-adjacent networks |

**Scalability — CPU to GPU Upgrade Path:**

| Capability | CPU (Current Prototype) | GPU (IAF Production) |
|-----------|------------------------|----------------------|
| Content throughput | ~50 articles/day with translation | ~10,000 articles/day |
| Report generation | ~5 minutes per report | ~10 seconds per report |
| Object detection | Lightweight nano model | Full-accuracy xlarge model |
| Deepfake detection | Basic CPU model | High-accuracy DIRE model |
| LLM quality | 7B parameter model | 72B parameter model (significantly fewer hallucinations) |

All upgrades require zero code changes — environment variable configuration only.

**Team & Execution Plan:** The two founding engineers have built and operated GrosINT for 3 years, deployed Cognecto across 10,000+ km of government infrastructure, and developed the complete Anveshak prototype. Grant funding will expand the team with dedicated hires for security certification, IAF deployment engineering, and defence-domain ML fine-tuning, ensuring the 9-month programme has adequate bandwidth for parallel workstreams.

**Compliance & Certification:** The platform is designed in accordance with the IT Act 2000 provisions on data handling for government systems. Sovereign deployment architecture ensures compliance with defence data localisation requirements. Stage 1 includes ISO 27001:2022 certification (information security management) and STQC software testing certification (MeitY). MeitY vendor empanelment and GeM listing will be initiated in parallel. These certifications ensure Anveshak meets the security and quality standards required for Indian defence procurement. A longer-term roadmap includes SOC 2 Type II for GrosINT SaaS operations and DRDO/CAIR security evaluation for the deployed platform.

---

### 5.4 Challenges & Mitigation

| Challenge | Risk | Mitigation |
|-----------|------|------------|
| **Defence-specific object detection** | Generic models detect vehicles, aircraft, and personnel but cannot distinguish military-specific types (e.g., J-20 vs Rafale) | Stage 1 includes GPU-accelerated fine-tuning on defence-relevant imagery. CLIP semantic classification provides interim analyst-defined category matching. |
| **LLM hallucination in reports** | Local 7B models may fabricate claims not present in source material | Anti-hallucination prompt framework + mandatory automated validation. Every claim must cite a source from the provided context. Failed validation results in report rejection. GPU upgrade to 72B model further reduces hallucination rate. |
| **X/Twitter API costs** | Pay-per-read pricing can escalate without control | Atomic spend guard checks monthly read count against a configurable ceiling before every API call. Budget overrun is architecturally impossible. |
| **Multilingual NLP accuracy** | Medium-tier NLP models achieve ~80-85% entity recognition accuracy on Russian and Chinese | Documented upgrade to transformer-based models (~94% accuracy) via configuration change only. Machine translation ensures all downstream analysis operates on English text regardless of source language. |
| **Classified network deployment** | IAF networks may restrict container runtimes and outbound access | Airgap deployment variant with pre-built images and offline model weights. Platform requires zero outbound internet once models are loaded. k3s is DISA STIG-compliant for defence environments. |
| **Analyst adoption** | Intelligence officers may resist new tooling if it doesn't match existing workflows | Three years of operating GrosINT across defence/LE agencies directly informs UI design. Stage 2 includes embedded on-site engineering with iterative refinement based on real IAF analyst feedback. |

---

### 5.5 Observability & Operational Monitoring

Anveshak includes a production-grade observability stack for operational health monitoring without external dependencies:

- **Prometheus** — collects metrics from all services every 15 seconds: request rates, latencies, job success/failure counts, queue depths, ML inference times
- **Grafana** — 8 pre-configured dashboards covering system overview, ingestion pipeline, vision analysis, credibility scoring, signal rates, report generation, and infrastructure health
- **Loki + Promtail** — centralised structured log aggregation with 7-day retention and search capability
- **Alerting Rules (13)** — automated detection of service failures, ingestion stalls, slow report generation, job failure spikes, deepfake volume anomalies, database connection exhaustion, and disk space warnings
- **Jaeger** — opt-in distributed tracing for debugging request lifecycle across service boundaries during incident investigation

All observability components deploy alongside the platform — no external monitoring infrastructure required.

---

## 6. Capabilities & Competencies

- **Proven OSINT platform in active defence and law enforcement use:** We operate GrosINT, a SaaS OSINT tool currently used by analysts across Indian Air Force, Indian Navy, Military Intelligence, Enforcement Directorate, Kerala Police, UP Police, and MP Police — approximately 300 users with 20-30 daily active. Three years of operational exposure to how Indian defence and LE analysts consume intelligence directly shaped Anveshak's architecture.

- **Government-scale AI deployment (Cognecto, sister company):** The same founding team built and deployed Cognecto, an AI-powered infrastructure monitoring platform spanning 10,000+ km across 9 Indian states (highways, expressways, rural roads) and mines monitoring across 4 continents. Recognised as Tech30 and India AI Top 10 Startups. Demonstrates proven ability to deliver AI/ML systems at government scale.

- **Working PS-18 prototype delivered at own investment:** All five PS-18 modules are built, integrated, and live-tested before this application — 267 unit tests, 20 end-to-end tests, zero security findings. Self-funded development de-risks the programme for iDEX.

- **AI/ML production capability:** Demonstrated deployment of multilingual NLP, computer vision (object detection, deepfake scoring), and sovereign local LLM inference — all operational without cloud dependencies.

- **Intellectual property:** CTO holds 5 US patents and 1 Indian patent. Complementary Drishti entity resolution platform fully built as enterprise upgrade path.

- **Company:** Garud Research & Tech Pvt. Ltd. 4 years in operation. DPIIT-registered startup. Startup India recognition. Team expansion planned with grant funding.

*(247 words)*

---

## A. Applicant Resumes

### Divyani Singh
**Co-Founder & CEO, Garud Research & Tech Pvt. Ltd.**

- 10+ years in technology and large-scale government infrastructure, spanning smart cities, national identity systems, entertainment platforms, and AI for defence
- **Founding team member, BookMyShow** — designed and implemented the recommendation engine platform, building ML-driven personalisation at consumer scale
- **UIDAI (Aadhaar)** — part of the core team for complete infrastructure deployment of India's national identity programme, one of the world's largest biometric ID systems
- **Smart City projects** — delivered technology solutions across multiple Indian Smart City Mission implementations
- Co-founded Cognecto (sister company) — AI infrastructure monitoring deployed across 10,000+ km in 9 Indian states and mines monitoring across 4 continents; recognised as Tech30 and India AI Top 10 Startups
- Co-founded Garud Research — operates GrosINT SaaS OSINT tool used by defence and law enforcement analysts; developed Anveshak AI-OSINT platform and Drishti entity resolution platform
- Led product strategy and defence/government client relationships across both ventures
- B.Tech Computer Science Engineering, UPES (2016)

### Anshul Saxena
**Co-Founder & CTO, Garud Research & Tech Pvt. Ltd.**

- 10 years in AI/ML engineering — NLP, computer vision, real-time data pipelines, sovereign LLM deployment
- 5 US patents and 1 Indian patent
- Architected Cognecto's computer vision pipeline (sister company) — 10,000+ km deployment across 9 states, mines monitoring across 4 continents
- Architected Anveshak — designed and built all 5 PS-18 modules (267 unit tests, 20 e2e tests, sovereign architecture)
- Built GrosINT SaaS OSINT tool used by analysts across IAF, Navy, MI, ED, and state police forces
- B.Tech Computer Science Engineering, UPES (2016)

---

## B. Relevant Information Related to Solution

### Past Experience Directly Informing the Proposed Solution

**1. GrosINT — SaaS OSINT Tool (Garud Research & Tech)**

A SaaS OSINT tool currently used by analysts across Indian Air Force, Indian Navy, Military Intelligence, Enforcement Directorate, Kerala Police, UP Police, and MP Police — approximately 300 users with 20-30 daily active. Operating GrosINT for 3 years gave us direct, continuous exposure to how Indian defence and law enforcement analysts consume open-source intelligence:

| Operational Insight from GrosINT | How It Shaped Anveshak |
|----------------------------------|----------------------|
| Analysts overwhelmed by duplicate content across sources | SHA-256 content deduplication — same article from different URLs produces one entry |
| Single-source alerts cause excessive false positives | Multi-platform signal corroboration — alerts only when independent platforms confirm a narrative |
| Defence users consistently reject cloud-dependent tools | Sovereign-first architecture: local LLM, zero cloud dependency, no data egress |
| Analysts distrust AI output without source attribution | Every report claim must cite a source; unsourced claims automatically rejected |
| Non-English content manually handled, causing delays | Automated NLLB-200 translation pipeline for Russian and Chinese |
| No audit trail for source reliability assessments | Immutable append-only credibility audit log — every score change traceable |

GrosINT proved the market demand. Anveshak is the full-capability sovereign platform that GrosINT users have been asking for.

**2. Cognecto — AI Infrastructure Monitoring (Sister Company, Same Founding Team)**

An AI-powered infrastructure monitoring platform demonstrating the founding team's ability to build and deploy AI at government scale:

- 10,000+ km deployed across Indian highways, expressways, and rural roads
- 9 Indian states with active government infrastructure contracts
- Mines monitoring operations across 4 continents
- Core technology: computer vision pipelines (object detection, classification, anomaly detection) operating at scale
- Recognition: Tech30, India AI Top 10 Startups

**Relevance to Anveshak:** Cognecto proves the team can deliver AI/ML systems that operate reliably at government scale. Computer vision expertise directly transfers to Anveshak's vision module (YOLOv8, CLIP, deepfake detection). Experience navigating Indian government procurement, compliance, and deployment directly informs the IAF deployment plan.

**3. National-Scale Infrastructure Experience**

The CEO was part of the UIDAI (Aadhaar) core infrastructure team — India's national biometric identity programme serving 1.4 billion citizens. This experience with security-critical, nationally-scaled government infrastructure directly informs Anveshak's approach to sovereign deployment, data handling, and defence-grade reliability requirements. Additionally, founding-team experience at BookMyShow (recommendation engine at consumer scale) and multiple Smart City Mission projects demonstrates sustained capability in building technology for large-scale Indian deployments.

**4. Intellectual Property**

The CTO holds 5 US patents and 1 Indian patent, demonstrating sustained innovation and R&D capability.

**5. Drishti — Entity Resolution Platform (Garud Research, Fully Built)**

Cross-domain intelligence fusion platform designed as Anveshak's enterprise complement. Demonstrates capability to architect complex AI systems beyond OSINT. Anveshak's one-directional entity bridge to Drishti is implemented and tested — a ready upgrade path for IAF if cross-domain fusion requirements emerge.
