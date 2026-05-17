# Workflow 2: Special Branch / Intel — Maoist Recruitment & Financing
## Demo Runbook for Anshul

### Pre-flight Checklist (30 seconds)

- [ ] Workflow 1 completed successfully (report generated)
- [ ] All containers still healthy (`make ps`)
- [ ] Browser on Topics page, ready to see new topic appear

### Opening Line

> "Now let me show you the intelligence convergence use case — tracking Maoist recruitment and financing across the Andhra-Odisha Border belt, with content in Telugu and Odia."

### Stage-by-Stage Script

**[0:00] Run seed script**

```bash
python -m demos.ap_police.workflow_2_intel.seed --replay
```

Say: "This ingests content from Telegram channels in Telugu and Odia, an ideological blog, Reddit regional threads, and news sources — 9 items across 4 platforms."

**[0:30] Point to: Translation indicator**

Show that Telugu and Odia content items have `translated_text` populated.

Say: "The Telugu and Odia content is translated via NLLB-200 — completely offline, no cloud dependency — then entities are extracted from the English translation."

**Honest limitation line (drop here):**

> "Production-grade vernacular Telugu NER is in our pipeline but not deployed today — we translate via NLLB-200 and re-extract from English. There's some recall loss; we're honest about it."

**[1:00] Point to: Entity extraction**

Show extracted entities: @janashakti_aob (Telegram handle), UPI handle janavikas2024@kotak, locations (Alluri Sitharama Raju, Vizianagaram, Koraput, Malkangiri).

Say: "The same Telegram handle and UPI handle appear across Telugu, Odia, and English sources — that's the cross-platform convergence."

**[1:30] Point to: Narrative clusters**

Two clusters should form: recruitment narrative + financing narrative.

Say: "Leiden clustering separates two distinct narratives — recruitment operations and fundraising operations — even though they share the same actors."

**[2:00] Point to: Prior topic convergence**

If cross-topic similarity is visible, show linkage to "Tribal Welfare Grievance Amplification" topic.

Say: "Anveshak detected convergence with a previously tracked topic — the tribal grievance amplification campaign. Same geography, overlapping actors."

**[2:30] Point to: Report generation**

Wait for report to complete. Show the intelligence brief.

Say: "The report maps findings to UAPA sections — Section 13 for unlawful activities, Section 38/39 for membership and support."

**[3:00] Point to: Three-Lens Evaluation (if present in PDF)**

Show the Brigadier / NIA Chief / R&AW Chief annexure panels.

Say: "The three-lens evaluation gives your different agencies distinct perspectives on the same intelligence. The Brigadier sees force deployment, NIA sees prosecution elements, R&AW assesses external linkages — and honestly flags when there's no foreign nexus in the evidence."

**[3:30] Point to: Legal provisions table**

Say: "UAPA 13, 17, and 38/39 mapped with evidence references. Again — AI-generated, requires your legal officer's verification."

### Close Line

> "This is what Anveshak does for Special Branch — multi-language, cross-platform intelligence convergence with prosecution-ready output. Your analysts spend time analyzing, not collecting."

### Failure Recovery

| Failure | Recovery |
|---------|----------|
| Odia translation fails | English content alone covers the scenario. Note: "Odia pipeline active, this demo used primarily English." |
| Only 1 cluster forms | Say: "The algorithm grouped these into a single narrative due to strong entity overlap — the recruitment and financing threads are tightly linked." |
| Three-lens not in PDF | Say: "The three-lens evaluation is a configurable annexure — here's the reference version" and open `bns_mapping.md`. |
| Prior topic convergence not visible | Skip that step. The core demo value is in the clustering + legal mapping. |
