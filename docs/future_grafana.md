# Pipeline Funnel Grafana Dashboard — Implementation Plan

## Problem

Every issue discovered during the 2026-05-26 debugging session required SSH + manual SQL + pipeline_health.py:
- 53% content rejected by quality gates → needed `SELECT content_quality, COUNT(*) ...`
- 208 items stuck without embeddings → needed `WHERE embedding IS NULL` query
- 49-95% clustering unassigned → needed pipeline_health.py
- Andaman Sea zero content → needed log grep
- Broken NDTV RSS → needed source health query

In production, operators need real-time Grafana visibility without CLI access.

---

## Dashboard Design: "Pipeline Funnel"

A single dashboard showing the entire content journey from scrape to signal, with clickable drill-down into each stage.

### Main View — 5 Rows

```
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE FUNNEL — Content Journey           [Topic: All ▼]    │
│                                                                 │
│  Row 1: INGESTION                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Scraped/24h  │ │ By Platform  │ │ Source Health │           │
│  │    ████ 243  │ │ RSS ████ 180 │ │ 🟢 23 healthy│           │
│  │              │ │ Web ███  40  │ │ 🟡  3 degradd│           │
│  │              │ │ TG  ██  23   │ │ 🔴  2 down   │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
│  Row 2: QUALITY FUNNEL (clickable bars)                         │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Scraped ██████████████████████████████  243         │       │
│  │ Gate 1-4 pass ████████████████████████  231 (95%)  │       │
│  │ Gate 5-8 pass ██████████████████████    218 (90%)  │       │
│  │ Embedded      █████████████████████     215 (88%)  │       │
│  │ Relevant      ████████████████          178 (73%)  │       │
│  │ Clustered     ██████████                 98 (40%)  │       │
│  │ In Signals    ████                       32 (13%)  │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  Row 3: PER-TOPIC TABLE                                         │
│  ┌──────────────────────────────────────────────────────┐      │
│  │ Topic           │Scraped│Quality│Embedded│Clustered│Signals│
│  │ Disinformation  │  65   │  64   │   63   │  32     │   8  ││
│  │ Pakistan LoC    │  36   │  36   │   34   │  12     │   4  ││
│  │ IOR Maritime    │  61   │  60   │   60   │  13     │   0  ││
│  │ LAC             │  21   │  21   │   21   │   1     │   1  ││
│  │ Andaman Sea     │   0   │   0   │    0   │   0     │   0  ││
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  Row 4: CLUSTERING HEALTH                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Assignment %  │ │ Clusters/24h │ │ Relevance    │           │
│  │ per topic     │ │ created      │ │ score distrib│           │
│  │ Disinfo ██ 49%│ │     ████ 12  │ │ [histogram]  │           │
│  │ PakLoC ███ 67%│ │              │ │              │           │
│  │ IOR    █  23% │ │              │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
│  Row 5: SIGNALS & OPERATIONS                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Signals/24h  │ │ Orphans swept│ │ URL dedup     │           │
│  │   ████ 13    │ │    ██  5     │ │ savings       │           │
│  │ HIGH ██  4   │ │              │ │ 85% skipped   │           │
│  │ MED  ███ 9   │ │              │ │              │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Drill-Down Dashboards (linked from clickable bars)

Each bar in the funnel is a Grafana panel with a **data link**. Clicking opens a drill-down dashboard with the relevant `$topic` variable pre-set.

### Drill-Down 1: Ingestion (click "Scraped")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Per-source breakdown | `scraper_items_fetched_total` by source | Which sources are producing, which are silent |
| Platform split | `scraper_items_fetched_total` by `source_platform` | RSS vs Web vs Telegram vs Social |
| URL dedup savings | `scraper_url_seen_skip_total` / total fetches | How many fetches saved by Redis tracking |
| Links discovered | `scraper_links_discovered_total` histogram | Article links found per web source page |
| Source health table | Loki query on health check logs | healthy/degraded/down with error messages |
| Recent errors | Loki: `scraper.fetch_failed` OR `scraper.source_timeout` | Last 10 scraper errors filtered by topic |

### Drill-Down 2: Scraper Quality Gates 1-4 (click "Gate 1-4")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Gate 1 — Too Short | `scraper_content_quality_total{gate="too_short"}` | Count + histogram of clean_text lengths below 100 |
| Gate 2 — Paywall | `scraper_content_quality_total{gate="paywall"}` | Count + Loki showing top paywall URLs |
| Gate 3 — Nav Icon | `scraper_content_quality_total{gate="nav_icon"}` | Count + Loki showing top nav-icon URLs |
| Gate 4 — Ratio | `scraper_content_quality_total{gate="ratio"}` | Count + histogram of clean/raw ratios with 0.08 threshold line |
| Gate 4 — Bypass | `scraper_content_quality_total{gate="bypass"}` | Count of items that bypassed ratio via 500-char rule |
| Good vs Low Quality | `scraper_content_quality_total` by `quality` | Pie chart over time |
| Recent rejections | Loki: `content_quality=low_quality` entries | Last 10 with URL + gate reason |

### Drill-Down 3: Analyst Quality Gates 5-8 (click "Gate 5-8")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Gate 5 — Too Short | `analyst_content_skipped_quality_total{gate="too_short"}` | Count |
| Gate 6 — Few Words | `analyst_content_skipped_quality_total{gate="few_words"}` | Count |
| Gate 7 — Unique Ratio | `analyst_content_skipped_quality_total{gate="unique_ratio"}` | Count + ratio histogram |
| Gate 8 — Punctuation | `analyst_content_skipped_quality_total{gate="punctuation"}` | Count + ratio histogram |
| Passed vs Skipped | Total passed / total attempted | Percentage over time |
| Recent skips | Loki: `analyst.content_skipped_quality` | Last 10 with content_item_id + text_len |

### Drill-Down 4: Embedding (click "Embedded")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Completion rate | `analyst_embedding_completed_total` / total attempted | Percentage over time |
| NLP duration | `analyst_nlp_duration_seconds` histogram | How long embedding takes per item |
| Orphan count | `analyst_clustering_items{status="orphan"}` or SQL-backed gauge | Items with NULL embedding older than 1h |
| Orphan sweep | `analyst_orphan_sweep_total` | Items re-enqueued per cycle |
| Failed NLP jobs | `analyst_nlp_jobs_total{status="failed"}` | NLP pipeline failures |
| Recent errors | Loki: NLP error entries | Translation failures, model load errors |

### Drill-Down 5: Relevance (click "Relevant")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Score distribution | `analyst_topic_relevance_score` histogram | Shows where articles land (0.0-1.0) — already exists! |
| Per-topic threshold | `analyst_topic_relevance_threshold` gauge | Auto-calibrated thresholds — already exists! |
| Above/below threshold | Computed from histogram + threshold | Items passing vs filtered per topic |
| Threshold history | `analyst_topic_relevance_threshold` over 7d | How thresholds drift as content accumulates |
| Topic selector | Grafana template variable | Filter all panels to one topic |

### Drill-Down 6: Clustering (click "Clustered")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Assignment rate | `analyst_clustering_items{status="assigned"}` / total per topic | Per-topic bar chart — the 49-95% unassigned would be immediately visible |
| Clusters created | `analyst_clusters_created_total` per topic | New clusters per cycle |
| Edge count | `analyst_clustering_edges` per topic | Leiden graph density — sparse = too-high threshold |
| Near-dupes detected | Counter from dedup module | Paraphrased content pairs |
| Stale labels | Gauge: clusters where label_item_hash differs | Clusters needing Ollama re-label |
| Incremental vs full | Counter: assigned-to-existing vs new-Leiden | Ratio of incremental assignment efficiency |

### Drill-Down 7: Signals (click "In Signals")

| Panel | Metric | What it shows |
|-------|--------|--------------|
| Signals per topic | `analyst_signals_fired_total` by topic | Time series |
| ISC distribution | Histogram/bar: clusters with ISC=1, 2, 3+ | Shows how close clusters are to signal threshold |
| Status breakdown | Gauge: new / acknowledged / dismissed | Signal lifecycle |
| Cross-topic convergence | `analyst_signals_fired_total{type="cross_topic"}` | Convergence signals separately |
| Time to signal | Histogram: scrape timestamp → signal fired timestamp | How fast the pipeline detects narratives |
| Recent signals | Loki: signal fire entries | Cluster label + ISC count + topic |

---

## New Prometheus Metrics Required

### Scraper service (`services/scraper/anveshak/scraper/metrics.py`)

```python
scraper_content_quality_total = Counter(
    "scraper_content_quality_total",
    "Content items by quality gate outcome",
    ["quality", "gate"],
    # quality: good, low_quality
    # gate: too_short, paywall, nav_icon, ratio, bypass, passed
    registry=registry,
)

scraper_url_seen_skip_total = Counter(
    "scraper_url_seen_skip_total",
    "URLs skipped due to Redis seen-tracking",
    registry=registry,
)

scraper_links_discovered_total = Histogram(
    "scraper_links_discovered_total",
    "Article links discovered per source page",
    buckets=[0, 1, 5, 10, 25, 50, 100],
    registry=registry,
)
```

**Instrumentation points:**
- `scraper_content_quality_total`: in `_insert_content()` after `score_content_quality()` returns. Requires `score_content_quality()` to also return which gate rejected (see below).
- `scraper_url_seen_skip_total`: in `_process()` where `_is_url_seen()` returns True.
- `scraper_links_discovered_total`: in `_process()` after `extract_article_links()` returns.

**Change to `score_content_quality()`:** Return a tuple `(quality, gate)` instead of just `quality`:
```python
def score_content_quality(raw_text, clean_text) -> tuple[str, str]:
    if not clean_text or len(clean_text) < _MIN_CLEAN_CHARS:
        return ("low_quality", "too_short")
    if is_paywall_page(raw_text) or is_paywall_page(clean_text):
        return ("low_quality", "paywall")
    if is_nav_icon_garbage(clean_text):
        return ("low_quality", "nav_icon")
    if not raw_text:
        return ("good", "passed")
    if len(clean_text) >= _RATIO_BYPASS_MIN_CHARS:
        return ("good", "bypass")
    ratio = len(clean_text) / len(raw_text)
    if ratio < _MIN_QUALITY_RATIO:
        return ("low_quality", "ratio")
    return ("good", "passed")
```

All callers of `score_content_quality()` need updating to unpack the tuple. This includes:
- `services/scraper/anveshak/scraper/jobs.py` (3 call sites: web, RSS, darkweb)
- `scripts/backfill_quality_and_titles.py` (1 call site)

### Analyst service (`services/analyst/anveshak/analyst/metrics.py`)

```python
analyst_embedding_completed_total = Counter(
    "analyst_embedding_completed_total",
    "Content items successfully embedded",
    registry=registry,
)

analyst_content_skipped_quality_total = Counter(
    "analyst_content_skipped_quality_total",
    "Content items skipped by analyst quality gate",
    ["gate"],
    # gate: too_short, few_words, unique_ratio, punctuation
    registry=registry,
)

analyst_clustering_items = Gauge(
    "analyst_clustering_items",
    "Items by clustering status per topic",
    ["topic_id", "status"],
    # status: assigned, unassigned, filtered_relevance, filtered_quality
    registry=registry,
)

analyst_orphan_sweep_total = Counter(
    "analyst_orphan_sweep_total",
    "Items re-enqueued by orphan sweep",
    registry=registry,
)

analyst_clustering_edges = Gauge(
    "analyst_clustering_edges",
    "Edges formed in Leiden similarity graph per topic",
    ["topic_id"],
    registry=registry,
)
```

**Instrumentation points:**
- `analyst_embedding_completed_total`: in `analyse_content()` after successful embedding write.
- `analyst_content_skipped_quality_total`: in `analyse_content()` where `is_quality_content()` returns False. Requires `is_quality_content()` to return which gate failed (same tuple pattern as scraper).
- `analyst_clustering_items`: in `run_clustering()` after Leiden completes — set gauge per topic with assigned/unassigned counts.
- `analyst_orphan_sweep_total`: in `orphan_sweep()` after re-enqueue batch.
- `analyst_clustering_edges`: in `run_clustering()` after graph construction — count edges.

**Change to `is_quality_content()`:** Return `(bool, str)` instead of just `bool`:
```python
def is_quality_content(text: str) -> tuple[bool, str]:
    if len(stripped) < settings.content_min_length:
        return (False, "too_short")
    if len(words) < 5:
        return (False, "few_words")
    if unique_ratio < settings.content_min_unique_word_ratio:
        return (False, "unique_ratio")
    if punct_ratio > settings.content_max_punctuation_ratio:
        return (False, "punctuation")
    return (True, "passed")
```

---

## Existing Metrics to Surface (have data, no Grafana panel yet)

| Metric | Currently in | Add to dashboard |
|--------|-------------|-----------------|
| `analyst_topic_relevance_score` | analyst/metrics.py | Drill-Down 5: Relevance histogram |
| `analyst_topic_relevance_threshold` | analyst/metrics.py | Drill-Down 5: Per-topic threshold gauge |
| `scraper_circuit_breaker_total` | scraper/metrics.py | Drill-Down 1: Source health transitions |
| `scraper_sources_skipped_total` | scraper/metrics.py | Drill-Down 1: Skipped due to circuit breaker |
| `social_quota_remaining` | social/metrics.py | Row 1: X/Twitter budget remaining |

---

## Grafana Technical Implementation

### Template variables (top of dashboard)

| Variable | Type | Values |
|----------|------|--------|
| `$topic` | Query (PostgreSQL) | `SELECT name FROM topics WHERE status = 'active'` |
| `$timerange` | Interval | 1h, 6h, 24h, 7d, 30d |
| `$platform` | Custom | all, rss, web, telegram, social |

### Data links (clickable drill-down)

Each stat panel in the funnel has a data link:
```
Panel: "Gate 1-4 Pass" → URL: /d/pipeline-quality?var-topic=$topic
Panel: "Embedded"       → URL: /d/pipeline-embedding?var-topic=$topic
Panel: "Clustered"      → URL: /d/pipeline-clustering?var-topic=$topic
Panel: "In Signals"     → URL: /d/pipeline-signals?var-topic=$topic
```

### Dashboard files

| File | Dashboard |
|------|-----------|
| `infra/configs/grafana/dashboards/anveshak_pipeline_funnel.json` | Main funnel view (5 rows) |
| `infra/configs/grafana/dashboards/anveshak_pipeline_quality.json` | Drill-down: Gates 1-8 |
| `infra/configs/grafana/dashboards/anveshak_pipeline_embedding.json` | Drill-down: Embedding + orphans |
| `infra/configs/grafana/dashboards/anveshak_pipeline_relevance.json` | Drill-down: Relevance scoring |
| `infra/configs/grafana/dashboards/anveshak_pipeline_clustering.json` | Drill-down: Clustering health |
| `infra/configs/grafana/dashboards/anveshak_pipeline_signals.json` | Drill-down: Signal analysis |

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `services/scraper/anveshak/scraper/metrics.py` | ADD 3 new metrics |
| `services/scraper/anveshak/scraper/clean.py` | MODIFY `score_content_quality()` to return `(quality, gate)` tuple |
| `services/scraper/anveshak/scraper/jobs.py` | MODIFY callers to unpack tuple + increment counters |
| `services/analyst/anveshak/analyst/metrics.py` | ADD 5 new metrics |
| `services/analyst/anveshak/analyst/content_quality.py` | MODIFY `is_quality_content()` to return `(bool, gate)` tuple |
| `services/analyst/anveshak/analyst/jobs.py` | MODIFY caller to unpack + increment counter |
| `services/analyst/anveshak/analyst/clustering.py` | ADD gauge updates after Leiden |
| `services/analyst/anveshak/analyst/scheduler.py` | ADD counter increment in orphan_sweep |
| `scripts/backfill_quality_and_titles.py` | MODIFY to handle tuple return from score_content_quality |
| `infra/configs/grafana/dashboards/anveshak_pipeline_funnel.json` | NEW |
| `infra/configs/grafana/dashboards/anveshak_pipeline_quality.json` | NEW |
| `infra/configs/grafana/dashboards/anveshak_pipeline_embedding.json` | NEW |
| `infra/configs/grafana/dashboards/anveshak_pipeline_relevance.json` | NEW |
| `infra/configs/grafana/dashboards/anveshak_pipeline_clustering.json` | NEW |
| `infra/configs/grafana/dashboards/anveshak_pipeline_signals.json` | NEW |
| `tests/unit/test_scraper_clean.py` | MODIFY tests for tuple return |
| `tests/unit/test_content_quality.py` | MODIFY tests for tuple return |

---

## Implementation Order

1. Modify `score_content_quality()` and `is_quality_content()` to return tuples
2. Update all callers + tests
3. Add new Prometheus metrics to scraper and analyst
4. Instrument code at each gate/stage
5. Create main funnel dashboard JSON
6. Create 6 drill-down dashboard JSONs
7. Rebuild + deploy scraper and analyst containers
8. Verify metrics flowing in Grafana

---

## What Each Issue From 2026-05-26 Would Look Like in This Dashboard

| Issue | Where visible | How |
|-------|--------------|-----|
| 53% quality rejection | Row 2 funnel: "Gate 1-4" bar at 47% of "Scraped" | Immediate red flag |
| Which gate? Ratio gate | Drill-down 2: Gate 4 bar dominates | Click to see ratio histogram |
| 208 stuck items | Row 2: gap between "Gate 5-8" and "Embedded" | 208 items went in, 0 came out |
| Why stuck? Analyst skipped | Drill-down 3: Gate 7 (unique_ratio) dominates | Shows nav-page content failing word diversity |
| 95% unassigned LAC | Row 4: LAC bar at 5% | Immediate red flag per topic |
| Why? Threshold too high | Drill-down 6: edge count near zero for LAC | Sparse graph = threshold too tight |
| Andaman Sea zero | Row 3 table: all zeros for Andaman Sea | Obvious gap |
| Why? No sources | Drill-down 1: Andaman Sea shows 0 in per-source breakdown | No sources linked |
| NDTV RSS broken | Row 1: source health shows degraded | DNS error in Loki panel |
