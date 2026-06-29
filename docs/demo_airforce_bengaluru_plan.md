# Air Force Bengaluru Demo — Seed Data Plan

**Status:** IMPLEMENTED (2026-06-29)
**Created:** 2026-06-28
**Target file:** `scripts/seed_airforce_bengaluru_demo.sql`

## Context

IAF Bengaluru demo — companion to Nagaland (police/social unrest) and Telangana (cyber fraud).
Bengaluru = HAL HQ, DRDO ADA (Tejas/AMCA), Aero India venue, IAF Training Command.
Audience: IAF intelligence officers monitoring adversary air capabilities + info warfare.

## Data Architecture

```
org_iaf (Air Force Intelligence Wing)
└── demo_iaf@anveshak.local (analyst, password: AnveshakDemo2024!)
    ├── Topic 1: Chinese Air Power — LAC Threat Assessment
    │   ├── Cluster 1: J-20 Stealth Deployments near LAC (12 items)
    │   ├── Cluster 2: PLAAF UAV/Drone Activity — Northern Borders (8 items)
    │   └── Cluster 5: Tibet Airbase Infrastructure Expansion (8 items)
    │
    ├── Topic 2: Anti-IAF Disinformation & Deepfakes
    │   ├── Cluster 3: Coordinated Deepfake Campaign (10 items)
    │   └── Cluster 6: HAL/DRDO Misinformation Narratives (7 items)
    │
    └── Topic 3: PAF Modernization & Force Posture
        └── Cluster 4: JF-17 Block 3 & PAF-PLAAF Exercises (10 items)
```

**Total: 55 content items, 6 clusters, 3 topics**

## Sources (16)

| ID | Name | Platform | Credibility | Topics |
|----|------|----------|-------------|--------|
| iaf-src-01 | Jane's Defence Weekly | rss | 91 | 1,3 |
| iaf-src-02 | The War Zone | rss | 80 | 1,2 |
| iaf-src-03 | Indian Defence Review | rss | 76 | 1,3 |
| iaf-src-04 | LiveFist Defence | rss | 74 | 1,2,3 |
| iaf-src-05 | SCMP Defence | rss | 72 | 1 |
| iaf-src-06 | Global Times Military | web | 35 | 1 |
| iaf-src-07 | Defence.pk Forum | web | 40 | 3 |
| iaf-src-08 | SIPRI Arms Transfers | web | 88 | 3 |
| iaf-src-09 | @defence_osint | telegram | 55 | 1,2 |
| iaf-src-10 | @china_mil_watch | telegram | 48 | 1 |
| iaf-src-11 | @paf_tracker | telegram | 42 | 3 |
| iaf-src-12 | @iaf_disinfo_alert | telegram | 50 | 2 |
| iaf-src-13 | @airpower_india | telegram | 45 | 1,2,3 |
| iaf-src-14 | Military Aviation IG | instagram | 52 | 2 |
| iaf-src-15 | Defence Forum India | reddit | 35 | 2,3 |
| iaf-src-16 | Bellingcat OSINT | web | 85 | 1,2 |

## Narrative Clusters (6)

### Cluster 1: J-20 Stealth Deployments near LAC (12 items, Topic 1)
- Satellite imagery of J-20s at Hotan Airbase, Xinjiang
- PLAAF exercises with J-20 near Aksai Chin corridor
- WS-15 engine upgrade implications for range/endurance
- J-20 spotted at Kashgar forward operating base
- Multiple sources: Jane's, satellite OSINT, SCMP, Global Times, Telegram

### Cluster 2: PLAAF UAV/Drone Activity — Northern Borders (8 items, Topic 1)
- WZ-7 Soaring Dragon high-altitude ISR near Ladakh
- Wing Loong III armed UCAV at Kashgar
- GJ-11 stealth drone development tests
- Drone sortie patterns correlating with Indian exercise schedules
- Sources: OSINT Telegram, defence RSS, Bellingcat

### Cluster 3: Coordinated Deepfake Campaign Against IAF (10 items, Topic 2)
- Fake Rafale shootdown video (deepfake probability 0.94)
- Fabricated HAL Tejas crash footage using Ukraine conflict imagery
- Amplification network: 15+ Telegram channels within 4 hours
- Vision analysis job result with EXIF anomalies
- Sources: Telegram, Reddit, Instagram, web OSINT

### Cluster 4: JF-17 Block 3 & PAF-PLAAF Exercises (10 items, Topic 3)
- JF-17 Block 3 with KLJ-7A AESA radar induction
- PL-15 BVR missile integration confirmed
- PAF-PLAAF Shaheen-X joint exercise near Skardu
- Chinese J-10CP transfer to PAF under evaluation
- Sources: Defence.pk, Jane's, SIPRI, Telegram

### Cluster 5: Tibet Airbase Infrastructure Expansion (8 items, Topic 1)
- New 3,500m runway at Ngari Gunsa airbase
- Hardened aircraft shelters at Lhasa Gonggar
- Fuel and ammunition depot construction near Shigatse
- Satellite imagery timeline showing construction phases
- Sources: satellite OSINT, think tanks, news RSS

### Cluster 6: HAL/DRDO Misinformation Narratives (7 items, Topic 2)
- Tejas delay narratives weaponized by adversary media
- AMCA timeline disinformation (fake "cancelled" reports)
- Coordinated social media campaign questioning LCA capability
- Sources: adversary news (Global Times, Defence.pk), social media

## Signals (5)

| Signal | Type | Cluster | ISC | Severity |
|--------|------|---------|-----|----------|
| J-20 deployment near LAC convergence | multi_source_convergence | Cl-1 | 5 | HIGH |
| Deepfake campaign detected — 4 platforms | threshold_breach | Cl-3 | 4 | CRITICAL |
| PAF Block 3 induction confirmed | multi_source_convergence | Cl-4 | 3 | MEDIUM |
| Tibet airbase construction confirmed | multi_source_convergence | Cl-5 | 4 | HIGH |
| Telegram amplification network identified | identifier_convergence | — | 3 | HIGH |

## Identifier Clusters (3)

1. **Telegram handle `@fake_iaf_leaks`** — appears across 4 disinfo content items (amplification node)
2. **Telegram handle `@china_mil_watch`** — forwarding source for 5 items across topics
3. **Aircraft identifier `J-20 serial 78271`** — tracked across 3 independent sources

## Keyword Alert Rules (4)

1. Topic 1: `['J-20', 'stealth', 'Hotan', 'WS-15', 'fifth-gen']`
2. Topic 2: `['deepfake', 'fabricated', 'propaganda', 'fake video', 'AI-generated']`
3. Topic 3: `['JF-17', 'Block 3', 'PL-15', 'PAF', 'Shaheen']`
4. Topic 1: `['airbase', 'runway', 'Tibet', 'Ngari', 'hardened shelter']`

## Forwarding Chains (Telegram Network)

```
@china_mil_watch → @defence_osint (LAC content forwarded)
@iaf_disinfo_alert → @airpower_india (deepfake alerts forwarded)
@paf_tracker → @defence_osint (PAF content forwarded)
```

## Additional Seed Data

- **Vision analysis job:** Deepfake detection result for fake Rafale video (score 0.94, EXIF: GPS stripped, software: Runway Gen-3)
- **Credibility audit log:** Global Times downgraded 50→35 after sharing unverified deepfake 3x in 30 days
- **Sample report:** Intelligence brief on Topic 1 (Chinese Air Power) covering J-20 + UAV + airbase clusters

## Implementation Steps

1. Create `scripts/seed_airforce_bengaluru_demo.sql` (full seed SQL, idempotent)
2. Add `seed-demo-iaf` target to Makefile
3. Verify: run twice with zero conflicts, org isolation with demo_cyber account

## Verification Checklist

- [ ] SQL runs without errors
- [ ] Idempotent (run twice, zero conflicts)
- [ ] Login as demo_iaf → 3 topics visible
- [ ] Topic 1 → 28 items, 3 clusters, 2 signals
- [ ] Topic 2 → 17 items, 2 clusters, 1 signal + vision result
- [ ] Topic 3 → 10 items, 1 cluster, 1 signal
- [ ] Signals page → 5 signals across topics
- [ ] Entity graph → entities linked across clusters
- [ ] Identifier intelligence → 3 identifier clusters
- [ ] demo_cyber login → zero IAF data (org isolation)

## Content Realism Notes

All content based on publicly available OSINT scenarios:
- J-20 deployments at Hotan/Kashgar — well-documented by satellite OSINT community
- Shaheen exercises — public PAF-PLAAF annual exercises
- Deepfake military videos — documented phenomenon (Ukraine conflict precedent)
- JF-17 Block 3 — publicly announced PAF program
- Tibet airbase expansion — documented by satellite imagery analysts
