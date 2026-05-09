# Anveshak M1-M5 Gap Analysis

> Generated: 2026-05-09
> Overall completion: ~90% of PS-18 scope

The core PS-18 scope is built and tested. The gaps below are hardening, polish,
and edge-case coverage — not missing modules.

---

## M1 — Analyst (Source Credibility + NLP) — 100% Core

**Fully implemented:** Credibility scoring (3 auto-passes), audit log, NLP pipeline
(NER/keywords/sentiment), multilingual translation (NLLB-200), narrative clustering
(Leiden), signals engine (3 signal types), backfill, content dedup, topic relevance,
entity MinHash.

No functional gaps. This is the most mature module.

---

## M2 — Scraper (Web Crawling) — ~90%

**Fully implemented:** Crawl4AI + trafilatura fallback, RSS feeds, dark web (Tor),
content cleaning (430-line module, 38 tests), dedup (SHA-256), circuit breaker health
tracking, scheduled per-topic scraping, recursive link following, media download +
vision dispatch.

| Gap | Priority | Effort |
|-----|----------|--------|
| robots.txt not enforced — setting exists but never checked | P1 | Small |
| Per-source rate delay not enforced — `scraper_default_delay_s` setting unused | P1 | Small |
| Language hardcoded to "en" — analyst fixes post-hoc, but scraper should detect | P2 | Medium |
| No PDF text extraction — PDFs stored but text not extracted | P2 | Medium |
| No embedded video URL extraction — YouTube/Vimeo/TikTok links ignored | P3 | Medium |
| No HTTP-level caching — every cycle re-fetches all URLs | P3 | Medium |

---

## M3 — Social (Platform Adapters) — ~85%

**Fully implemented:** All 4 adapters (Telegram, Reddit, Bluesky, X/Twitter),
conformance suite, content ingestion pipeline, per-adapter scheduling, X spend guard
(atomic Redis INCR), media extraction.

| Gap | Priority | Effort |
|-----|----------|--------|
| No Bluesky quota guard — 7200 calls/day limit not tracked, can get blocked | P1 | Small |
| No adapter circuit breaker — chronically failing adapter retried forever | P1 | Medium |
| Settings validation at startup — missing credentials silently fail at runtime | P1 | Small |
| Bluesky media incomplete — images only, no external links or video embeds | P2 | Small |
| No credential refresh — expired tokens silently stop working | P2 | Medium |
| No backfill/catchup — content missed during downtime is lost | P2 | Medium |
| Incomplete metrics — missing `social_api_calls_total`, rate-limit counters, quota gauges | P2 | Small |
| X stream adapter — `XStreamAdapter` raises `NotImplementedError` (needs Enterprise API) | P3 | Large (contractual) |

---

## M4 — Vision (YOLO, CLIP, Deepfake, EXIF, pHash) — ~95%

**Fully implemented:** YOLOv8 object detection, CLIP classification, face deepfake
(ConvNeXt ONNX), non-face deepfake (EfficientNet ONNX), EXIF extraction (dual-backend),
pHash reverse lookup, video frame extraction, media retention cleanup, analyst credibility
integration.

| Gap | Priority | Effort |
|-----|----------|--------|
| DIRE model scaffold only — raises `NotImplementedError` on CPU (by design, needs GPU) | P3 | Large (hardware) |
| No video transcription — audio-to-text not implemented | P3 | Large |

Both are deferred pending hardware (GPU for DIRE) or scope expansion (transcription
is arguably beyond PS-18).

---

## M5 — Reporter (LLM Reports, GIS, PDF) — ~85%

**Fully implemented:** RAG-based LLM report generation (3 types), report immutability,
source snapshot, PDF export (WeasyPrint), GIS geocoding (offline, 3-tier), scheduled
reports (croniter), source credibility warnings, prompt templates with grounding rules.

| Gap | Priority | Effort |
|-----|----------|--------|
| Zero tests for scheduled report cron logic — `check_scheduled_reports()` untested | P1 | Small |
| Zero tests for source warning detection — `check_source_warnings()` untested | P1 | Small |
| No end-to-end worker integration test — all tests mock DB | P1 | Medium |
| No RAG credibility filtering test — low-credibility chunks could leak into reports | P2 | Small |
| Report type not validated against enum — invalid type silently defaults | P2 | Small |
| No report schema versioning docs — adding fields could break old reports | P2 | Small |
| Custom locations overlay not tested — defence-specific geocoding untested | P2 | Small |
| No PDF error handling tests — disk full, WeasyPrint failure untested | P3 | Small |

---

## Cross-Cutting / Frontend — ~90%

**Fully implemented:** JWT auth with expiry countdown, WebSocket signals (<=10s delivery),
topic/source CRUD, content feed (infinite scroll + filters + semantic search), report
builder (3 types + GIS + PDF), signal inbox (real-time + timeline + graph), MapLibre map,
vision media viewer (deepfake gauge + YOLO canvas + EXIF table + reverse search).

| Gap | Priority | Effort |
|-----|----------|--------|
| No unified analytics dashboard — metrics scattered across pages | P2 | Medium |
| No user management UI — only login, no user CRUD | P2 | Medium |
| No scheduled report management UI — cron configured only via API | P2 | Medium |
| No cross-topic intelligence in UI — backend has it, frontend doesn't expose | P3 | Medium |
| No analytics data export — no CSV/JSON export for charts | P3 | Small |

---

## Recommended Implementation Order

### Wave 1 — Quick Wins (1-2 days)

1. Enforce `robots.txt` in scraper
2. Enforce per-source rate delay
3. Add Bluesky quota guard (copy X pattern)
4. Add settings validation for social adapters
5. Write tests for reporter scheduled reports + source warnings
6. Validate report_type against enum

### Wave 2 — Hardening (3-5 days)

7. Social adapter circuit breaker
8. Reporter end-to-end integration test
9. RAG credibility filtering test
10. Scraper language detection (use langdetect)
11. Social credential refresh mechanism

### Wave 3 — Features (1-2 weeks)

12. Unified analytics dashboard
13. PDF text extraction in scraper
14. Social backfill/catchup on restart
15. User management UI
16. Scheduled report management UI
