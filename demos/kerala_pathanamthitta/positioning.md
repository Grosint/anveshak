# Anveshak — Positioning for Kerala Police

## Officer Profile

Anand R, IPS (Kerala 2016 batch), has been Pathanamthitta DPC since August 2025 — a full Sabarimala season under his command. Prior posting: DCP VIP Security, Kerala — high-security operational background, not tech-architecture. Posted to Pathanamthitta specifically for pilgrimage-season operational expertise. In November 2025 he publicly launched the Vi Suraksha pilgrim child-safety wristband partnership, demonstrating openness to private-tech collaborations during Sabarimala season. Frame Anveshak as the adjacent digital-safety layer to Vi's physical-safety layer.

## Where Anveshak Sits

Anveshak is a **sovereign OSINT intelligence layer** — it does not replace your AI-driven SOC (C-DOT built, defensive posture) but feeds INTO it with open-source intelligence from social media, web, and dark web. Your SOC detects attacks on your infrastructure; Anveshak detects threats IN the information environment before they hit your infrastructure or your streets.

**Your existing stack (we complement, not compete):**

- Kerala AI SOC → defensive cyber operations, alert triage, incident response
- Microservices/K8s on SUSE → your operational platform (Anveshak runs on similar infra)
- Kerala Cyber Safety Protocol 2026 → policy framework for deepfakes/SGI — Anveshak is the **detection engine** that operationalises this protocol

**Anveshak adds:**

- Multi-platform OSINT ingestion (Telegram, Reddit, web, X) with sovereign NLP
- Narrative clustering + signal engine for convergence detection
- Vision pipeline: deepfake/SGI detection (0.0–1.0 scores, never boolean)
- Prosecution-ready report generation with BNS/IT Act section mapping
- Full audit trail for evidence chain integrity

## Open Architecture

Your officers can extend:

- **Source adapters** — Python classes following SourceAdapterBase contract; add new platforms without touching core
- **Geocoder overlays** — JSON files for Kerala-specific locations
- **LLM prompt templates** — Jinja2 templates, no code changes needed for new report types
- **Signal thresholds** — per-topic configuration via API, no restarts

Everything is Python + PostgreSQL + Redis. No vendor lock-in beyond Ollama (which runs any GGUF model).

## Anticipated Questions

**"How fast does a signal surface after a fraud ring goes active during pilgrim season?"**
> Tunable; signals surface within seconds in replay. Live ingestion latency is bounded by source rate limits — Telegram near-real-time, Reddit minutes. Tuned for season-load before Mandalam ramp.

**"If my Cyber Crime PS analyst flags a false positive, does the system learn?"**
> Credibility scores update via audit-logged manual override and feed forward. Continual learning on NER and clustering is roadmap, not deployed — honest about it.

**"Sabarimala season is November to January. Can a pilot be live and useful by October?"**
> Yes if we start scoping in the next two weeks. 30 days deployment + 30 days tuning on your historical fraud patterns = ready before Mandalam opens.

**"What happens to our data if we decommission the box?"**
> Your hardware, your disks, your call. Secure-wipe runbook provided. Nothing phones home, no cloud copy ever.

**"How does this sit alongside the AI SOC the state launched last year?"**
> Different category. The C-DOT SOC is defensive cybersec on police networks. Anveshak is offensive open-source intelligence on external content — fraud sites, scam Telegram channels, disinformation. We feed signals; we don't compete.
