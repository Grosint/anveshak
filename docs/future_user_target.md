# Anveshak — Target-Centric Social Monitoring (Future Feature)

**Status:** Planning (not yet implemented)
**Date:** 2026-04-17
**Scope:** Track specific persons of interest (POIs) across social platforms, detect behavioral anomalies and cross-target coordination.

---

## Product Vision

### The Paradigm Shift

Current Anveshak answers: "What is the world saying about Topic X?" (topic-centric)
Target monitoring answers: "What is Person Y doing across the open internet?" (person-centric)

Both are essential. Together they create a complete OSINT picture.

### What an IAF Analyst Gets

#### 1. Cross-Platform Activity Fusion

A target posts on Telegram, comments on X, shares a photo on Instagram. Individually — noise. Fused together on a timeline:

- **Coordination detection** — same narrative posted across platforms within minutes (information operation signature)
- **Network mapping** — who they interact with consistently across platforms
- **Content attribution** — Telegram forwards traced back to the original poster
- **Operational pattern** — posting schedule, timezone inference, activity cadence

#### 2. Behavioral Baseline + Anomaly Detection

After 2-3 weeks of collection, Anveshak builds a behavioral profile per target:

| Baseline Metric | What a Change Means |
|---|---|
| Posts per day (by platform) | Activity spike = something brewing |
| Topics discussed (embedding clusters) | Sudden topic shift = new tasking/interest |
| Active hours | Schedule change = location change or operational shift |
| Language/register | Formal to informal or language switch = different audience |
| Platform preference | New platform adoption = new operational need |
| Interaction network | New contacts = network expansion |
| Sentiment trend | Escalating negativity = radicalization indicator |

**Example signal:** "Target FOXTROT-3 posted 14x on Telegram in last 6 hours (baseline: 2/day). Topic shifted from cricket to Indian military exercises. 3 posts forwarded from known disinformation channel."

#### 3. Multi-Target Correlation

Detects coordinated inauthentic behavior across multiple targets:

- Synchronized posting across targets (same content within minutes)
- Shared amplification networks (same accounts retweeting multiple targets)
- Common group memberships (3 targets all in the same Telegram group)
- Information flow directionality (Target A originates, Target B amplifies, Target C translates)

#### 4. IAF-Specific Use Cases

| Use Case | How It Works |
|---|---|
| **Counter-intelligence** | Track known adversary IO operatives; detect when narratives shift before operations |
| **Info warfare early warning** | Detect coordinated anti-IAF narrative seeding across platforms |
| **Force protection** | Monitor threats against IAF installations/personnel mentioned by POIs |
| **Strategic assessment** | Track adversary military commentators for doctrine/capability narrative shifts |
| **HUMINT correlation** | Cross-reference open-source POI activity with classified reporting (analyst does this manually) |

---

## Platform Assessment

### Tier 1 — Full Automation

| Platform | Library | Collection Depth | Feasibility |
|---|---|---|---|
| **Telegram** | Telethon | Excellent — full access to group messages, forward chains, content attribution | High |
| **X/Twitter** | tweepy | Good — `get_users_tweets`, `get_users_mentions`. Budget-limited (pay-per-use) | Medium-High |

### Tier 2 — Best-Effort

| Platform | Library | Collection Depth | Feasibility |
|---|---|---|---|
| **Instagram** | instagrapi (private API) | Good capability but high ban risk. Requires dedicated collection accounts with rotation | Medium |
| **Facebook** | Playwright (browser automation) + manual input | Limited — no usable API for personal profiles. Public pages only via scraping | Low-Medium |

### Instagram via instagrapi — Detail

- GitHub: https://github.com/subzeroid/instagrapi (~6,100 stars, actively maintained)
- Uses Instagram's **private mobile API** (reverse-engineered, not official)
- **Capabilities:** `user_medias()`, `media_comments()`, `user_followers/following()`, `user_stories()`, `user_info()`
- **Risks:** ToS violation, account bans (reported after scraping just 10 posts), requires real aged Instagram account
- **Mitigations:** Account rotation, session persistence, aggressive rate limiting (`delay_range=[3,8]`), stable residential proxies, graceful degradation
- **Design principle:** Treat collection accounts as expendable. System degrades gracefully when Instagram blocks us.

### Facebook — The Hard Truth

- **Graph API:** Locked down post-Cambridge Analytica. Cannot read arbitrary user profiles.
- **CrowdTangle:** Shut down August 2024.
- **Content Library API:** Academic-only, no defense access.
- **facebook-scraper:** Unreliable, doesn't work on personal profiles.
- **Realistic approach:** Playwright-based best-effort for public profiles + **manual activity input** by analysts who observe Facebook directly.

---

## Signal Types for Targets

| Signal Type | Trigger | Severity |
|---|---|---|
| `activity_spike` | Posts in 6h window > 3x daily baseline | HIGH |
| `topic_shift` | Embedding similarity to baseline < 0.5 | MEDIUM |
| `schedule_anomaly` | Activity outside normal active hours | LOW |
| `cross_platform_burst` | Same content hash/semantic match across 2+ platforms within 1h | HIGH |
| `network_expansion` | New interaction with previously unseen account | LOW |
| `narrative_convergence` | Target's content clusters with known disinformation topic | HIGH |
| `coordination_detected` | 2+ targets post semantically similar content within 30min | CRITICAL |

---

## Behavioral Baseline — How It Works

### Phase 1: Collection (Days 1-14)

Every activity record captures:
- timestamp, platform, activity_type (post/comment/share/forward/like)
- content (text, with translation if non-English)
- embedding (384-dim vector of the content's meaning)
- media (images/videos attached)
- interaction_targets (who they replied to, who they forwarded from)

### Phase 2: Baseline Computation (After 14 days)

The system computes a BehavioralProfile — a statistical fingerprint of "normal":

| Metric | Computation | Example |
|---|---|---|
| **Activity rate** | Mean + stddev of posts per day, per platform | "3.2 +/- 1.1 posts/day on Telegram" |
| **Active hours** | Histogram of posting times (UTC) | "Active 06:00-09:00 and 18:00-22:00 IST" |
| **Topic centroid** | Mean embedding vector of all content | 384-dim vector of "what they normally talk about" |
| **Topic spread** | Stddev of cosine distances from centroid | "Usually within 0.3 cosine distance of centroid" |
| **Platform distribution** | % of activity per platform | "60% Telegram, 30% X, 10% Instagram" |
| **Sentiment baseline** | Mean sentiment score over time | "Neutral-to-slightly-negative (0.42)" |
| **Language distribution** | % of content per language | "85% Urdu, 10% English, 5% Arabic" |

Profile recomputes weekly on a rolling 30-day window.

### Phase 3: Anomaly Detection (Continuous)

Every new activity checked against profile using z-score thresholds:

```
Example: Target posts 15 times on Telegram today.
Baseline: 3.2 +/- 1.1 posts/day
Z-score: (15 - 3.2) / 1.1 = 10.7 -> beyond threshold of 3.0
-> Signal: ACTIVITY_SPIKE (severity: HIGH)
```

For topic shift detection (embedding-based):
```
Example: Target normally discusses cricket and local politics.
Today's posts are about Indian military base locations.
Cosine similarity to topic centroid: 0.18 (baseline spread: 0.3)
-> Signal: TOPIC_SHIFT (severity: HIGH)
```

**Why 14 days minimum:** Weekday/weekend patterns need 2+ full weeks. One-off events skew shorter baselines. Stddev unreliable with <30 observations. Analyst can override to 7 days for urgent targets (accepting higher false-positive rate).

---

## Multi-Target Correlation — How It Works

### A. Synchronized Posting (Coordination Fingerprint)

```
Timeline:
  14:02:31  Target ALPHA posts on Telegram: "IAF Rafale deployment to Hashimara is a provocation"
  14:03:12  Target BRAVO posts on X: "India sending Rafales to NE border — aggressive posturing"
  14:04:45  Target CHARLIE posts on Facebook: "Rafale jets moved to Hashimara — escalation!"

Detection:
  - 3 targets posted within 2.5 minutes
  - Semantic similarity between posts: 0.87 (high)
  - Platforms are different (cross-platform coordination)
  -> Signal: COORDINATION_DETECTED (severity: CRITICAL)
  -> Analyst inference: likely receiving shared talking points from a handler
```

Algorithm: for every new activity, compute embedding. Compare against all other target activities within configurable time window (default: 30 minutes). If semantic similarity > 0.75 AND 2+ distinct targets AND 2+ distinct platforms -> fire coordination signal.

### B. Shared Amplification Network

```
Over 30-day window:
  Target ALPHA's Telegram posts forwarded by accounts X, Y, Z
  Target BRAVO's Telegram posts forwarded by accounts X, Y, W
  Shared amplifiers: X, Y (Jaccard similarity of amplifier sets > 0.3)
  -> Signal: SHARED_NETWORK (severity: MEDIUM)
```

### C. Information Flow Directionality

```
Pattern over 14 days:
  Target ALPHA posts original content -> 2-4 hours later -> Target BRAVO posts adapted version
  This happens 8 times. Reverse direction: 0 times.
  -> Signal: INFORMATION_FLOW (severity: MEDIUM)
  -> Analyst inference: ALPHA is the originator, BRAVO is the amplifier
```

### D. Behavioral Synchronization

```
Target ALPHA, BRAVO, CHARLIE all spike on same days, go silent on same days.
Activity pattern correlation coefficient: 0.82
-> Signal: BEHAVIORAL_SYNC (severity: HIGH)
-> Analyst inference: likely coordinated by same handler
```

### Cross-Target Correlation Matrix

Maintained daily, dimensions: temporal correlation, semantic similarity, network overlap, activity pattern correlation.

```
           ALPHA   BRAVO   CHARLIE   DELTA
ALPHA        -      0.82    0.71     0.12
BRAVO       0.82     -      0.68     0.15
CHARLIE     0.71    0.68     -       0.09
DELTA       0.12    0.15    0.09      -
```

When any cell crosses threshold (default 0.6), the pair is flagged. Clusters of correlated targets presented as coordination groups in the workbench.

Scale: 50 targets = 1,225 pairs (~2s daily on CPU). 200 targets = 19,900 pairs (still manageable on CPU, GPU benefits at 500+).

---

## Architecture Plan

### Design Principles

- **Not a new service** — extends existing social (collection) and analyst (analysis) services
- **Reuses existing ML pipeline** — sentence-transformers, spaCy, NLLB translation. No new models.
- **Analyst defines linkage** — the analyst creates a Target with known platform handles. Anveshak does NOT attempt cross-platform identity resolution (that is Drishti's job).
- **Configurable scale** — `TARGET_MAX_COUNT` env var, default 50, increase with hardware.

### New Database Tables

```sql
-- Person of interest
targets (
    id              UUID PRIMARY KEY,
    codename        TEXT NOT NULL,         -- analyst-assigned, e.g. "FOXTROT-3"
    notes           TEXT,
    status          TEXT DEFAULT 'active', -- active/paused/archived
    baseline_ready  BOOLEAN DEFAULT FALSE,
    baseline_min_days INTEGER DEFAULT 14,
    labels          JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Platform handles for a target
target_platform_identities (
    id                  UUID PRIMARY KEY,
    target_id           UUID REFERENCES targets(id),
    platform            TEXT NOT NULL,     -- telegram/x/instagram/facebook
    platform_user_id    TEXT NOT NULL,
    platform_username   TEXT,              -- for display
    collection_enabled  BOOLEAN DEFAULT TRUE,
    last_collected_at   TIMESTAMPTZ,
    labels              JSONB NOT NULL,
    UNIQUE(platform, platform_user_id)
);

-- Individual activities collected or manually entered
target_activities (
    id                      UUID PRIMARY KEY,
    target_id               UUID REFERENCES targets(id),
    platform_identity_id    UUID REFERENCES target_platform_identities(id),
    activity_type           TEXT NOT NULL,  -- post/comment/share/forward/like/story/manual
    raw_text                TEXT,
    clean_text              TEXT,
    content_hash            TEXT NOT NULL,  -- SHA-256 dedup
    url                     TEXT,
    embedding               vector(384),
    language                TEXT,
    translated_text         TEXT,
    captured_at             TIMESTAMPTZ NOT NULL,
    metadata                JSONB,         -- platform-specific: reply_to, forward_from, media_urls
    labels                  JSONB NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(content_hash)
);

-- Computed behavioral fingerprint per target
behavioral_profiles (
    id                          UUID PRIMARY KEY,
    target_id                   UUID REFERENCES targets(id) UNIQUE,
    computed_at                 TIMESTAMPTZ NOT NULL,
    window_start                TIMESTAMPTZ NOT NULL,
    window_end                  TIMESTAMPTZ NOT NULL,
    activity_rate_mean          JSONB,      -- per-platform
    activity_rate_stddev        JSONB,
    active_hours_histogram      JSONB,      -- 24 bins, per-platform
    topic_centroid              vector(384),
    topic_spread                FLOAT,
    platform_distribution       JSONB,
    sentiment_baseline          FLOAT,
    language_distribution       JSONB,
    interaction_density         JSONB,
    labels                      JSONB NOT NULL
);

-- Target-specific signals
target_signals (
    id              UUID PRIMARY KEY,
    target_id       UUID REFERENCES targets(id),
    signal_type     TEXT NOT NULL,
    severity        TEXT NOT NULL,          -- LOW/MEDIUM/HIGH/CRITICAL
    detail          JSONB,                  -- z-score, evidence activity IDs
    status          TEXT DEFAULT 'new',     -- new/acknowledged/dismissed
    labels          JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Cross-target correlation (recomputed daily)
target_correlation_matrix (
    target_a_id     UUID REFERENCES targets(id),
    target_b_id     UUID REFERENCES targets(id),
    temporal_score  FLOAT,
    semantic_score  FLOAT,
    network_score   FLOAT,
    overall_score   FLOAT,
    computed_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (target_a_id, target_b_id)
);
```

### New Configuration (settings.py, all env-var driven)

```
TARGET_MAX_COUNT=50                             # Scale with hardware
TARGET_POLL_INTERVAL_S=900                      # 15 min default
TARGET_X_POLLS_PER_DAY=4                        # Budget-aware for X/Twitter
TARGET_BASELINE_MIN_DAYS=14                     # Override per-target
TARGET_ANOMALY_ZSCORE_THRESHOLD=3.0             # Sensitivity
TARGET_COORDINATION_WINDOW_MINUTES=30           # Time window for sync detection
TARGET_COORDINATION_SIMILARITY_THRESHOLD=0.75   # Semantic match threshold
TARGET_CORRELATION_THRESHOLD=0.6                # Matrix alert threshold
TARGET_INSTAGRAM_DELAY_MIN=3                    # instagrapi rate limit (seconds)
TARGET_INSTAGRAM_DELAY_MAX=8
TARGET_INSTAGRAM_ACCOUNTS_POOL=1                # Number of collection accounts
TARGET_FACEBOOK_ENABLED=false                   # Best-effort, off by default
```

### New ARQ Jobs

```
Social service (collection):
  poll_target_activities(target_id)        # Polls all platforms for one target

Analyst service (analysis):
  analyse_target_activity(activity_id)     # NLP + embedding for one activity
  compute_behavioral_profile(target_id)    # Daily baseline recomputation
  check_target_anomalies(target_id)        # Per-activity anomaly detection
  compute_correlation_matrix()             # Daily cross-target correlation
```

### New Analyst Service Loops

```
target_baseline_loop (runs daily)
  -> For each active target with >= baseline_min_days of data:
     -> Compute/update behavioral_profile (rolling 30-day window)

target_anomaly_loop (runs every 5 min)
  -> For each new target_activity since last check:
     -> Compare against behavioral_profile
     -> Compute z-scores for activity rate, topic distance, schedule
     -> Insert target_signal if threshold breached

target_correlation_loop (runs daily)
  -> Recompute cross-target correlation matrix
  -> Fire coordination signals for pairs above threshold
```

### Implementation Phases

| Phase | Deliverable | Dependencies |
|---|---|---|
| **0: Data Model** | DB migration + SDK Pydantic models (Target, TargetActivity, BehavioralProfile, TargetSignal) | None |
| **1: Telegram + X Collection** | Target-centric polling adapters, `poll_target_activities` ARQ job | Phase 0 |
| **2: Instagram + Facebook** | instagrapi adapter (with account rotation), Playwright Facebook adapter, manual activity input API | Phase 0 |
| **3: Behavioral Analysis** | Baseline computation, anomaly detection, target signal engine | Phase 0 + 1 |
| **4: Multi-Target Correlation** | Correlation matrix, coordination detection, information flow analysis | Phase 3 |
| **5: Frontend** | Target CRUD, activity timeline, behavioral dashboard, correlation graph | Phase 0 + 3 |

### Hardware Impact

| Component | CPU Impact | GPU Upgrade Path |
|---|---|---|
| 50 targets x embedding per activity | ~14ms x activities/day — negligible | No change needed |
| Behavioral profile computation | Daily batch, <10s for 50 targets | Not needed |
| Correlation matrix (1,225 pairs) | ~2s daily | Benefits from GPU at 500+ targets |
| instagrapi sessions | Network-bound, not compute-bound | N/A |
| Scale to 200 targets | Increase `TARGET_MAX_COUNT`, add RAM | Correlation benefits from GPU at 500+ |

No new ML models required. Reuses existing sentence-transformers, spaCy, NLLB translation pipeline.

---

## What This Is NOT (Boundary with Drishti)

- Does NOT attempt cross-platform identity resolution ("is @handle_x the same as @tg_user?") — the analyst provides the linkage
- Does NOT build a social graph database — tracks activities, not relationships as first-class entities
- Does NOT do facial recognition across platforms — that is vision service + Drishti territory

The analyst defines: "This is Target FOXTROT-3. Here are their platform handles." Anveshak monitors and analyses. Clean boundary.
