# Bidadi Township — Demo Script (MHA/IB)

**Date:** 2026-08-13 (Thursday)
**Audience:** Ministry of Home Affairs / Intelligence Bureau (MAC coordination role)
**Duration:** ~24 minutes (18 min Anveshak + 5 min Drishti + buffer)
**Login:** demo_bidadi@anveshak.local / AnveshakDemo2024!

---

## The Pitch (one line)

> "Five agencies look at Bidadi through five lenses. Anveshak shows one screen."

---

## Live Topic IDs

| Topic | ID | Status |
|-------|-----|--------|
| Civil Unrest & Protest Coordination | `e48e93e7-4247-47c6-949c-dc3466f987ab` | active |
| Land Deal Nexus & Financial Irregularities | `8b54f649-2c14-4fce-90ae-0328f9fe48a8` | active |
| Foreign Linkages & Information Warfare | `11f7dd05-9d92-4c2a-804b-8cb214d39f87` | active |

---

## Pre-Demo Checklist

- [ ] Seed SQL loaded (`scripts/seed_bidadi_demo.sql`)
- [ ] 3 topics visible on dashboard
- [ ] Deccan Herald RSS source ready for live scrape
- [ ] Pre-generated report + PDF available
- [ ] Drishti Preview tab verified on Topic 2 (click 🔮 tab in Intelligence Graph)

---

## Beat 0 — The Hook (1 min)

**Screen:** Blank. Talk only.

> "Bidadi Township. 460-day farmer protest. You know it as a law-and-order
> problem. We'll show you it's five intelligence problems on one map —
> civil unrest, financial crime, foreign funding, information warfare,
> and political manipulation. No single agency sees all five. Anveshak does."

---

## Beat 1 — Login & Topics Overview (2 min)

**Screen:** Login → Dashboard → 3 topics.

| Topic | Sources | Items | Narratives |
|-------|---------|-------|------------|
| Civil Unrest & Protest Coordination | News RSS, X/Twitter, YouTube | ~60 | 4 |
| Land Deal Nexus & Financial Irregularities | News RSS, Gov portals, SEBI | ~40 | 4 |
| Foreign Linkages & Information Warfare | News RSS, X/Twitter, Change.org | ~30 | 4 |

> "Three concurrent operations. 17 sources. 6 platforms. Running 24/7
> on one machine in your premises. No cloud. No analyst searching."

---

## Beat 2 — Live Scrape (2 min)

**Action:** Add Deccan Herald Bidadi RSS feed live. Let them watch.

> "Let me add a source right now."

- Add RSS: `https://www.deccanherald.com/tag/bidadi/rss` (or equivalent)
- Wait for scrape cycle (show the spinner)
- New articles appear in content feed
- Show credibility score auto-assigned (Deccan Herald = ~80)

> "Not pre-loaded. Not a recording. Live intelligence collection."

---

## Beat 3 — Topic 1: Civil Unrest Deep Dive (3 min)

**Screen:** Narrative view for Topic 1.

**Expected narratives:**
1. **"Farmer displacement & livelihood"** — genuine grievance articles (10,580 farmers, 9 villages, dairy/sericulture destruction)
2. **"Political weaponization"** — BJP Freedom Park protest, JD(S) padayatra, coordinated opposition
3. **"Escalation rhetoric"** — "blood protest", "give us poison", "Punjab-style agitation", mass suicide threats
4. **"Women's resistance"** — broom attack at Mandalahalli, women SHG mobilization

**Key moments:**
- Click into escalation narrative → show sentiment scores (strongly negative)
- Show timeline: rhetoric intensity increasing over last 30 days
- Signal: "Escalation markers crossed threshold — 3 independent sources"

> "Your State Intelligence sees a protest. But the system flagged escalation
> language matching the Punjab farm laws pattern — 'blood protest', 'give us
> poison', 'mass suicide'. That's an early warning, not a headline."

---

## Beat 4 — Topic 2: Land Deal Nexus (3 min)

**Screen:** Narrative view → Entity graph for Topic 2.

**Expected narratives:**
1. **"Sobha-Shivakumar SEBI settlement"** — SEBI order SO/AA/HP/2022-23/6654-6658, Rs 2.93cr, residence construction
2. **"GBDA formation & tender"** — Rs 26cr DPR tender, HUDCO Rs 21,000cr loan, P Rajendra Cholan
3. **"Kumaraswamy family land paradox"** — Kethaganahalli Sy 7-79, wife 36 acres, seeking compensation while opposing
4. **"Benniganahalli denotification"** — Sy 50/2, Rs 1.62cr, Puravankara JV, Lokayukta case

**Killer moment — Entity convergence:**

> "Watch this. DK Shivakumar appears in narrative 1 as Sobha's client.
> In narrative 2 as GBDA's creator. In narrative 4 as Benniganahalli's buyer.
> His brother DK Suresh sits on the GBDA board. Same person, three
> financial threads. Your ED sees one. Your ACB sees another.
> Anveshak sees all three connected."

**Show the low-credibility item:**
- Include one social media post alleging "Shivakumar owns 500 acres in Bidadi" (credibility: 18)
- System flags it as unverified, shows WHY (single source, no corroboration, social media platform)

> "And here's what the system did NOT trust. One Twitter post claiming
> 500 acres. Credibility 18 out of 100. Single source. Unverified.
> The system shows it, scores it, but doesn't treat it as fact.
> That's the difference between intelligence and noise."

**Drishti forward-reference (plant the seed):**

> "Anveshak found Shivakumar across three narratives in one topic.
> Drishti would tell you he appears across 47 intelligence threads,
> not just three. We'll show you that in a moment."

---

## Beat 5 — Topic 3: Foreign Linkages & Info Warfare (3 min)

**Screen:** Narrative view for Topic 3.

**Expected narratives:**
1. **"KRRS–La Via Campesina foreign funding"** — Amrita Bhoomi, Associazione SUM (Italy), Agroecology Fund (US), Christensen Fund, One Earth, Lush Spring Prize (UK)
2. **"Save Bidadi digital campaign"** — @vijayvruksha, Change.org petition (79K, ID 295807609), Project Vruksha Foundation
3. **"Narrative amplification"** — #SaveBidadi, #BidadiChalo, #BattleForBidadi hashtag tracking, BJP-JD(S) coordinated digital campaign

**The "dog that didn't bark":**

> "460 days. 10,000 farmers. Zero public crowdfunding. Zero UPI links.
> Zero Milaap campaigns. Compare Shaheen Bagh — crowdfunding pages within
> days. Farm laws protest — public donation drives everywhere. This
> absence IS the signal. The system generates three hypotheses..."

**Talk through (verbal, no UI panel):**

> "Three hypotheses. One — party-funded. JD(S) and BJP both providing
> legal aid, logistics, padayatra infrastructure. High confidence,
> confirmed by news. Two — informal cash, possibly hawala. 460-day camp,
> significant logistics cost, zero visible funding. Medium confidence,
> needs ground verification. Three — foreign-routed via NGO. KRRS's
> neighbour Amrita Bhoomi receiving Italian, American, British grants
> through La Via Campesina. Low-medium — funding to org confirmed,
> link to protest logistics unconfirmed."

> "Your FCRA cell tracks La Via Campesina manually. Anveshak maps the
> chain automatically — Italian farmer org funded Amrita Bhoomi,
> DARPAN registration 129/1997-98, registered at Rajarajeshwari Nagar
> 560098. KRRS headquarters? RMG-S20-2013-14, also Rajarajeshwari Nagar
> 560098. Same pincode. Same locality. The foreign-funded training
> centre and the protest union — neighbors. Five hops. Real registration
> numbers. Found from open sources."

---

## Beat 6 — Cross-Topic Convergence (2 min)

**Navigate:** Sidebar → Signals → "New" tab (8 signals visible)

**Walk through signals in order:**

1. Click **"Farmer displacement confirmed by 5 sources"** — shows multi-source convergence
2. Click **"Escalation rhetoric confirmed by 4 sources"** — links back to Beat 3 narratives
3. **KILLER MOMENT** — Click **"CRITICAL: DK Shivakumar across ALL 3 topics"**

> "No single agency sees this. State Intelligence sees a protest. ED sees
> a land deal. FCRA cell sees foreign money. But watch this signal..."

4. Click **"Kumaraswamy family opposing while owning land"** — paradox surfaced
5. Click **"Same Kethaganahalli Sy 7-79 in protest AND encroachment case"** — location convergence
6. Click **"Amrita Bhoomi + KRRS same pincode 560098"** — organizational proximity from DARPAN data

> "Three topics. Three agencies. One machine connected the dots.
> What MAC coordinates in weekly meetings across 5 agencies,
> Anveshak surfaces in real-time."

---

## Beat 7 — Report & PDF (1.5 min)

**Screen:** Generated intelligence brief.

- Show source citations with credibility scores
- Show "source_snapshot" — credibility at generation time
- Show PDF export
- Show immutable evidence chain — "this report cannot be edited after generation"

> "Audit-grade. Every claim traced to source. Every source scored.
> If a source is later downgraded, the system flags the report —
> but never changes it. Point-in-time truth."

---

## Beat 8 — REMOVED (merged into Beat 10)

---

## Beat 9 — The Close (1.5 min)

> "One analyst. One machine. Your premises. Zero cloud.
> Your MAC brief, automated, every morning, on your hardware.
>
> Built under iDEX ADITI 4.0 PS-18. Defence-grade. Not a startup toy.
>
> Anveshak is the collection and analysis layer.
> Drishti is the knowledge graph.
> Together — what no agency in India has today."

**Leave behind:** Printed case study + USB with PDF report sample.

---

## Beat 10 — Drishti Preview: Entity Resolution (5 min)

**Transition from Beat 9 close:**

> "You asked about Drishti. Let me show you what it does."

**Navigate:** Topic 2 (Land Deal Nexus) → Intelligence Graph → Click **🔮 Drishti Preview** tab.

The 3D force graph loads — glowing nodes, particles flowing along edges, auto-rotating.
Preview banner clearly reads: *"Preview — What Drishti entity resolution would surface from this data"*

**FALLBACK:** If 3D graph doesn't render, stay on Key Players tab and deliver the talk track verbally over the existing entity graph. The data is the same — Shivakumar, KRRS, Kumaraswamy all visible. The 3D visualization is the "wow" but the story works without it.

**Capability 1 — Entity Resolution (90 sec):**

> "You saw Shivakumar in three narratives inside one topic. That's Anveshak.
> Now look at this graph. Shivakumar appears in ALL three topics — civil unrest,
> land deals, foreign linkages. Same person, different spellings, different
> contexts. 'DK Shivakumar', 'Siddaramaiah cabinet Shivakumar', 'CM Shivakumar'.
> Drishti resolves these into one node. Fifteen edges, not five."

**Click the glowing Shivakumar node** — detail panel shows topic breakdown with mention counts.

**Capability 2 — Multi-Agency Correlation (90 sec):**

> "State Intelligence sees the protest. ED sees the SEBI settlement.
> FCRA cell sees Italian money reaching Rajarajeshwari Nagar.
> Three agencies. Three databases. Zero overlap.
> Drishti takes Anveshak output from each agency and builds THIS graph.
> The connection between KRRS and Amrita Bhoomi — same pincode, 560098 —
> no single agency would flag it. Drishti does."

**Capability 3 — Multi-Instance Bridging (60 sec):**

> "Each agency runs their own Anveshak. Sovereign. On their premises.
> Drishti sits at MAC. Federates entities across instances.
> Same mule account in Bengaluru cyber fraud AND Bidadi land deal?
> Drishti surfaces it. No agency shares raw data. Only resolved entities."

**Close (30 sec):**

> "Anveshak is collection and analysis. One machine, one officer.
> Drishti is fusion. One graph, all agencies.
> Together — what MAC doesn't have today."

**IMPORTANT:** On other topics (Topic 1, Topic 3), the Drishti Preview tab shows:
*"Entity resolution for this topic — coming with Drishti."*
This is by design — only Topic 2 has demo data seeded.

---

## If They Ask...

| Question | Answer |
|----------|--------|
| "Can it monitor WhatsApp?" | "WhatsApp bridge operational. Requires pairing with a number. We can demo separately." |
| "What about Telegram?" | "Telethon adapter live. We can add Kannada news channels right now." (demo if time) |
| "Air-gapped?" | "Yes. Docker Compose. Ollama runs locally. Zero outbound connections. We'll share the compose file." |
| "What LLM?" | "Qwen2 7B via Ollama. Runs on CPU. Upgradable to any model — env var change only." |
| "Cost?" | "Rs 25L/workstation/year. Zonal: Rs 80L. National HQ: custom." |
| "When Drishti?" | "3 months after Anveshak deployment. Entity bridge is already built — one env var enables it." |
| "Drishti infrastructure?" | "3-node minimum. Redpanda cluster, AGE graph DB, Vault, Keycloak. We handle deployment." |
| "Drishti without Anveshak?" | "Drishti consumes Anveshak output. Anveshak runs standalone. Drishti needs at least one Anveshak feeding it." |
| "Drishti cost?" | "Separate contract. We'll share pricing in the follow-up." |
| "Can we pilot Drishti?" | "Deploy Anveshak first. Once collecting, we activate Drishti bridge — same hardware, additional software layer." |
| "Can we test on our own topic?" | "Yes. Give us a topic, we'll set it up in 30 minutes." |

---

## Real Identifiers Used in Demo

All identifiers are from public sources — news articles, SEBI orders, court filings, government notifications.

### Persons
- DK Shivakumar (CM), DK Suresh (brother, GBDA member)
- Ravi PNC Menon, Jagdish Chandra Sharma (Sobha, SEBI noticees)
- Anita Kumaraswamy (HDK wife, 36-37 acres Kethaganahalli)
- DC Thamanna (ex-minister, 110 acres joint survey)
- P Rajendra Cholan (GBDA Commissioner)
- Nagaraju R (farmer, Mandalahalli, 12 acres)
- Kadyamada Manu Somaiya (KRRS Kodagu president, arrested)
- Vijay Nishanth (@vijayvruksha, Save Bidadi petition)
- Chukki Nanjundaswamy (Amrita Bhoomi, KRRS)
- Justice Santosh Hegde (retd Lokayukta, solidarity)
- Justice Guhanathan Narendar (review committee chair)
- Kabbale Gowda, TJ Abraham (Lokayukta complainants)
- G Madegowda (ex-Mandya MP, complainant)
- Mohammed Sameer (FIR complainant)

### Documents
- SEBI order: SO/AA/HP/2022-23/6654-6658 (Rs 2,92,50,000)
- Sobha Ltd: BSE 532784
- Benniganahalli: Survey No 50/2, Rs 1.62cr (2003)
- Kethaganahalli: Survey No 7, 8, 9, 10, 16, 79
- GBDA tender: Rs 26cr DPR
- HUDCO loan: Rs 21,000cr
- Karnataka Act No 36 of 2025
- Gazette: DPAL 45 SHASANA 2024
- Phase 1: 518 acres (Kempegowdanapalya 367, Mandalahalli 70, Oderahalli 61)
- Change.org petition: ID 295807609 (79K signatures)
- 2 FIRs: Bidadi Police Station, Jul 13, 2026 (BNS 2023 sections)

### DARPAN Registration (from ngodarpan.gov.in — REAL)
| Org | DARPAN Reg No | District | Address | Sectors |
|-----|--------------|----------|---------|---------|
| AMRITA BHOOMI | 129/1997-98 OF BOOK IV PAGES 1 | BENGALURU URBAN | 636, Ideal Homes Layout, Rajarajeshwari Nagar, 560098 | -- |
| KARNATAKA RAJYA RAITHA SANGHA | RMG-S20-2013-14 | BENGALURU URBAN | 4th Floor, Remco Bhel Layout, Kenchenhalli, Rajarajeshwari Nagar, 560098 | Agriculture, Animal Welfare, Environment & Forests, Food Processing, Land Resources, Micro Finance (SHGs), Panchayati Raj, Rural Dev |
| KRRS Yuva Sene Trust | BK IV BNG-BHM42/2025-26 | BENGALURU URBAN | Tammenhalli, Chickbanawara, Bengaluru North, 560090 | Agriculture, Environment & Forests |
| KRRS Hasiru Sene Raichur | DRRH/SOR/352/2021-2022/21048 | RAICHUR | Daradoddi, Devadurga, 584111 | -- |

**KEY FINDING:** Amrita Bhoomi (foreign-funded) and KRRS HQ share same locality — Rajarajeshwari Nagar, Bengaluru 560098. Organizational proximity = demo-worthy cross-link.

### Foreign Funding Chain
- Associazione SUM (Italy) → Amrita Bhoomi (Reg 129/1997-98, Rajarajeshwari Nagar 560098)
- Agroecology Fund (US) → Amrita Bhoomi
- Christensen Fund → Agroecology Fund (indirect)
- One Earth → Amrita Bhoomi (project grant)
- Lush Spring Prize (UK) → Amrita Bhoomi (2018 nominee)
- **Amrita Bhoomi (560098) ↔ KRRS HQ (560098) = same neighborhood**

### Telegram Channels (joined, real)
| Channel | Handle | Credibility |
|---------|--------|-------------|
| Haveri Raita Sanga KRRS | @HaveriRaitaSangaKRRS | 22 |
| ಸ್ವಾಭಿಮಾನ ಸ್ವಾತಂತ್ರ ಸಮಾನತೆ | (name-based) | 15 |

### Social Handles
- @DKShivakumar, @NikhilKSwamy, @BYVijayendra
- @vijayvruksha (Vijay Nishanth)
- @IndexKarnataka (development data)
- @krrs_kodagu (Instagram)
- KRRS Facebook: /Karnataka-Rajya-Raitha-Sangha-100054201683227

### Locations
- KRRS HQ: #699, 1st Floor, 13 Main Rd, TK Layout, Ramakrishnanagar, Mysore 570022
- Affected villages: Bhyramangala, Bannigiri, Mandalahalli, Kanchugaranahalli, Kempayyanahalli, Hosuru, Aralusandra, KJ Gollarapalya
- Padayatra stopped: Kanaminike Village, Bengaluru-Mysuru Highway
