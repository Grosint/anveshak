# Source Discovery — Future Roadmap

## Current State

Anveshak has a backend endpoint (`GET /api/v1/topics/{topic_id}/discover-sources`) that
extracts outbound URLs from scraped content and suggests domains not yet registered as sources.
However, **no frontend UI exists** — the endpoint is unreachable by analysts.

---

## The 5-Level Discovery Architecture

```
Level 0 — Curated Catalog         "We already know these sources exist"
    │     (instant, no scraping)    400+ entries across 22 domains
    │                               Keyword match + effectiveness analytics
    │
    ▼
Level 1 — Snowball                 "Your sources are linking to these sites"
    │     (needs scraping history)  Outbound URL extraction + frequency ranking
    │
    ▼
Level 2 — Telegram Forwarding     "This message was forwarded from here"
    │     (needs Telegram adapter)  Forward chain mapping, origin discovery
    │
    ▼
Level 3 — Entity Search           "Other platforms discussing the same people/places"
    │     (needs NLP entities)      Cross-platform entity search
    │
    ▼
Level 4 — LLM Suggestions         "Based on this topic, you should also monitor..."
          (needs LLM pipeline)      Source type recommendations (not specific URLs)
```

Each level builds on the previous. Level 0 works from day zero (no scraping needed).
Levels 1-4 get better as more content flows through the pipeline.

---

## Level 0 — Curated Source Catalog (PLANNED — see .claude/plans/elegant-baking-torvalds.md)

> "We already know 400+ OSINT sources across 22 domains — suggest them instantly"

Pre-built knowledge base of known OSINT sources (Telegram channels, RSS feeds, web sources)
organized by domain tags (china, pakistan, narcotics, cyber, etc.). When an analyst creates
a topic, Anveshak immediately suggests relevant sources based on keyword matching.

**Key features:**
- 22 domain catalogs (~400 entries): China, Pakistan, India Defence, Naxalism, Myanmar,
  Maritime/IOR, Narcotics, Cyber/CTI, Middle East, NE India, Kashmir, Russia/Ukraine,
  Africa Sahel, Terrorism, Nuclear, Space, Disinfo, Arms Trade, Economic Intel,
  Border Security, Coastal Security, CBRN
- Rich metadata per source: reliability tier (S/A/B/C), bias indicator, risk level,
  subscriber count, activity frequency, language, category
- Source effectiveness analytics: weekly job traces signal→cluster→content→source,
  computes recommendation_rank (most_recommended/proven/curated/low_performer)
- Sources that actually produce signals float to the top of suggestions over time
- One-click approve flow: analyst clicks "Add" → source created + linked to topic
- UX: category-grouped collapsible cards with tier badges, analytics badges

**Implementation:** DB table `source_catalog` + `catalog_approvals`, JSON manifests
in `scripts/catalog/`, seed script, 2 API endpoints, frontend CatalogSuggestionsPanel.

**Status:** Plan complete. Data collection (Perplexity research for 22 domains) in progress.

### Source Effectiveness Analytics — Catalog Learns From Signals

The catalog isn't static — it gets smarter over time. Sources that actually produce
signal-worthy content float to the top of suggestions via a feedback loop:

```
Catalog suggests source → Analyst approves → Source produces content
→ Content enters clusters → Clusters fire signals
                                    │
                                    ▼
                      Weekly ARQ job: compute_source_effectiveness
                      Traces: signal → cluster → content_items → source
                                    │
                                    ▼
                      Updates source_catalog with computed scores
                                    │
                                    ▼
                      Next suggestion query ranks signal-contributors higher
                      Badge: "⭐ Most Recommended — contributed to 5 signals"
```

**What we measure per source** (from data already in the pipeline):

| Metric | Where it comes from | What it tells us |
|--------|-------------------|-----------------|
| Signal contributions | `content_items` → `narrative_clusters` → `signals` — trace which sources had items in signal-firing clusters | This source produces intelligence that matters |
| ISC contributions | How often this source is the 2nd/3rd independent platform in a cluster | This source corroborates narratives from other platforms |
| Relevance hit rate | % of items from this source that pass the relevance gate (Gate 11) | This source stays on-topic |
| Quality hit rate | % of items that pass quality gates (not marked low_quality) | This source produces clean content, not garbage |
| Cluster participation | % of items that end up in a cluster (not unassigned) | This source produces content that relates to narratives |

**How it flows into the catalog:**

```
source_catalog entry: "@ChinaMilitaryReview"
         │
         ▼
  Approved for topic "India-China LAC"
  → Creates source in sources table
  → Scraper starts collecting
         │
         ▼ (after 2 weeks of data)

  Analytics job runs (weekly cron):
    - This source contributed to 5 fired signals
    - 78% of items passed relevance gate
    - 45% of items ended up in clusters
    - ISC contribution: appeared in 3 multi-source clusters
         │
         ▼
  source_catalog.signal_effectiveness = 0.82
  source_catalog.recommendation_rank = "most_recommended"
         │
         ▼
  Next analyst creating a China topic sees:
    @ChinaMilitaryReview  [Telegram] [S tier] ⭐ Most Recommended
    "Contributed to 5 signals across 3 topics"
```

**Recommendation ranking tiers:**

| Level | Criteria | Badge in UI |
|-------|----------|-------------|
| Most Recommended | Approved in 2+ topics AND contributed to 3+ signals | ⭐ Most Recommended |
| Proven | Approved in 1+ topic AND items entered clusters | ✓ Proven |
| Curated | Never approved — pure catalog entry, no performance data | (no badge) |
| Low Performer | Approved but < 10% items pass relevance gate after 2 weeks | ⚠ Low relevance |

**Implementation:**
1. Weekly ARQ cron job `compute_source_effectiveness` in analyst-scheduler
2. Columns on `source_catalog`: `signal_contribution_count`, `relevance_hit_rate`,
   `cluster_participation_rate`, `recommendation_rank`, `topics_approved_count`
3. Suggestion API sorts by `recommendation_rank` first, then `reliability_tier`, then `credibility`
4. Frontend shows badge + "Contributed to N signals across M topics" text

---

## Part A — Frontend for Existing Discover Sources Endpoint

### What exists (backend)

- `SQL_OUTBOUND_LINKS` query extracts URLs from `clean_text` via regex
- Compares extracted domains against registered sources
- Returns: `suggested_domains`, `total_outbound_domains`, `already_registered`
- Location: `services/api/anveshak/api/routes/intelligence.py` (lines 156–200)

### What needs to be built (frontend)

1. **"Discover Sources" button** on the topic detail page
2. **Suggestions panel** showing:
   - Recommended domains (sorted by frequency of appearance)
   - How many times each domain was referenced in scraped content
   - One-click "Add as Source" button per suggestion
   - Bulk "Add Selected" for multiple sources at once
3. **Badge/counter** on the topic card: "N new sources found" to draw analyst attention
4. **Auto-link**: when a source is added via discovery, auto-link it to the current topic

### Backend improvements needed

- Add frequency count to `SQL_OUTBOUND_LINKS` (how many content items reference each domain)
- Add source type detection (is it RSS? news site? social profile?)
- Return top suggestions sorted by citation frequency, not alphabetically

---

## Part B — Four Levels of Automatic Source Discovery

### Level 1 — Snowball from Existing Content (Low effort, Medium value)

> "Sources your current sources are talking about"

- Anveshak already scrapes articles that **link to other websites**
- If multiple sources all link to the same domain, that domain is likely relevant
- Auto-recommend with a confidence score based on citation frequency

**Example:** Topic "arms smuggling western border". Three news articles all cite
rajasthanpatrika.com, which isn't registered. Anveshak recommends:
> "Recommended: rajasthanpatrika.com — cited by 3 of your existing sources"

**Implementation:**
- Enhance existing `/discover-sources` endpoint with frequency ranking
- Add ARQ background job to periodically extract and rank outbound domains
- Store suggestions in a `discovered_sources` table with topic_id, domain, citation_count
- Surface via frontend suggestions panel (Part A above)

---

### Level 2 — Telegram Forwarding Chain (Medium effort, Very high value)

> "Where did this message originally come from?"

Telegram messages carry forwarding metadata (`message.forward_from_channel`,
`message.fwd_from`). If Channel A forwards from Channel B, Anveshak can discover
Channel B automatically. **This data is not currently captured.**

**Example:** A monitored channel forwards 12 messages from an unknown channel
"weapons_market_21". Anveshak recommends:
> "New channel detected via forwarding: weapons_market_21 — 12 forwarded messages
> in the last week. Add to monitoring?"

**Implementation:**
- Extend Telegram adapter `RawItem` to capture `forward_from_channel` metadata
- Add `forwarded_from_channel_id` and `forwarded_from_channel_name` columns to content_items
- Create ARQ job: `discover_telegram_channels` — aggregates forwarding sources per topic
- Store in `discovered_sources` table with platform=telegram, discovery_method=forwarding
- Rank by forward frequency and recency
- Surface in frontend with "Discovered via forwarding" badge

**Why this is gold:** It maps the information supply chain — where narratives originate
before they spread to mainstream channels.

---

### Level 3 — Entity-Based Source Discovery (Medium-high effort, High value)

> "Other sources talking about the same people and places"

When Anveshak extracts entities (persons, locations, organisations) from a topic,
it can search for those entities across platforms it isn't yet monitoring.

**Example:** Topic mentions "Rashid K" and "Barmer". Anveshak searches Reddit,
Bluesky, and web for those terms and finds:
> "3 Reddit threads and 1 news blog discussing 'Rashid K + Barmer' — not
> currently monitored. Add these sources?"

**Implementation:**
- Extract top entities per topic from NLP pipeline (already done in analyst service)
- Create ARQ job: `discover_entity_sources` — searches each platform adapter for
  top entities that aren't in currently monitored sources
- Use platform search APIs: Reddit search, Bluesky search, web search via Crawl4AI
- Deduplicate against existing sources
- Score by entity overlap and content relevance
- Store in `discovered_sources` table with discovery_method=entity_search
- Respect rate limits and budget guards (especially X/Twitter)

**Constraint:** Entity search on social platforms may have rate limits. Use
per-adapter scheduling (see arq-jobs.md) to avoid hitting API caps.

---

### Level 4 — LLM-Recommended Sources (Low effort, Medium value)

> "Based on this topic, you should also monitor..."

Use the local LLM to analyze the topic description and existing content,
then suggest **types of sources** that would be valuable.

**Example:** Topic "Chinese infrastructure at India-Myanmar border". LLM suggests:
> "Consider monitoring: Myanmar-language Telegram channels, satellite imagery
> forums, construction tender websites for border states, ASEAN defence outlets"

**Implementation:**
- Create ARQ job: `suggest_source_types` — sends topic summary + existing source
  list to LLM with a structured prompt
- LLM returns structured suggestions (Pydantic-validated, per CLAUDE.md rule 9):
  ```python
  class SourceSuggestion(BaseModel):
      platform: str
      description: str
      search_terms: list[str]
      reasoning: str
      labels: Labels
  ```
- Surface as "AI Suggestions" tab in the discovery panel
- Analyst acts on suggestions manually (Anveshak doesn't auto-add)
- All LLM calls via ARQ (CLAUDE.md rule 5), localhost Ollama only (rule 10)

**Note:** This provides guidance, not specific URLs. The analyst uses these
suggestions to find and register actual sources.

---

## Implementation Priority

| Level | Effort | Value | Priority | Depends on | Status |
|-------|--------|-------|----------|------------|--------|
| Level 0 — Curated Catalog | Medium | Very high | **In progress** | Nothing (works from day zero) | Plan complete, data collection in progress |
| Frontend (Part A) | Low | High | **Do with Level 0** | Nothing | Not started |
| Level 1 — Snowball | Low | Medium | **Do after Level 0** | Part A + scraping history | Not started |
| Level 2 — Telegram forwarding | Medium | Very high | **Do second** | Telegram adapter changes | Not started |
| Level 3 — Entity search | Medium-high | High | Phase 2 | NLP entity extraction | Not started |
| Level 4 — LLM suggestions | Low | Medium | Nice-to-have | ARQ + LLM pipeline | Not started |

## Analyst Experience (End State)

**Today:** Analyst manually finds and adds every source — limited by their own
knowledge and time.

**After (Level 0):** Analyst creates topic "China PLA" → Anveshak instantly suggests
40 Telegram channels, RSS feeds, and web sources, ranked by reliability tier and
signal effectiveness. Analyst clicks "Add" on the ones they want.

**After (Level 0+1):** Same as above, plus "3 of your existing sources keep linking
to rajasthanpatrika.com — add it?"

**After (Level 0+1+2):** Same as above, plus "Channel @weapons_market_21 forwarded
12 messages to your monitored channels this week — add it?"

**After (all levels):** Anveshak discovers, suggests, and ranks sources automatically.
The analyst just reviews and approves. Source collection shifts from a **manual
research task** to a **review-and-approve task**.

---

## Related Plans

- **Source Catalog (Level 0):** `.claude/plans/elegant-baking-torvalds.md`
- **Pipeline Observability:** `docs/future_grafana.md`
- **Tuning History:** `docs/tuning_history.md`
