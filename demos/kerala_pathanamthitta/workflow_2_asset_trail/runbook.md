# Workflow 2: Multi-State Asset Misappropriation Trail (SYNTHETIC)
## Demo Runbook for Anshul

**IMPORTANT: This is a SYNTHETIC scenario. Do NOT reference any real ongoing case. If the SP asks about a specific real case, say: "This is a synthetic parallel demonstrating the pattern-detection capability — we do not reference active cases in demonstrations."**

### Opening Line

> "Sir, quick context — I'm an OSINT builder, did 7-8 years in the space before Cognecto, built a tool called Groint that Kerala Police used. Now I'm Solution Architect for Drishti, our sovereign multi-domain intel fusion platform for central agencies. Anveshak is the OSINT pillar of that work — iDEX ADITI 4.0 PS-18 backed, runs entirely on your hardware, your data never leaves your premise. I noticed your district has already partnered with Vi for pilgrim child-safety this season — Anveshak sits in the adjacent layer: fraud detection and disinformation around the same pilgrim base. Let me skip the marketing and show you on a real workflow."

### First Discovery Question

> "Sir, you've been through a full Sabarimala season now and watched pilgrim-targeted cyber fraud grow year-on-year. From your seat, what's the operational gap that, if we closed it before next Mandalam season starts this October-November, would visibly help your unit — the booking-fraud detection side, the season-disinformation side, or the cross-state suspect tracing side?"

### Stage-by-Stage

**[0:00] Run seed**
```bash
python -m demos.kerala_pathanamthitta.workflow_2_asset_trail.seed --replay
```
Say: "Ten sources — RTI responses, news articles, Reddit discussion threads, and one Telegram insider channel. All synthetic, demonstrating the pattern."

**[0:30] Entity correlation**
Show: K. Ramachandran (admin officer), P. Sundaram (Chennai jeweller), M. Naveen Pillai (Bengaluru intermediary), Idukki, Chennai Sowcarpet, Bengaluru.

Say: "NLP extracted three persons, three locations, monetary values, and the routing pattern. The same accused names surface across RTI documents, news, and Reddit — cross-source corroboration without manual analysis."

**[1:00] Three-state routing pattern**
Point to: Idukki → Chennai → Bengaluru chain visible in entities.

Say: "The multi-state routing pattern: Kerala source, Tamil Nadu extraction, Karnataka financial routing. Anveshak surfaces this from open sources — your DCRB coordinates the formal investigation across jurisdictions."

**[1:30] Financial indicators**
Show: Rs 18.5 lakh transfers, Rs 2.8 crore estimated value, disproportionate assets.

Say: "Financial signals: transfers exceeding declared income, estimated total value crossing PMLA thresholds. These are leads for your ED coordination, surfaced from RTI responses and public financial discussions."

**Honest limitation (DROP HERE):**
> "Cross-jurisdiction asset trail intelligence is as good as the public-source data. For sealed financial records, we surface signals and leads — the investigator pulls records through legal process."

**[2:30] Report**
Show the intelligence brief.

Say: "PMLA Section 3 money laundering, BNS 316 criminal breach of trust, BNS 61 conspiracy — mapped against the three-state evidence chain. Your legal team verifies the section applicability."

### Close Line
> "This is pattern detection across jurisdictions from open sources. When your DCRB gets a tip, Anveshak has already mapped who, where, and the routing — from publicly available information."

### Failure Recovery
| Failure | Action |
|---------|--------|
| SP asks about real case | "Synthetic parallel only — we don't reference active proceedings" |
| Report slow | Show pre-generated PDF |
| Entities incomplete | Focus on the three-state routing pattern visible in content |
