# Workflow 3: OCTOPUS — AP Coastal Infiltration Risk
## Demo Runbook for Anshul

### Pre-flight Checklist

- [ ] Workflows 1 and 2 completed
- [ ] All containers healthy
- [ ] Browser on Topics page

### Opening Line

> "Final scenario — coastal security. Anveshak monitors the 974 km AP coastline for infiltration signals using text intelligence, image analysis, and geolocation."

### Stage-by-Stage Script

**[0:00] Run seed script**

```bash
python -m demos.ap_police.workflow_3_octopus.seed --replay
```

Say: "Telugu and Tamil Telegram chatter about 'fish cargo' at Machilipatnam and Nizampatnam, plus news reports about suspicious vessel activity. Five content items plus one image for vision analysis."

**[0:30] Point to: Content items with port references**

Show entities: Machilipatnam, Nizampatnam, Kakinada, crypto wallet 0xAB12CD34EF56, @fishcargo_ap.

Say: "NLP extracted port names, crypto wallet addresses, and the Telegram handle across platforms."

**[1:00] Point to: Vision analysis result (the showpiece)**

Navigate to the vision analysis for the pre-seeded result. Show:
- YOLO: boat detected (0.92 confidence), person detected (0.78)
- CLIP: fishing-boat-at-commercial-port (0.73) — not a fishing harbour
- Deepfake score: 0.12 (low — image is authentic)
- EXIF: GPS stripped, timestamp 2:15 AM (anomalous)
- pHash: duplicate found in prior database

**Honest limitation line (drop here):**

> "Deepfake scores are floats 0.0 to 1.0, never boolean. The model gives the signal; the analyst makes the call. Here 0.12 means likely authentic, but the EXIF anomalies and pHash match to a prior flagged image raise different concerns."

**[2:00] Point to: GeoJSON map**

Show Machilipatnam, Nizampatnam, Kakinada, Visakhapatnam pins on the map.

Say: "The AP coastline with all mentioned harbours geocoded. Your OCTOPUS team can see the geographic pattern of the intelligence."

**[2:30] Point to: Narrative cluster**

Show the clustering result.

Say: "All five sources converge on one operational narrative — coordinated nighttime cargo movement along the Machilipatnam-Nizampatnam coast."

**[3:00] Point to: Report with legal mapping**

Show: UAPA 17 (terror finance), 18 (conspiracy), PMLA 3 (money laundering via crypto).

Say: "Legal provisions mapped based on evidence. The crypto wallet trail gives you the financial intelligence for PMLA, while the coordinated operations give you the UAPA elements."

**[3:30] Point to: Inter-agency coordination note (if in report)**

Say: "The report flags that this requires Navy, Coast Guard, and NIA coordination — it's a multi-agency scenario that Anveshak consolidates into one view."

### Close Line

> "Three scenarios, three different wings of AP Police — Cyber, Special Branch, OCTOPUS. One platform. That's the Anveshak proposition for a pilot deployment."

### Failure Recovery

| Failure | Recovery |
|---------|----------|
| Vision results not visible in frontend | Show the seed script console output — it prints all vision metrics. Say: "The vision pipeline completed offline; here are the results." |
| Telugu translation fails | English content carries the scenario. Skip the translation highlight. |
| Report generation slow (>5 min) | Open pre-generated PDF from expected_outputs/. |
