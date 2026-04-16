# Anveshak: Airport Analyst Walkthrough

You're an IAF wing intelligence officer. Anveshak is your workbench. Here's a complete operational session that exercises every feature.

---

## Pre-Session: System Check

Before you start, confirm all services are green:

```bash
make demo-check
# All 8 steps should PASS
```

Then seed the demo database (one-time):
```bash
make seed-demo
```

---

## Step 1 — Login & Orient

**Navigate to:** `http://localhost:3000/login`

- Credentials: `demo@anveshak.local` / `AnveshakDemo2024!`
- After login you get a JWT token — the frontend handles this automatically
- You land on the **Topics Dashboard** (`/topics`)

You'll see 3 pre-seeded topics from Operation Kargil Watch:

1. *China-Pakistan Military Cooperation* (signal threshold: 3)
2. *UAV Activity Near Northern Borders* (threshold: 2)
3. *Disinformation: IAF Operations* (threshold: 2)

---

## Step 2 — Create Your Own Topic (M2/M3)

As an airport analyst, create a topic relevant to you:

1. Click **"New Topic"**
2. Fill in:
   - **Name:** `Airport Security Incidents — Northern Sector`
   - **Signal threshold:** `2` ← fire alert when 2 independent platforms report same cluster
   - **Scheduled report:** Weekly digest, every Monday 06:00
3. Save — Anveshak now monitors this topic

> This activates the backfill: pgvector searches your existing corpus for already-ingested content that matches this topic.

---

## Step 3 — Add Sources & Configure Collection (M1/M3)

Navigate to **Source Manager** (`/sources`):

### Add Web Sources
1. Click **"Add Source"**
2. Add sources:
   - `https://theprint.in` — credibility: 75
   - `https://eurasiantimes.com` — credibility: 68
   - A Telegram channel handle for border area monitoring
3. Each source gets an initial credibility score (0–100)

### Platform Sources
For social platforms, these are configured via environment variables in `.env`:
```
TELEGRAM_SESSION_STRING=...     # Telethon session
REDDIT_CLIENT_ID=...            # PRAW credentials
BLUESKY_HANDLE=...              # atproto
X_BEARER_TOKEN=...              # Twitter, pay-per-use
X_MONTHLY_READ_CAP=200          # $200/month budget cap
```

Once set, the social service polls these platforms automatically for your active topics.

---

## Step 4 — Monitor the Content Feed (M2)

Navigate to **Content Feed** for your topic (`/topics/:id/content`):

### What you'll see
- Infinite-scroll cards of ingested articles/posts
- Platform badge on each card: `web`, `telegram`, `reddit`, `x`
- NLP-extracted entities (persons, organizations, locations) highlighted

### Use Semantic Search
In the search bar, type:
> `drone activity near airbase`

Anveshak does a **pgvector cosine similarity search** — finds semantically related content even if those exact words aren't present. Results ranked by relevance.

### View Narrative Clusters
Switch to **Cluster View**:
- Each cluster = group of content items that say similar things from different sources
- A cluster labelled `"PLA drone exercises near LAC"` with `independent_source_count: 3` → **this is your signal trigger**
- Click a cluster to see all contributing content items + source platforms

---

## Step 5 — Signals Inbox (Signals Engine)

Navigate to **Signals Inbox** (`/signals`):

The moment a cluster's `independent_source_count` hits your topic's threshold, a **real-time WebSocket push** fires. You'll see:

```
HIGH  |  UAV Activity Near Northern Borders
      |  Cluster: "PLA drone exercises near LAC"
      |  3 independent sources reported this
      |  [Acknowledge]  [Dismiss]
```

### Workflow
1. **New tab** — unread signals with red badge count
2. Click **Acknowledge** — moves to Acknowledged tab, logs the time
3. After investigation: **Dismiss** — closes the loop
4. If you reconnect after being offline: missed signals replay automatically (using `since` param)

---

## Step 6 — Image/Video Analysis (M4)

Navigate to **Image Analysis** (`/images`):

Suppose you've received an image — alleged satellite photo of an airbase, or a social media video frame. Upload it:

### Tab 1: Deepfake Score
- Animated meter: `0 ——————●—— 100`
- `deepfake_score: 0.73` — you decide the threshold, not the system
- If face present: Facetorch model
- If scene/video frame: EfficientNet-B0 model
- `synthetic_probability: 0.81` — probability it's AI-generated

### Tab 2: YOLO Object Detection
- Bounding boxes drawn on the image canvas
- Labels: `helicopter (0.94)`, `military vehicle (0.87)`, `runway (0.92)`
- 80 COCO classes — detects weapons, aircraft, persons, vehicles

### Tab 3: EXIF Metadata
| Field | Value |
|-------|-------|
| GPS | 32.1234°N, 77.5678°E |
| Timestamp | 2026-04-12 04:33:21 UTC |
| Camera | Samsung SM-G998B |
| Software | **Adobe Firefly 2.0** ← AI generation flag |

The **AI software tag** is automatically flagged as an anomaly.

### Tab 4: Reverse Image Search (pHash)
Enter a pHash or upload a reference image → finds **near-duplicate images** across your entire corpus (Hamming distance ≤ 8). Useful for detecting coordinated disinformation with slightly-modified images.

---

## Step 7 — Review Source Credibility (M1)

Back in **Source Manager** (`/sources`):

Suppose your Telegram source has been amplifying the deepfake image you just caught:

1. Click the source → view **Credibility Audit Log**
   - Full immutable history: who changed the score, when, why
2. Click **"Update Credibility"**
   - Set score from 68 → 35 with reason: `"Amplified confirmed deepfake content"`
   - This is **audit-logged** automatically
3. The auto-feedback loop also kicks in: sources that amplify confirmed deepfakes are auto-downgraded by the analyst service

> Any reports that previously included this source now get a **retroactive warning** — but the reports themselves are NOT modified (immutability rule).

---

## Step 8 — Generate an Intelligence Report (M5)

Navigate to **Report Builder** (`/reports/:topicId`):

### Create a Report
1. Select topic: `UAV Activity Near Northern Borders`
2. Report type: **Intelligence Brief** (1–3 page executive summary)
3. Time window: `Last 72 hours`
4. Credibility filter: `min 50` ← excludes low-credibility sources
5. Click **Generate** → HTTP 202 returned immediately, job enqueued

While it generates (3–5 min on CPU, Ollama `mistral:7b` running locally):

### Tab 1: Report (when complete)
- Structured markdown report with:
  - **Key entities** extracted (persons, organizations, locations)
  - **Timeline** of events
  - **Threat assessment** grounded in ingested content (RAG)
  - **Confidence badge** on each claim
- Source snapshot captured at generation time (credibility scores frozen)

### Tab 2: GIS Map
- MapLibre GL renders a map
- Pins for every geotagged entity (EXIF GPS + NER-extracted locations)
- Click a pin → linked content items

### Tab 3: History
- All previous reports for this topic
- Click any past report — it's **immutable**, exactly as generated
- If a source was later downgraded: yellow warning banner `"Source X credibility dropped post-generation"`

### Export to PDF
Click **Export PDF** → WeasyPrint generates a court-ready PDF (~500ms).

---

## Step 9 — Schedule Automated Reports

When creating or editing a topic, set:
- **Scheduled report type:** `weekly_digest`
- **Cron schedule:** `0 6 * * 1` (every Monday 06:00)

Every Monday morning, Anveshak auto-generates a 7-day digest for your topic and pushes a signal to your inbox.

---

## Complete Feature Coverage Map

| Feature | Where Used | Step |
|---------|-----------|------|
| Login/JWT auth | `/login` | 1 |
| Topic creation + backfill | `/topics` | 2 |
| Source credibility scoring | `/sources` | 3, 7 |
| Web scraping (Crawl4AI) | Background | 4 |
| Social collection (Telegram/Reddit/Bluesky/X) | Background | 3, 4 |
| Multilingual NLP + NER | Content cards | 4 |
| Semantic search (pgvector) | Content Feed | 4 |
| Narrative clustering (HDBSCAN) | Cluster view | 4 |
| Content deduplication (SHA-256) | All ingestion | 4 |
| Real-time signals (WebSocket) | `/signals` | 5 |
| Signal acknowledge/dismiss flow | `/signals` | 5 |
| YOLO object detection | `/images` | 6 |
| Deepfake scoring (float, analyst-threshold) | `/images` | 6 |
| CLIP image classification | `/images` | 6 |
| EXIF + AI software anomaly detection | `/images` | 6 |
| pHash reverse image lookup | `/images` | 6 |
| Credibility update + audit log | `/sources` | 7 |
| Retroactive report warnings | `/sources` | 7 |
| Intelligence brief (RAG + LLM) | `/reports` | 8 |
| GeoJSON mapping (MapLibre) | `/reports` → GIS tab | 8 |
| Immutable report history | `/reports` → History tab | 8 |
| PDF export | `/reports` | 8 |
| Scheduled reports | Topic settings | 9 |

---

## Key Rules to Remember as an Analyst

1. **Deepfake scores are probabilities** — `0.73` means you decide, the system doesn't
2. **Reports are immutable** — regenerate for updated analysis, don't edit
3. **Signals need acknowledgement** — the inbox is your primary action queue
4. **X/Twitter has a budget cap** — `$200/month` by default, check before enabling
5. **All LLM inference is local** — no intelligence data leaves your machine
