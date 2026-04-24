# Anveshak — Demo Script

## THE STORY (Tell this before touching the screen)

### The Problem (Why)

Every day, defence forces and law enforcement agencies face a flood of open-source
information — news sites, Telegram channels, social media, satellite imagery forums.
An intelligence analyst might need to track 50+ sources across 5 languages just for
one topic. Today this is done manually — copy-pasting links into spreadsheets,
eyeballing images for fakes, writing reports from memory.

Three critical problems:

1. **Volume.** No human can read 200 articles a day across Hindi, Urdu, Chinese, and
   English — and catch the one that matters.

2. **Trust.** A source that was reliable last month may be compromised today.
   There's no systematic way to track source credibility over time, and no audit
   trail when it changes.

3. **Speed.** By the time an analyst manually writes a report, the situation has
   already evolved. Decision-makers get stale intelligence.

### The Solution (What)

Anveshak (अन्वेषक — "the seeker") is a sovereign AI-powered OSINT platform that
automates the entire intelligence cycle:

**Collect → Analyse → Alert → Report**

- It crawls open web sources and social platforms automatically
- It translates multilingual content into English in real-time
- It clusters related narratives and detects when independent sources corroborate a story
- It fires real-time signals to the analyst when something crosses a threshold
- It detects deepfakes and manipulated images using on-device AI
- It generates auditable, traceable intelligence reports grounded in source evidence

### Why Sovereign (How it's different)

**Everything runs on one machine. No cloud. No data leaves the deployment boundary.**

- LLM inference runs locally via Ollama — no OpenAI, no cloud API
- All data stays in a local PostgreSQL database
- No internet dependency once sources are configured
- Deployable on a single laptop or a rack server — hardware-independent

This is not a SaaS product. This is a tool you own, you control, and you audit.

---

## THE DEMO (Step by step)

### Pre-demo checklist

- [ ] All 19 containers running (`make ps`)
- [ ] Ollama has `qwen2:7b` loaded (`curl localhost:11434/api/tags`)
- [ ] Frontend accessible at http://localhost:3000
- [ ] 3 active topics with scraped content already present
- [ ] Browser in dark mode, full screen, no bookmarks bar

### Current demo data

| Entity | Count |
|--------|-------|
| Topics | 3 (China-Pak Mil Coop, UAV Northern Borders, Disinfo Ops) |
| Sources | 6 (4 web, 1 Telegram, 1 manual) |
| Content items | 614 |
| Narrative clusters | 83 |
| Signals | 96 |
| Reports | 1 |
| User | demo@anveshak.local |

---

### Act 1 — Login & First Impression (30 seconds)

1. Open http://localhost:3000
2. **Pause** on the login screen — point out:
   - "Unclassified · For Official Use Only" classification bar
   - Animated Anveshak mark (breathing ring + radar scan dots)
   - अन्वेषक in Devanagari — "the seeker"
3. Login: `demo@anveshak.local` / (your password)
4. You land on the **Topics Dashboard** — this is the analyst's home

**Say:** "This is the analyst workbench. Everything an intelligence officer needs
is in one place — topics they're monitoring, signals that need attention, sources
they trust, and reports they've generated."

---

### Act 2 — Topics & Live Content (2 minutes)

5. Point out the 3 active topics on the dashboard:
   - Each card shows content count, signal count, and status
6. Click **"China-Pakistan Military Cooperation"** → Content Feed opens
7. **Scroll the feed** — show:
   - Content cards with platform badges (Web, Telegram)
   - Credibility score on each card (colour-coded: green/yellow/red)
   - Language tags — some content is Hindi/Chinese, with "Translated" badge
   - Captured timestamps showing continuous collection

**Say:** "The scraper runs 24/7. It crawled 614 items across these 3 topics. Content
in Chinese or Hindi is automatically translated to English using an on-device NLLB
model — no cloud translation API."

8. **Toggle to Cluster View** — show narrative clusters:
   - Clusters group semantically similar articles
   - Each cluster shows a label and independent source count
   - "When 3+ independent platforms report the same narrative, a signal fires"

9. **Demonstrate Semantic Search:**
   - Type a natural language query: `"drone technology transfer"`
   - Show results ranked by pgvector cosine similarity
   - "This isn't keyword search — it understands meaning"

---

### Act 3 — Signals Inbox (1.5 minutes)

10. Click **Signals** in the sidebar (note the red badge count)
11. Show the **New** tab — 96 signals waiting for triage
12. Point out a signal card:
    - Severity (HIGH/MED/LOW)
    - Signal type (CLUSTER_FORMATION, ENGAGEMENT_SPIKE)
    - Cluster label + independent source count
    - Timestamp

**Say:** "A signal fires when multiple independent sources — say a news site,
a Telegram channel, and a Reddit post — all report the same narrative. The analyst
doesn't have to hunt for this. The system surfaces it."

13. Click **Acknowledge** on one signal — it moves to the Acknowledged tab
14. Click **Dismiss** on another — it moves to Dismissed
15. Click a signal card → it navigates to the topic feed filtered to that cluster

**Say:** "Every signal is traceable. You can see exactly which sources triggered it,
when, and what content was in the cluster."

---

### Act 4 — Source Credibility & Audit Trail (1.5 minutes)

16. Click **Sources** in the sidebar
17. Show the source list:
    - Health status indicators (green dot = healthy, red = down)
    - Credibility bars (0–100 scale)
    - Platform badges
    - Sort order: Down → Degraded → Unverified → Healthy

18. Click on a source to open the detail pane
19. Show the **Audit Log** tab:
    - Every credibility change is logged with timestamp, old/new score, reason
    - "This is immutable. Nobody can silently change a source's trustworthiness."

20. **Demonstrate a credibility update:**
    - Click "Update Credibility"
    - Change score and add a reason: "Source published retracted article on 2026-04-20"
    - Save — show the new audit log entry appear

**Say:** "Source credibility isn't a gut feeling. It's a scored, audited, versioned
attribute. When a report cites a source, the credibility score at that exact moment
is snapshot into the report. If the source is later downgraded, the system warns —
but the original report is never modified."

---

### Act 5 — Vision & Deepfake Detection (2 minutes)

21. Click **Image Analysis** in the sidebar
22. **Prepare a test image** — drag and drop it onto the upload zone
23. Wait for the async analysis job to complete (5–15 seconds)
24. Walk through the 4 tabs:

    **Deepfake tab:**
    - Deepfake probability score (float 0.0–1.0)
    - "This is a probability, not a yes/no. The analyst decides the threshold."

    **Objects (YOLO) tab:**
    - Bounding boxes drawn on the image
    - Detected objects with confidence percentages
    - "Military vehicle detection, aircraft identification — runs on-device"

    **EXIF tab:**
    - Camera metadata table
    - GPS coordinates (if present), timestamps
    - "Forensic metadata — was this image taken where they claim?"

    **Reverse Search tab:**
    - pHash-based near-duplicate detection
    - "Has this exact image appeared before in our corpus? Catch recycled propaganda."

**Say:** "All of this runs locally — YOLOv8, CLIP, DIRE deepfake detection — no cloud
API. An image uploaded here never leaves this machine."

---

### Act 6 — Report Generation (2 minutes)

25. Click **Reports** in the sidebar
26. **Generate a new report:**
    - Select topic: "China-Pakistan Military Cooperation"
    - Report type: **Intelligence Brief**
    - Time window: 72 hours
    - Min credibility: 30
    - Click "Generate Report"

27. Show the status: "Generating..." with polling indicator
28. While waiting (~30–60 seconds), explain:

**Say:** "The report is generated by a local LLM — qwen2:7b running on Ollama.
It uses RAG — retrieval-augmented generation. It pulls the actual content items
from the database, grounds every claim in source evidence, and validates the output
through a Pydantic schema before storing it. No hallucinations pass through."

29. When complete, show:
    - **Report tab:** Markdown-rendered intelligence brief
    - Source citations inline: [Source: domain.com]
    - Confidence score and metadata
    - **Download PDF** button

30. Switch to **GIS Map** tab:
    - Show entities and locations plotted on a MapLibre map
    - "Every location mentioned in the report is automatically geocoded"

31. Switch to **History** tab:
    - Show the list of previous reports
    - "Reports are immutable snapshots. If something changes, generate a new one.
      The old one is preserved as-is — auditable, traceable."

---

### Act 7 — The Bigger Picture (1 minute, no clicks)

**Say:**

"What you've seen is the full intelligence cycle — automated:

1. **Collect** — Web crawling, RSS, Telegram, Reddit, with multilingual translation
2. **Analyse** — NLP clustering, entity extraction, semantic search
3. **Detect** — Deepfake scoring, object detection, EXIF forensics
4. **Alert** — Real-time signals when independent sources corroborate a narrative
5. **Report** — LLM-generated, source-grounded, auditable intelligence briefs
6. **Audit** — Every source change, every credibility score, every report — traceable

All running on one machine. No cloud dependency. Fully sovereign.

This is Anveshak."

---

## TIMING SUMMARY

| Act | Duration | Focus |
|-----|----------|-------|
| 1. Login | 30s | First impression, branding |
| 2. Topics & Content | 2m | Collection, translation, clustering, search |
| 3. Signals | 1.5m | Real-time alerting, triage workflow |
| 4. Sources | 1.5m | Credibility scoring, audit trail |
| 5. Vision | 2m | Deepfake, YOLO, EXIF, reverse search |
| 6. Reports | 2m | LLM generation, RAG, PDF, GIS |
| 7. Closing | 1m | Recap the cycle |
| **Total** | **~10 minutes** | |

---

## HARD QUESTIONS & ANSWERS

**Q: "Can this scale to 1000 sources?"**
A: Yes. Scraping is async via ARQ workers. Add more workers horizontally.
   PostgreSQL + pgvector handles millions of embeddings.

**Q: "What if Ollama is slow on CPU?"**
A: Default config runs on CPU. Drop in a GPU and change one env var
   (`OLLAMA_DEVICE=cuda`). No code changes. See hardware.md for the full
   upgrade matrix.

**Q: "How do you prevent LLM hallucinations in reports?"**
A: Every LLM output is parsed through a Pydantic schema. Claims must cite
   sources from the provided context. The anti-hallucination prompt enforces
   "if not in context, say not confirmed." The schema rejects any output that
   doesn't validate.

**Q: "What languages are supported?"**
A: NLLB-200 supports 200 languages. Currently configured for Hindi, Chinese,
   Arabic, Urdu → English. Add more with one config change.

**Q: "Can different agencies use this for different missions?"**
A: Absolutely. Topics are independent workspaces. Each can have its own sources,
   keywords, credibility thresholds, and scheduled reports. One deployment,
   multiple missions.

**Q: "What about classified networks / air-gapped deployment?"**
A: Anveshak has zero cloud dependency. Package the Docker images, copy to the
   air-gapped network, run `docker compose up`. Ollama models are bundled locally.

**Q: "How is this different from Palantir / Recorded Future?"**
A: Those are cloud SaaS platforms. Your data goes to their servers. Anveshak is
   sovereign — you own the hardware, the data, and the models. No vendor lock-in,
   no subscription, no data exfiltration risk.
