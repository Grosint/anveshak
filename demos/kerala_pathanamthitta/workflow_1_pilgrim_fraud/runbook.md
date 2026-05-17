# Workflow 1: Pilgrim Cyber Fraud Network
## Demo Runbook for Anshul

### Pre-flight (30 sec)
- [ ] `make ps` — all containers healthy
- [ ] `ollama ps` shows qwen2:7b
- [ ] Frontend: http://localhost:3000, logged in
- [ ] Audit Trail tab open
- [ ] Terminal ready

### Opening Line

> "Sir, quick context — I'm an OSINT builder, did 7-8 years in the space before Cognecto, built a tool called Groint that Kerala Police used. Now I'm Solution Architect for Drishti, our sovereign multi-domain intel fusion platform for central agencies. Anveshak is the OSINT pillar of that work — iDEX ADITI 4.0 PS-18 backed, runs entirely on your hardware, your data never leaves your premise. I noticed your district has already partnered with Vi for pilgrim child-safety this season — Anveshak sits in the adjacent layer: fraud detection and disinformation around the same pilgrim base. Let me skip the marketing and show you on a real workflow."

### First Discovery Question

> "Sir, you've been through a full Sabarimala season now and watched pilgrim-targeted cyber fraud grow year-on-year. From your seat, what's the operational gap that, if we closed it before next Mandalam season starts this October-November, would visibly help your unit — the booking-fraud detection side, the season-disinformation side, or the cross-state suspect tracing side?"

### Stage-by-Stage

**[0:00] Run seed**
```bash
python -m demos.kerala_pathanamthitta.workflow_1_pilgrim_fraud.seed --replay
```
Say: "Loading 11 items — Telegram messages in Malayalam and English, Reddit victim reports, and news from Manorama, The Hindu, Mathrubhumi, NDTV."

**[0:30] Content list**
Point to the topic content. Show Malayalam content alongside English.

Say: "Three platforms, two languages. The Malayalam Telegram messages are translated offline via NLLB-200 for entity extraction — the original text is preserved for evidence integrity."

**[1:00] Entities**
Show: UPI (pilgrimstay@ybl), domain (darshanmokshahomestay.in), Telegram handles (@mandalam_yatra_deals, @sabarimala_booking_vip, @pamba_darshan_group), phone (+91-9847123456), locations (Pamba, Erumeli, Nilackal, Pathanamthitta).

Say: "Same UPI handle and fake domain appear on three Telegram channels AND four Reddit threads. Cross-platform convergence — your Cyber PS gets this automatically."

**[1:30] Multi-state aspect**
Point to: Haryana (registration), Tamil Nadu (UPI shell entity), Karnataka (fund routing).

Say: "The operators are in Haryana, the mule account is registered in Tamil Nadu, funds route through Karnataka. Anveshak surfaces this multi-state pattern from open sources before your formal coordination requests go out."

**[2:00] Audit Trail (Tab 2)**
Show the credibility downgrade row.

Say: "Every credibility change is audit-logged. Here — the Telegram source downgraded from 18 to 10 with the reason recorded."

**Honest limitation:**
> "X/Twitter is pay-per-use — we keep a spend guard but it's not free. Telegram and Reddit are where the volume sits for pilgrim-targeting operations."

**[2:30] Report**
Show the intelligence brief (or open PDF).

Say: "The report assembles evidence from high-credibility sources, runs through our local LLM — sovereign, offline — and produces this brief. BNS 318 cheating, IT Act 66C identity theft, 66D cheating via computer resource — mapped against the evidence."

**[3:00] GeoJSON map**
Navigate to: Reports page > select the generated report > click "GIS" tab. MapLibre map renders with location pins.

Show: Pathanamthitta, Pamba, Erumeli, Nilackal, Kochi, Thrissur pins.

Say: "Geographic spread of victim reports and operational locations — your district and beyond. Click any pin for details."

### Close Line
> "This is what Anveshak does for your Cyber Crime PS before Mandalam season opens. We can have it monitoring your real Telegram channels within a week — zero cloud, everything on your infrastructure."

### Failure Recovery
| Failure | Action |
|---------|--------|
| LLM timeout | Show pre-generated PDF from expected_outputs/ |
| Malayalam not translated | "Translation pipeline is active; English content alone produces valid report" |
| No clusters | "Entity convergence across platforms is the signal — clustering threshold is tunable" |
| Frontend stale | Cmd+Shift+R hard refresh |
