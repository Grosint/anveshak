# Workflow 3: SGI/Deepfake Detection — Sabarimala Season Disinformation
## Demo Runbook for Anshul

### Opening Line

> "Sir, quick context — I'm an OSINT builder, did 7-8 years in the space before Cognecto, built a tool called Groint that Kerala Police used. Now I'm Solution Architect for Drishti, our sovereign multi-domain intel fusion platform for central agencies. Anveshak is the OSINT pillar of that work — iDEX ADITI 4.0 PS-18 backed, runs entirely on your hardware, your data never leaves your premise. I noticed your district has already partnered with Vi for pilgrim child-safety this season — Anveshak sits in the adjacent layer: fraud detection and disinformation around the same pilgrim base. Let me skip the marketing and show you on a real workflow."

### First Discovery Question

> "Sir, you've been through a full Sabarimala season now and watched pilgrim-targeted cyber fraud grow year-on-year. From your seat, what's the operational gap that, if we closed it before next Mandalam season starts this October-November, would visibly help your unit — the booking-fraud detection side, the season-disinformation side, or the cross-state suspect tracing side?"

### Stage-by-Stage

**[0:00] Run seed**
```bash
python -m demos.kerala_pathanamthitta.workflow_3_sgi_deepfake.seed --replay
```
Say: "Malayalam and Hindi Telegram channels pushing inflammatory content about 'violence at Pamba.' Plus three images for vision analysis."

**[0:30] Content + entities**
Show: @sabarimala_truth_ml, @sabarimala_truth_hindi handles, Pamba, Nilackal, Sannidhanam locations.

Say: "Two coordinated channels — one Malayalam for local reach, one Hindi for national amplification. Same playbook that runs every season."

**[1:00] VISION — THE SHOWPIECE**

Show the 3 pre-seeded vision results:

**Image 1 — Staged victim face photo:**
Say: "Deepfake score 0.87 — high probability this face is synthetic. EXIF shows November 2024, not current season. GPS stripped. The model gives the score; your analyst makes the call."

**Image 2 — Doctored crowd scene:**
Say: "Score 0.72. CLIP classifies this as an indoor event hall, not Pamba riverside — location-claim mismatch. GPS points to a hall in Kottayam. And the perceptual hash matches a known stock photo from our database."

**Image 3 — Legitimate press photo:**
Say: "Score 0.08 — authentic. GPS matches Sannidhanam, timestamp consistent, professional camera. This is your baseline for comparison."

**Honest limitation (DROP HERE):**
> "Deepfake scores are floats, 0.0 to 1.0, never boolean. Production-grade Malayalam NER is on our roadmap — today we translate and re-extract. There's recall loss; we're honest about it."

**[2:30] Convergence**
Show narrative clustering or cross-topic link.

Say: "Text disinformation + visual SGI detection + metadata anomalies — all converging on the same coordinated campaign. That's the signal your Special Branch acts on."

**[3:00] Report**
Show report with legal mapping reference.

Say: "BNS 196 promoting enmity, BNS 353 public mischief, plus the SGI provisions under your new Kerala Cyber Safety Protocol. The report gives your IG Cyber Operations the technical evidence for platform takedown coordination."

### Close Line
> "Your Kerala Cyber Safety Protocol 2026 gives you the legal framework. Anveshak gives you the detection engine. Together, you're ahead of the disinformation cycle — detecting SGI before it goes viral, not after."

### Failure Recovery
| Failure | Action |
|---------|--------|
| Vision data not visible | Show seed script console output with all 3 scores |
| Malayalam not translated | English content carries the scenario |
| Report slow | Open pre-generated PDF |
