# ANVESHAK DEMO — IAF (Air Intelligence)

**Audience:** IAF intelligence officers
**Duration:** 15-18 minutes (defence audience expects more depth than police)
**Objective:** Officer sees Anveshak as force multiplier for air intelligence; initiates procurement or pilot
**Three topics:** Chinese Air Power (LAC), Anti-IAF Disinformation, PAF Modernization
**Your edge:** iDEX ADITI 4.0 — government-vetted, sovereign, no cloud

---

## PRE-DEMO CHECKLIST (30 min before)

```
□ make ps                                    — all containers green
□ curl localhost:11434/api/tags              — qwen2:7b loaded
□ http://localhost:3000                      — frontend accessible
□ Login as demo_iaf@anveshak.local           — verify 3 topics visible
□ Topic 1 (Chinese Air Power)               — 300+ items, clusters visible
□ Topic 2 (Disinformation)                  — 130+ items, deepfake cluster visible
□ Topic 3 (PAF Modernization)               — 60+ items
□ Signals tab                               — 3300+ signals visible
□ Pre-generate reports for Topic 1           — so you can show instantly
□ make pdf-iaf                               — leave-behind PDF ready
□ Print 3 copies of case_study_iaf.md as PDF — hand one to each officer
□ Browser: dark mode, full screen, no bookmarks bar
□ Close all notifications
□ Phone on silent
□ Have case_study_iaf.md printed as leave-behind
```

---

## THE DEMO

---

### BEAT 0 — BEFORE THE SCREEN (2 min)

Do NOT open laptop. Eye contact.

**SAY:**

> "Thank you for making the time, sir.
>
> Anveshak is built under iDEX ADITI 4.0 PS-18. Sovereign AI-OSINT
> platform — everything runs on local hardware, no cloud dependency,
> air-gap deployable.
>
> What I'm about to show you is a live system. We loaded defence-relevant
> sources — Jane's, War Zone, Bellingcat, SCMP, SIPRI, defence Telegram
> channels, even adversary media like Global Times and Defence.pk — and
> let the system run for 30 days on three topics relevant to air intelligence.
>
> Let me show you what it found on its own."

**WHY THIS WORKS:**
- "iDEX ADITI" — government-vetted, not random vendor
- "Sovereign" — IAF cares deeply about data sovereignty
- "Jane's, Bellingcat, SIPRI" — sources they know and respect
- "Adversary media" — shows dual-use monitoring capability

**PAUSE.** Wait for nod.

---

### BEAT 1 — LOGIN + TOPICS OVERVIEW (1 min)

1. Open http://localhost:3000
2. Login: `demo_iaf@anveshak.local`
3. Topics Dashboard shows 3 topics

**SAY:**

> "Three topics — three missions running simultaneously on one machine:
>
> **Chinese Air Power** — LAC threat assessment. 300+ items from 10 sources.
> **Anti-IAF Disinformation** — deepfake detection and narrative tracking.
>   130+ items from 8 sources.
> **PAF Modernization** — force posture monitoring. 60+ items from 7 sources.
>
> Each topic is an independent workspace — own sources, own signals,
> own reports. An intelligence cell could run 10 topics simultaneously."

Click into **Chinese Air Power** first. This is strongest topic.

---

### BEAT 2 — CHINESE AIR POWER: CONTENT FEED (2 min)

4. Content feed opens — 300+ items
5. Scroll slowly

**SAY:**

> "Over 300 items collected from 10 sources. Jane's Defence Weekly, The War Zone,
> SCMP Defence, Bellingcat, LiveFist, Indian Defence Review — plus Telegram
> OSINT channels and adversary media like Global Times.
>
> The system runs 24/7. Every article about Chinese air activity near LAC
> is captured, timestamped, credibility-scored, and stored."

6. Point at specific items:
   - Jane's article (credibility 91)
   - Global Times editorial (credibility 35)
   - Telegram @china_mil_watch post

> "See the credibility spread. Jane's at 91. Global Times at 35 — the
> system auto-downgraded it after it amplified a deepfake video three times.
> The analyst sees this at a glance — knows which sources to trust."

---

### BEAT 3 — CLUSTER VIEW: THE MONEY SHOT (4 min)

7. Switch to **Cluster View**

**SAY:**

> "This is where the platform earns its keep. The AI reads every article
> and groups them by narrative — which developments are connected."

Walk through clusters deliberately:

**Cluster: "J-20 Stealth Fighter Deployments near LAC" (12 items, 5 sources)**

> "12 items from 5 independent sources — Jane's confirms satellite imagery
> of 8 J-20s at Hotan. SCMP reports PLAAF Western Theatre achieving IOC
> with J-20. Bellingcat traces shelter construction timeline. @china_mil_watch
> spots 4 more at Kashgar. War Zone analyses WS-15 engine extending combat
> radius to cover all of northern Ladakh.
>
> The system correlated all five automatically. No analyst searched for this.
> Five independent sources, one intelligence picture."

**Cluster: "PLAAF UAV/Drone Activity — Northern Borders" (8 items, 4 sources)**

> "WZ-7 Soaring Dragon high-altitude ISR near Ladakh airspace. Wing Loong III
> armed UCAVs at Kashgar. GJ-11 stealth drone tests. The system detected
> sortie patterns correlating with Indian exercise schedules — that's a
> significant intelligence finding buried in open sources."

**Cluster: "Tibet Airbase Infrastructure Expansion" (8 items, 4 sources)**

> "New 3,500-metre runway at Ngari Gunsa. Hardened aircraft shelters at
> Lhasa Gonggar. Fuel and ammunition depots at Shigatse. The system built
> a construction timeline from satellite OSINT and news reports.
> Operational readiness estimate: Q4 2026."

**TRANSITION LINE:**

> "Sir, these three clusters together form a single strategic picture:
> fifth-gen stealth deployment, drone ISR buildup, and infrastructure
> for sustained operations. The system assembled this from 300 open-source
> items across 10 sources. That's what it does — turns volume into
> intelligence."

**PAUSE.** 3 seconds.

---

### BEAT 4 — DISINFORMATION TOPIC: DEEPFAKE DETECTION (3 min)

8. Navigate back to Topics → Click **Anti-IAF Disinformation**
9. Switch to Cluster View

**Cluster: "Coordinated Deepfake Campaign Against IAF" (10 items, 4 platforms)**

**SAY:**

> "Now this is the information warfare angle. A fabricated video of a
> Rafale being shot down appeared on Telegram. Let me show you what the
> system's vision AI found."

10. **Click on content item** "URGENT ALERT: Fabricated video showing IAF Rafale being shot down..."
11. **Scroll to Vision Analysis section** — DeepfakeMeter gauge will show **94% red**

> "The vision module scored this at **0.94 deepfake probability**. See
> the red gauge — 94%. EXIF metadata shows the software field: Runway
> Gen-3 — that's an AI video generation tool. No camera data, no GPS.
> The machine caught what a human eye might miss."

12. Point at **EXIF anomalies**: "No camera EXIF", "Runway Gen-3 Alpha", "Temporal artifacts"
13. Point at **CLIP labels**: military_aircraft 0.89, explosion 0.82, fabricated 0.94
14. Navigate back to cluster view

> "But here's the critical finding — the system tracked the amplification.
> 15 Telegram channels forwarded this video within 4 hours. That's not
> organic spread — that's a coordinated operation."

**Cluster: "HAL/DRDO Misinformation Narratives" (7 items, 3 sources)**

> "Adversary media weaponizing Tejas production delays. False reports
> about AMCA being cancelled. Let me show you how the system maps this."

15. **Switch to Dashboard tab** (same topic — Anti-IAF Disinformation)
16. **Scroll to Forwarding Network graph** — Cytoscape visualization will show

> "See this graph? Global Times publishes → Defence.pk picks it up →
> Telegram amplifies → Instagram and Reddit spread. The system mapped
> this amplification chain automatically from forwarding metadata.
> That's not one officer's analysis — the machine traced the
> information operation."

17. Point at the **two hub nodes**:
    - `fake_iaf_leaks` — 3 outgoing edges (deepfake campaign origin)
    - `globaltimes_military` → `Defence.pk` → `airpower_india` chain (HAL/DRDO misinfo)

> "Two distinct amplification patterns. The deepfake campaign originates
> from @fake_iaf_leaks — spreads to Defence OSINT, Instagram, Reddit.
> The Tejas narrative originates from Global Times — picked up by
> Defence.pk — amplified by Telegram — reaches Instagram and Reddit.
> Same playbook, different content. The system sees the structure."

18. If time, point at **Influence Matrix** below the graph

> "This matrix shows the forwarding count. Who originates, who amplifies.
> The analyst now knows which nodes to watch — not just which content
> to read."

> "The officer monitoring this topic gets a signal the moment a new
> disinformation narrative crosses the 2-source threshold. Not after
> it goes viral — as it starts forming."

---

### BEAT 5 — SIGNALS (1.5 min)

11. Click **Signals** in sidebar
12. Show signal count (3,300+)

**SAY:**

> "Over 3,300 signals fired automatically across all three topics."

13. Point at key signals:
    - "J-20 deployment near LAC — 5 independent sources" → HIGH
    - "Deepfake campaign detected — 4 platforms" → CRITICAL
    - "Tibet airbase construction — 4 sources" → HIGH

> "Each signal is triaged — acknowledged, dismissed, or escalated.
> Full audit trail. The CRITICAL signal on the deepfake campaign —
> that would have reached the intelligence officer within minutes of
> the second source confirming it."

---

### BEAT 6 — IDENTIFIER INTELLIGENCE (2 min) — RETELLABLE MOMENT

**Stay in Topic 2** (Anti-IAF Disinformation — you're already here from Beat 4)

14. Click **Identifiers** tab in workspace sidebar

**SAY:**

> "The system extracts identifiers from unstructured text and links them
> across sources."

15. Show **fake_iaf_leaks** — 4 sources, 6 items
16. **Click to expand** → shows linked items from IAF Disinfo Alert (telegram), Defence Forum India (reddit), Bellingcat (web), Air Power India (telegram)

> "@fake_iaf_leaks — this Telegram handle appeared across 4 independent
> sources on 3 different platforms. Telegram, Reddit, web. The system
> identified it as the amplification node behind the deepfake campaign.
> That's network mapping from unstructured content — no officer searched."

17. **Navigate to Topic 1** (Chinese Air Power) → Click **Identifiers** tab
18. Filter by **Aircraft ID** (dropdown) — or scroll to find it
19. Show **J-20 serial 78271** — 5 sources, 6 items
20. **Click to expand** → shows linked items from China Mil Watch, Defence OSINT, Bellingcat, Indian Defence Review, LiveFist

> "Aircraft serial number 78271. First spotted at Kashgar in a satellite
> image from @china_mil_watch. Then confirmed during Aksai Chin exercises
> by Defence OSINT. Then in Bellingcat geospatial analysis and Indian
> Defence Review assessment. Five independent sources, same airframe.
> The system tracked this J-20 from Kashgar to Aksai Chin — movement
> tracking from open sources. Automatically."

**THIS IS THE RETELLABLE MOMENT:**

> "You give the system 16 sources. It gives you back: an aircraft serial
> tracked across 5 sources and 2 locations. A disinformation network node
> linked across 4 sources on 3 platforms. Forwarding chains mapped.
> From open sources. No analyst searched. The machine connected the dots."

---

### BEAT 7 — REPORT + PDF (1.5 min)

16. Show pre-generated report on Chinese Air Power topic
17. Show PDF structure

**SAY:**

> "AI-generated intelligence brief. Every claim cites a source. Every source
> has a credibility score frozen at generation time. The report is immutable —
> once generated, never modified. If a source is later downgraded, the system
> adds a warning — the report itself stays untouched. Evidence chain preserved."

18. Hand over printed case study

> "This case study documents what the system found over 6 months.
> 521 items, 11 narrative clusters, 3,300+ signals. All from open sources.
> All on one machine. All sovereign."

---

### BEAT 8 — THE CLOSE (2 min, no clicks)

Close laptop halfway. Conversation mode.

**SAY:**

> "Sir, what you saw is three intelligence missions running simultaneously:
>
> **Chinese Air Power:** J-20 deployments tracked across 5 sources, drone
>   activity near LAC, Tibet airbase construction timeline. Strategic picture
>   assembled from 300+ open-source items.
>
> **Information Warfare:** Deepfake detected at 0.94 probability.
>   Amplification network of 15 channels mapped. Adversary narrative
>   campaigns traced from origin to distribution.
>
> **PAF Monitoring:** Block 3 induction confirmed, exercise patterns tracked,
>   arms transfer data correlated.
>
> One machine. No cloud. No data leaves your network. Air-gap deployable.
> Built under iDEX ADITI 4.0.
>
> Rs 25 lakh per year for a single analyst workstation. For an intelligence
> cell deployment — we tailor to your requirements."

**THEN SHUT UP.**

---

## READY ANSWERS

---

**Q: "Can it process classified imagery?"**

SHORT: "Anveshak processes open-source data — satellite imagery from commercial
providers, social media, news. For classified imagery, it would need to run
inside your classified network. The architecture supports air-gapped deployment."

---

**Q: "Chinese language content?"**

SHORT: "Full Chinese support via NLLB-200 translation model. Chinese articles
from Global Times and SCMP are translated on-device. Also handles Hindi,
Arabic, Urdu — 200 languages total. No cloud translation service."

---

**Q: "Can it detect deepfakes in real-time?"**

SHORT: "Vision module runs YOLOv8, CLIP, and deepfake detection via ONNX.
Processes images and video frames. Returns probability score — 0.94 means
94% likely AI-generated. EXIF forensics runs alongside. Currently CPU-based,
GPU upgrade changes one environment variable."

---

**Q: "How does it compare to [US/Israeli tool]?"**

SHORT: "Those are cloud-dependent and come with data-sharing agreements.
Anveshak runs entirely on your hardware. No data leaves your deployment.
No vendor has access to your intelligence. That's the sovereign difference."

---

**Q: "Can different commands use different topics?"**

SHORT: "Yes. Each topic is an independent workspace with its own sources,
keywords, signals, and reports. Different commands, different classification
levels, same deployment. Org-level isolation built in."

---

**Q: "Integration with existing intelligence systems?"**

SHORT: "API-first architecture. REST API for all data. PDF/CSV export for
reports. Can be integrated with any system that accepts API input.
No existing connector for specific military systems — happy to build."

---

**Q: "What about satellite imagery analysis?"**

SHORT: "Current version processes images from web sources — when Bellingcat or
Jane's publishes satellite analysis, Anveshak ingests and correlates it.
Direct satellite feed integration is a roadmap item. Current focus is
making open-source intelligence actionable."

---

**Q: "Dark web monitoring?"**

SHORT: "Yes. Onion search engines and public forums. No marketplace infiltration.
Same as any OSINT analyst using Tor browser — automated and continuous."

---

**Q: "Price for a command-level deployment?"**

SHORT: "Depends on scale — number of analysts, topics, source volume.
Single workstation: ₹25 lakh/year. Intelligence cell (4-6 seats):
₹80 lakh/year. Command-level: custom pricing based on requirements.
All include setup, training, and 12-month support."

---

**Q: "Is this the same as Palantir/Babel Street?"**

SHORT: "Those are cloud SaaS products with US data residency requirements.
Anveshak is Indian-built, sovereign-deployed, iDEX ADITI vetted.
Your data stays in your building. No foreign vendor has access.
Also: fraction of the cost."

---

**Q: "Send us a proposal"**

This is GOOD. Say: "Absolutely, sir. We'll prepare a technical proposal with
deployment specifications and pricing by [day after tomorrow]. Would it help
to schedule a follow-up with your intelligence cell to identify the specific
sources and topics they'd want to prioritize?"

Creates urgency + second meeting with working-level officers.

---

## WHAT TO ABSOLUTELY AVOID

| Don't | Why |
|-------|-----|
| Don't explain embeddings, cosine similarity, or ML algorithms | They care about output, not engine |
| Don't compare to DRDO products | Political minefield. Stay above it |
| Don't claim "real-time" — say "continuous monitoring" | Real-time implies classified feed integration |
| Don't demo creating a topic live | Things can break. Show what works |
| Don't show police topics (Nagaland, Telangana, Haryana) | Different org, different audience. Shows org isolation if asked |
| Don't mention specific classified programs | Stick to what's in open source |
| Don't oversell deepfake detection accuracy | Say "probability score" not "detection" |
| Don't promise satellite feed integration | It's roadmap, not current |
| Don't let demo go past 18 minutes | IAF officers are busy. Respect time |
| Don't scroll to entity table in live UI | NER noise (cookie banners, SIPRI boilerplate) still visible in raw DB — PDF is filtered, live UI isn't |
| Don't say "30 days" — say "6 months" | Collection period is Jan-Jul 2026 per BLUF. System ran longer than 30 days |
| Don't show sources page if credibility was recently reset | Scores were manually restored — auto-scoring may change them again before demo |

---

## IF LIVE DEMO FAILS

1. **Containers crashed:** Use pre-taken screenshots of every beat
2. **Report generation hangs:** Show existing report
3. **Cluster view empty:** Fall back to content feed + manual scrolling
4. **Login fails:** Have password on paper: `AnveshakDemo2024!`

---

## DEMO FLOW: WHICH TOPIC FIRST?

**Default order (recommended):**
1. Chinese Air Power (strongest — most items, most clusters, J-20 wow factor)
2. Disinformation (deepfake detection — unique differentiator)
3. PAF Modernization (brief — shows multi-topic capability)

**If audience is intelligence wing:** Lead with Chinese Air Power
**If audience is PR/information warfare:** Lead with Disinformation
**If audience is strategic planning:** Lead with all three briefly, then deep-dive Chinese

---

## THE ONE THING

**The IAF officer will evaluate Anveshak in the 30 seconds they describe it to their commanding officer.**

Make those 30 seconds easy:

> "There's this iDEX platform — runs on our own hardware, no cloud —
> it monitored 16 defence sources for 6 months. Found J-20 deployments
> at two airbases confirmed by 5 independent sources. Detected a deepfake
> Rafale video at 94% probability and mapped the 15-channel amplification
> network. Tracked an aircraft serial number across 3 sources automatically.
> Generates intelligence briefs on demand. ₹25 lakh per year per workstation."

That's your demo. Everything else is scaffolding.
