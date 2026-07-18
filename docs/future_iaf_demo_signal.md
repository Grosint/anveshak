# Future IAF Demo — Identifier Intelligence Improvements

## Current State (2026-07-15)

### Identifier Clusters in DB

| ID | Topic | Type | Value | Sources | Items | Status |
|----|-------|------|-------|---------|-------|--------|
| iaf-ic-01 | topic-02 (Disinfo) | TELEGRAM_HANDLE | fake_iaf_leaks | 4 | 6 | STRONG — 4 sources across platforms |
| iaf-ic-03 | topic-01 (Chinese Air) | AIRCRAFT_ID | J-20 serial 78271 | 3 | 3 | OK — but only 2 distinct sources |
| iaf-ic-02 | topic-01 (Chinese Air) | TELEGRAM_HANDLE | china_mil_watch | 1 | 5 | WEAK — single source |

### Problems

1. **AIRCRAFT_ID not in frontend filter dropdown** — `Identifiers.tsx` line 8-26 has 17 types but no `AIRCRAFT_ID`. Still renders in top/cluster views but can't be filtered by type.
2. **Topic-scoped page** — fake_iaf_leaks (topic-02) and J-20 serial (topic-01) require topic switching during demo.
3. **china_mil_watch source_count=1** — not demo-worthy, skip in talk track.
4. **@fake_iaf_leaks is fictional** — created in seed SQL. Does NOT exist on Telegram. If officer searches — nothing. Frame as: "channel may have been deleted or renamed."

### Linked Content Items

**fake_iaf_leaks (4 sources, 6 items):**
- iaf-ci-21 — "URGENT ALERT: Fabricated video..." (IAF Disinfo Alert, telegram)
- iaf-ci-23 — "Defence Forum India thread..." (Defence Forum India, reddit)
- iaf-ci-25 — "Bellingcat investigation identifies..." (Bellingcat OSINT, web)
- iaf-ci-26 — "New deepfake: fabricated HAL Tejas..." (Air Power India, telegram)
- iaf-ci-29 — "@fake_iaf_leaks channel still active..." (IAF Disinfo Alert, telegram)
- iaf-ci-52 — "IAF Disinfo Alert analysis..." (IAF Disinfo Alert, telegram)

**J-20 serial 78271 (3 items):**
- iaf-ci-03 — "BREAKING: New satellite pass shows 4x J-20 at Kashgar... Serial 78271 visible on tail." (China Mil Watch)
- iaf-ci-04 — "Defence OSINT: Multiple J-20 sorties... Serial 78271 confirmed again." (Defence OSINT)
- iaf-ci-11 — "Two-ship J-20 formation... Serial 78271 and 78273 identified." (China Mil Watch)

## Future Improvements

### 1. Add AIRCRAFT_ID to frontend filter
File: `frontend/src/pages/Identifiers.tsx` line ~20
```typescript
{ value: 'AIRCRAFT_ID', label: 'Aircraft ID' },
```

### 2. Strengthen J-20 serial cluster
Add more content items mentioning serial 78271 from additional sources (Jane's, Indian Defence Review) to increase source_count from 2 to 4.

### 3. Add cross-topic identifier view
Currently topic-scoped. For defence demo, a cross-topic identifier view showing same identifier appearing across Chinese Air Power + Disinformation topics would be powerful.

### 4. Demo navigation path (current workaround)

**Stay in Topic 2** (Anti-IAF Disinformation) after Beat 4:
1. Click **Identifiers** tab in workspace
2. Show `fake_iaf_leaks` — 4 sources, 6 items
3. Click to expand → items from Telegram, Reddit, Web, Telegram (4 platforms)
4. SAY: "Same Telegram handle across 4 independent sources, 3 platforms. Network node identified automatically."

**Switch to Topic 1** (Chinese Air Power):
5. Click **Identifiers** tab
6. Show `J-20 serial 78271` — 3 sources
7. Click to expand → Kashgar satellite image + Aksai Chin sorties + formation photo
8. SAY: "Same aircraft serial tracked from Kashgar to Aksai Chin. Movement tracking from open sources."

### 5. Consider adding more identifier types for defence context
- `AIRCRAFT_ID` — tail numbers, serials
- `VESSEL_ID` — IMO numbers, hull numbers
- `UNIT_ID` — military unit designations
- `EXERCISE_NAME` — joint exercise codenames (Shaheen-X, Cope India)
