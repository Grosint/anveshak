# Workflow 1: Cyber Crime — Investment Scam Ring
## Demo Runbook for Anshul

### Pre-flight Checklist (30 seconds)

- [ ] `make ps` — all 23 containers healthy
- [ ] `ollama ps` shows qwen2:7b loaded (or run `ollama pull qwen2:7b`)
- [ ] Browser Tab 1: Frontend at http://localhost:3000 — logged in as demo@anveshak.local
- [ ] Browser Tab 2: Audit Trail page (Settings > Audit Trail)
- [ ] Browser Tab 3: Terminal ready to run seed script
- [ ] Demo data NOT yet seeded (fresh state preferred; seed script is idempotent if already run)

### Opening Line

> "Let me show you how Anveshak tracks a live cyber fraud operation across Telegram, Reddit, and news sources — and produces a prosecution-ready brief with legal section mapping in under 4 minutes."

### Stage-by-Stage Script

**[0:00] Run the seed script**

```bash
cd /Users/navitas28/Work/anveshak
python -m demos.ap_police.workflow_1_cyber.seed --replay
```

Say: "This loads 11 synthetic OSINT items — Telegram scam messages, Reddit victim reports, and news articles — all tagged as synthetic for audit clarity."

DO NOT over-explain: the data loading step. Let it run.

**[0:30] Point to: Topics page in frontend**

The topic "AP Cyber Fraud: Investment Scam Ring" appears with content count updating.

Say: "Anveshak has ingested content from 3 platforms — Telegram in Telugu and English, Reddit threads, and news articles from Deccan Chronicle, The Hindu, and Times of India."

**[1:00] Point to: Content list for the topic**

Click into the topic. Show content items with source credibility badges.

Say: "Each item carries the source's credibility score at capture time — Telegram channels score 20-25, news outlets 72-85. This flows through to the report."

**[1:30] Point to: Entity extraction panel**

Show extracted entities: UPI IDs (scammer9876@ybl), crypto wallet (0x7a3B...), Telegram handles (@quickprofit_vja), location names (Vijayawada, Guntur, Visakhapatnam).

Say: "NLP extracts entities across all content — the same UPI handle and crypto wallet appear on 3 different platforms. That's the convergence signal."

**[2:00] Point to: Narrative clusters**

Show the Leiden clustering result — one dominant cluster linking all scam-related content.

Say: "The clustering algorithm groups content by narrative. Here it's found one dominant fraud narrative spanning all three platforms."

**[2:15] Point to: Signals panel**

If a signal fired (multi-source convergence), point to it.

Say: "When 3+ independent platforms corroborate the same entity — like this crypto wallet — Anveshak fires an intelligence signal."

**[2:30] Point to: Audit Trail (Tab 2)**

Show the credibility adjustment row: Telegram source downgraded from 25.0 to 15.0 with reason.

Say: "Every credibility change is audit-logged — who changed it, when, old score, new score, and why. This is your evidence chain."

**Honest limitation line (drop here):**

> "X/Twitter is pay-per-use — we keep a spend guard that caps monthly API calls, but it's not free. Telegram and Reddit are where the volume sits for this kind of operation."

**[3:00] Point to: Report page**

The intelligence brief should be generating or complete. Show the PDF.

Say: "The report assembles RAG context from all high-credibility content, runs it through our local LLM — never cloud, sovereign deployment — and produces this brief."

**[3:30] Point to: Legal Provisions table in PDF**

Show the "Applicable Legal Provisions" section with BNS 318, 319, IT Act 66C, 66D, PMLA 3 mappings.

Say: "Each finding is mapped to applicable BNS, IT Act, and PMLA sections. These are AI-generated starting points — they require verification by your legal officer before proceedings."

**[3:45] Point to: GeoJSON map (if visible in frontend)**

Show Vijayawada, Guntur, Visakhapatnam, Kakinada pins on the map.

Say: "Locations mentioned in the evidence are geocoded and displayed. Your analyst can see the geographic spread of the operation."

### Close Line

> "This is what Anveshak does for your Cyber Wing on day one. We can have a pilot running against your real Telegram channels within a week — zero cloud dependency, everything stays on your infrastructure."

### Failure Recovery

| Failure | Recovery |
|---------|----------|
| Ollama hangs (report generation > 5 min) | Open pre-generated PDF from `demos/ap_police/workflow_1_cyber/expected_outputs/workflow_1_report.pdf`. Say: "LLM inference on CPU takes variable time — here's the output." |
| Signal doesn't fire | Skip the signals demo step. Say: "Signal threshold is configurable — for this dataset the convergence threshold needs tuning." Move to report. |
| Telugu content not translated | The English content alone produces a valid report. Note: "Telugu translation pipeline is active but this demo uses primarily English fixtures." |
| Vision model OOM | Not applicable — Workflow 1 has no vision component. |
| Fixture path breaks | Re-run: `python -m demos.ap_police.workflow_1_cyber.seed --replay`. Script is idempotent. |
| Frontend not showing updated data | Hard refresh (Cmd+Shift+R). React Query cache may be stale. |
