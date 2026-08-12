# ANVESHAK DEMO — NCB (Narcotics Control Bureau)

**Audience:** NCB intelligence officers (national-level narcotics intelligence analysts)
**Duration:** 15-18 minutes (national agency = more depth than state STF)
**Objective:** NCB sees Anveshak as force multiplier for national narcotics intelligence; initiates pilot or procurement
**Login:** `ncb_demo@anveshak.local` / `AnveshakDemo2024!`
**Three topics:** Golden Crescent Heroin Pipeline, Synthetic Drug Networks, Maritime Drug Interdiction
**Your edge:** iDEX ADITI 4.0, sovereign, already used by defence (IAF) and police across states

---

## PRE-DEMO CHECKLIST (30 min before)

```
□ make ps                                    — all containers green
□ curl localhost:11434/api/tags              — qwen2:7b loaded
□ http://localhost:3000                      — frontend accessible
□ Login as ncb_demo@anveshak.local           — verify 3 topics visible
□ Topic 1 (Golden Crescent)                  — ~80 items, clusters visible
□ Topic 2 (Synthetic Drugs)                  — ~60 items, clusters visible
□ Topic 3 (Maritime Interdiction)            — ~40 items, clusters visible
□ Signals tab                                — 8-10 signals visible
□ Cross-topic identifier convergence signal  — CRITICAL signal visible
□ Pre-generate report for Topic 1            — so you can show instantly
□ make pdf-ncb                               — leave-behind PDF ready
□ Print 3 copies of case_study_ncb.md as PDF — hand one to each officer
□ Browser: dark mode, full screen, no bookmarks bar
□ Close all notifications
□ Phone on silent
□ Have case_study_ncb.md printed as leave-behind
```

---

## THE DEMO

---

### BEAT 0 — BEFORE THE SCREEN (2 min)

Do NOT open laptop. Eye contact.

**SAY:**

> "Thank you for the time, sir.
>
> Anveshak is built under iDEX ADITI 4.0 PS-18. Sovereign AI-OSINT
> platform — everything runs on local hardware, no cloud dependency,
> air-gap deployable. Already in use by defence forces and police
> across multiple states.
>
> We loaded NCB-relevant sources — NCB official feeds, DRI seizure
> reports, UNODC threat assessments, BSF border intelligence, Coast Guard
> maritime alerts, Telegram drug intelligence channels, dark web listings —
> and let the system run for 45 days on three operations relevant to
> your mandate. Let me show you what it found."

**WHY THIS WORKS:**
- "iDEX ADITI" — government-vetted, not random vendor
- "Already in use by defence and police" — social proof at the highest level
- "NCB official, DRI, UNODC, BSF, Coast Guard" — sources they know and respect
- "Three operations" — mirrors how NCB thinks (concurrent ops across zones)

**PAUSE.** Wait for nod.

---

### BEAT 1 — LOGIN + TOPICS OVERVIEW (1 min)

1. Open http://localhost:3000
2. Login: `ncb_demo@anveshak.local`
3. Topics Dashboard shows 3 topics

**SAY:**

> "Three topics — three operations running simultaneously on one machine:
>
> **Golden Crescent Heroin Pipeline** — Afghanistan to Mumbai. ~80 items
>   from 15 sources.
> **Synthetic Drug Networks** — dark web to street. ~60 items from 12 sources.
> **Maritime Drug Interdiction** — western and southern coast. ~40 items
>   from 10 sources.
>
> Each topic is an independent workspace — own sources, own signals,
> own reports. An NCB zonal office could run 10 operations simultaneously."

Click into **Golden Crescent Heroin Pipeline** first. This is the strongest topic.

---

### BEAT 2 — GOLDEN CRESCENT: CONTENT FEED (2 min)

4. Content feed opens — ~80 items
5. Scroll slowly

**SAY:**

> "Over 80 items collected from 15 sources. NCB official releases, DRI
> seizure reports, UNODC World Drug Report excerpts, BSF border
> intelligence, Tribune India, NDTV, Telegram drug intelligence channels,
> dark web monitoring — all collected automatically, 24/7."

6. Point at specific items:
   - NCB official release (credibility 95)
   - DRI seizure report (credibility 90)
   - Anonymous Telegram channel (credibility 10)

> "See the credibility spread. NCB official feed at 95. DRI at 90.
> Anonymous Telegram tip at 10. The system assigns credibility
> automatically — the analyst sees at a glance which sources to
> trust and which to cross-verify."

**DO NOT** explain how scraping works. DO NOT mention Crawl4AI or embeddings.

---

### BEAT 3 — GOLDEN CRESCENT: CLUSTER VIEW — CORE DEMO (4 min)

7. Switch to **Cluster View**

**SAY:**

> "This is where the platform earns its keep. The AI reads every item
> and groups them by narrative — which developments are connected."

Walk through clusters deliberately:

**Cluster: "Afghan Heroin Entry via Punjab Border" (14 items, 5 sources)**

> "14 items from 5 independent sources — BSF intercepts drone drops
> carrying heroin packets near Fazilka. NCB-DRI coordinated seizure
> at Attari. Telegram intelligence on new mule routes through Tarn Taran.
> Poppy husk concealment in agricultural trucks on NH-1.
>
> The system correlated all of these automatically. Five independent
> sources, one entry corridor picture."

**Cluster: "Gujarat Maritime Heroin Consignments" (12 items, 4 sources)**

> "Mundra port — 2,988 kg seizure pattern analysis. DRI container scan
> intelligence. Coast Guard suspicious vessel intercepts off Gujarat coast.
> Charas consignments via fishing trawlers from Makran coast.
> Four sources, one maritime pipeline."

**Cluster: "Mumbai Distribution Network" (10 items, 3 sources)**

> "NCB Mumbai zonal operations. Pedlar network arrests in Dongri and
> Kurla. Price fluctuations correlating with supply disruptions upstream.
> The system detected that heroin street prices in Mumbai spiked 40%
> after the Mundra seizure — supply chain economics from open sources."

**Cluster: "Pakistan-Based Handlers" (8 items, 3 sources)**

> "Cross-border coordination. Hawala channels funding smuggling operations.
> Pakistan-based handlers using encrypted apps — the system extracted
> phone numbers and Telegram handles from unstructured intelligence."

**TRANSITION LINE:**

> "Sir, four clusters — one pipeline. Afghanistan to Punjab border to
> Gujarat ports to Mumbai streets. The system traced the entire supply
> chain from 80 open-source items across 15 sources. That's what it
> does — turns volume into intelligence."

**PAUSE.** 3 seconds.

---

### BEAT 4 — SYNTHETIC DRUGS: DARK WEB + TELEGRAM (2 min)

8. Navigate back to Topics → Click **Synthetic Drug Networks**
9. Switch to Cluster View

**SAY:**

> "Now the synthetic angle — mephedrone, MDMA, LSD. Different supply
> chain, different sources."

**Cluster: "Gujarat Mephedrone Labs" (10 items, 4 sources)**

> "Gujarat mephedrone lab detections from 4 independent sources — NCB
> zonal reports, news coverage, Telegram vendor channels, dark web
> listings advertising 'Gujarat MD'. The system connected a dark web
> listing to a Telegram vendor channel to an NCB seizure report.
> Same product, same origin, three different intelligence planes."

**Cluster: "Dark Web Vendor Migration" (8 items, 3 sources)**

> "Telegram vendors changing handles after enforcement action. The system
> tracked identity persistence through shared phone numbers. A vendor
> operating as @maal_786 went dark, resurfaced as @ncr_drops_new —
> the system linked them through the same phone number appearing in
> both channel descriptions."

> "That's identity persistence across channel changes. No officer
> searched for this. The machine connected the digital footprints."

---

### BEAT 5 — IDENTIFIER INTELLIGENCE — RETELLABLE MOMENT (3 min)

**THIS IS THE KILLER DEMO MOMENT.**

10. Click **Identifiers** tab in workspace sidebar
11. Show cross-topic identifiers

**SAY:**

> "Now this is where Anveshak does something no manual process can do."

12. Show phone number `+91-98765-44444` — highlight that it appears across topics

> "This phone number — 98765-44444.
>
> It appeared first in a Telegram post about a Punjab border handler
> coordinating drone drops — that's Topic 1, Golden Crescent.
>
> Then the same number surfaced in a dark web mephedrone listing with
> a Gujarat contact — that's Topic 2, Synthetic Drugs.
>
> Then again in a Coast Guard interception report — a sat phone intercept
> from a fishing vessel off the Konkan coast — that's Topic 3, Maritime.
>
> Three different operations. Three different topics. Three different
> intelligence streams. The system linked them automatically.
>
> Same handler operating across heroin pipeline, synthetic drug networks,
> AND maritime smuggling. That's cross-domain intelligence from open
> sources. No analyst would have connected these — they sit in three
> different case files."

**PAUSE.** Let that land.

13. Show crypto wallet cross-topic convergence

> "Same pattern here. A Bitcoin wallet address appeared in a dark web
> drug listing AND in a hawala network tip linked to the Golden Crescent
> pipeline. Two operations, one financial node."

14. Show Telegram handle cross-topic convergence

> "And this Telegram handle — appeared in both the synthetic drug vendor
> network and the Punjab border handler communications. The system
> flagged all three convergences automatically."

**THIS IS THE RETELLABLE MOMENT:**

> "You give the system 15 sources across three operations. It gives you
> back: the same phone number operating across heroin, synthetics, and
> maritime smuggling. The same crypto wallet linking dark web to hawala.
> The same Telegram handle bridging two networks. Cross-domain
> intelligence that would take weeks of manual correlation — assembled
> automatically from open sources."

---

### BEAT 6 — MARITIME TOPIC (1.5 min)

15. Navigate back to Topics → Click **Maritime Drug Interdiction**
16. Quick scroll through content feed

**SAY:**

> "Quick look at the maritime picture — 40 items from 10 sources.
> Coast Guard ops, Indian Navy intelligence, fishing vessel intercepts
> off the Konkan and Kerala coasts, Mundra port container scanning
> intelligence, Sri Lankan Navy coordination reports."

17. Switch to Cluster View — point at 2-3 clusters without deep-diving

> "Makran coast origin tracking. Gujarat landfall patterns. Kerala coast
> emerging as alternate route. The system built the maritime intelligence
> picture from Coast Guard releases, news, and Telegram simultaneously."

> "This shows breadth of coverage. Three operations, three different
> theatres — all monitored from one machine."

---

### BEAT 7 — SIGNALS (1 min)

18. Click **Signals** in sidebar
19. Show signal count (8-10 signals)

**SAY:**

> "8 signals fired automatically across all three topics."

20. Point at key signals:
    - "Golden Crescent corridor — confirmed by 5 independent sources" → HIGH
    - "Cross-topic identifier convergence — phone number across 3 operations" → CRITICAL
    - "Gujarat mephedrone lab activity — 4 sources" → HIGH

> "The CRITICAL signal — cross-topic identifier convergence. The system
> detected that the same handler is operating across your Golden Crescent
> pipeline AND synthetic drug networks AND maritime smuggling. That signal
> fired automatically when the third source confirmed the phone number.
> No analyst triggered it. The machine correlated across operations."

---

### BEAT 8 — REPORT + PDF (1.5 min)

21. Show pre-generated report on Golden Crescent topic
22. Show PDF structure

**SAY:**

> "AI-generated intelligence brief. Every claim cites a source. Every source
> has a credibility score frozen at generation time. The report is immutable —
> once generated, never modified. If a source is later downgraded, the system
> adds a warning — the report itself stays untouched.
>
> NDPS-ready evidence chain. Source citations with timestamps. Credibility
> audit trail. Immutable reports. Section 63 of the Bharatiya Sakshya
> Adhiniyam — electronic evidence admissibility requirements met."

23. Hand over printed case study

> "This documents what the system found across 45 days of automated
> collection. Three operations, 180 items, cross-domain identifier
> convergence, supply chain mapping — all from open sources, all sovereign."

---

### BEAT 9 — THE CLOSE (2 min, no clicks)

Close laptop halfway. Conversation mode.

**SAY:**

> "Sir, what you saw is three operations running simultaneously:
>
> **Golden Crescent Pipeline:** Afghanistan to Mumbai — entry via Punjab
>   border, maritime via Gujarat, distribution through Mumbai. Entire
>   supply chain traced from 80 open-source items across 15 sources.
>
> **Synthetic Drug Networks:** Dark web to street — Gujarat mephedrone
>   labs detected, vendor identity persistence tracked across Telegram
>   channel changes, dark web listings correlated with seizure reports.
>
> **Maritime Interdiction:** Coast Guard ops, fishing vessel intercepts,
>   Mundra port intelligence, alternate route detection along Kerala coast.
>
> And the cross-domain convergence — the same phone number, crypto wallet,
> and Telegram handle operating across all three operations. That's
> intelligence no single case file would produce.
>
> One machine. No cloud. No data leaves your network. Sovereign.
> Built under iDEX ADITI 4.0.
>
> Rs 25 lakh per year for a single analyst workstation. For a zonal
> deployment — 4 to 6 seats — Rs 80 lakh. National HQ deployment
> custom-priced to your requirements.
>
> We can have this running on your zonal office hardware within a week."

**THEN SHUT UP.**

---

## READY ANSWERS

---

**Q: "NDPS Court admissibility?"**

SHORT: "Reports are immutable — once generated, never modified. Full audit trail
on every credibility score change. Source citations with timestamps frozen at
generation time. Meets Section 63 of the Bharatiya Sakshya Adhiniyam requirements
for electronic evidence. The system produces the evidence chain — your officers
produce the certificate under Section 65B."

---

**Q: "Identity persistence when dealers change channels?"**

SHORT: "Engine C extracts phone numbers, Telegram handles, crypto wallets, UPI IDs
from unstructured text. When a vendor closes one Telegram channel and opens another,
the system links them through shared identifiers — same phone number, same wallet.
The identity persists even when the channel name changes."

---

**Q: "Dark web — is it legal?"**

SHORT: "Public onion search engines only. Same as using Tor browser for
open-source research. No marketplace accounts. No purchases. No infiltration.
No entrapment. Passive collection from publicly accessible pages."

---

**Q: "Crypto tracing?"**

SHORT: "The system extracts wallet addresses from content and links them across
sources. If the same Bitcoin wallet appears in a dark web listing and a hawala
tip, the system connects them. It's cross-source linking of identifiers — not
blockchain analysis. For on-chain tracing, you'd use Chainalysis or Crystal.
Anveshak tells you WHICH wallets to trace."

---

**Q: "Integration with NARCOS portal?"**

SHORT: "API-first architecture. REST API for all data. PDF and CSV export for
reports. Custom connector can be built for NARCOS integration. No direct
connector today — happy to build for a committed deployment."

---

**Q: "Coast Guard / DRI coordination?"**

SHORT: "Separate topics for separate operations — but the system detects when
identifiers converge across topics. That cross-topic convergence signal is
exactly what surfaced the phone number operating across three operations.
Coast Guard feeds go into maritime topic, DRI feeds into Golden Crescent —
the system finds the connections automatically."

---

**Q: "Can it track precursor chemical networks?"**

SHORT: "Absolutely. Set up a topic for precursor chemicals — monitor chemical
trade publications, customs data feeds, Telegram channels, dark web listings.
The identifier intelligence engine extracts company names, phone numbers,
shipping references. Same cross-source linking. Ephedrine shipment from
Gujarat linked to a mephedrone lab via shared phone number — the system
would surface that."

---

**Q: "WhatsApp monitoring?"**

SHORT: "WhatsApp connector is built and tested. Analyst scans QR code from
their phone, system auto-ingests group messages. Same sovereign approach —
everything on your hardware. Useful for monitoring known drug trafficking
groups with proper authorisation."

---

**Q: "Who else uses this?"**

SHORT: "Defence forces — IAF uses it for air intelligence and information
warfare monitoring. Police across multiple states for narcotics and cyber
crime intelligence. You'd be the first national-level LEA deployment.
That means direct input into the product roadmap — your requirements
shape the platform."

Frame "first national LEA" as advantage (shapes product), not risk.

---

**Q: "Accuracy of identifier extraction?"**

SHORT: "Regex plus NLP hybrid. Approximately 80% accuracy on phone numbers
and Telegram handles. The system shows confidence scores — analyst validates
before action. It surfaces candidates, never makes enforcement decisions.
Think of it as automated triage — the machine reads 10,000 messages and
hands you the 50 phone numbers worth checking."

---

**Q: "Price for zonal deployment?"**

SHORT: "Single analyst workstation: Rs 25 lakh per year. Zonal office
deployment — 4 to 6 seats: Rs 80 lakh per year. National HQ deployment:
custom pricing based on number of analysts, topics, and source volume.
All include setup, training, and 12-month support."

---

**Q: "Send us a proposal"**

This is GOOD. Say: "Absolutely, sir. Technical proposal with deployment
specifications and pricing by [day after tomorrow]. Would it help to
schedule a follow-up with your intelligence officers to identify the
priority operations — which zones, which pipelines, which source feeds
they'd want to monitor first?"

Creates urgency + second meeting with working-level officers.

---

**Q: "Can it handle Punjabi/Urdu content?"**

SHORT: "Full multilingual support. NLLB-200 translation model handles Hindi,
Punjabi, Urdu, Arabic — 200 languages total. All on-device. No cloud
translation service. Drug trafficking intelligence in Punjabi from border
areas is translated and processed automatically."

---

**Q: "What about call detail records / CDR analysis?"**

SHORT: "Anveshak is an OSINT platform — it works with open-source and
publicly accessible data. CDR analysis is a different capability requiring
legal authorisation. What Anveshak does is tell you WHICH phone numbers
to request CDRs for — the system surfaces the numbers from open sources,
your officers take the legal route."

---

## WHAT TO ABSOLUTELY AVOID

| Don't | Why |
|-------|-----|
| Don't explain embeddings, vectors, cosine similarity | They care about output, not engine |
| Don't say "AI" more than 3 times total | Say "the system" or "the platform" |
| Don't demo creating a topic live | Things can break. Show what works |
| Don't show other org's data (IAF, Haryana, Telangana) | Different org, different audience. Org isolation if asked |
| Don't promise blockchain analysis | Wallet extraction yes, on-chain tracing no |
| Don't oversell dark web coverage | Public pages only, no marketplace infiltration |
| Don't mention specific informant networks | Stick to open-source intelligence |
| Don't oversell deepfake detection accuracy | Say "probability score" not "detection" |
| Don't compare to NARCOS portal | Complementary, not competitive |
| Don't let demo exceed 18 minutes | NCB officers are busy. Respect time |
| Don't demo WhatsApp bridge live | Mention as capability, don't show |
| Don't scroll to raw entity tables | NER noise visible in live UI — PDF is filtered |

---

## IF LIVE DEMO FAILS

1. **Containers crashed:** Use pre-taken screenshots of every beat
2. **Report generation hangs:** Show existing report — "generated earlier, same data"
3. **Cluster view empty:** Fall back to content feed + manual scrolling through items
4. **Cross-topic identifiers not showing:** Describe the convergence verbally — "in the full deployment, the system linked..."
5. **Login fails:** Have password on paper: `AnveshakDemo2024!`
6. **Page loads slowly:** Fill silence — "System monitoring 37 sources across three operations in real-time"

---

## DEMO FLOW: WHICH TOPIC FIRST?

**Default order (recommended):**
1. Golden Crescent (strongest — most items, most clusters, supply chain wow factor)
2. Synthetic Drugs (dark web + identity persistence — unique differentiator)
3. Maritime Interdiction (brief — shows breadth of coverage)

**If audience is dark web / cyber focused:** Lead with Synthetic Drugs
**If audience is Coast Guard liaison / maritime ops:** Lead with Maritime first
**If audience is border / BSF coordination:** Lead with Golden Crescent, emphasise Punjab corridor
**If audience is DDG-level strategic:** Lead with all three briefly, then deep-dive Golden Crescent + cross-topic convergence

---

## THE ONE THING

**The NCB officer will evaluate Anveshak in the 30 seconds they describe it to their DDG.**

Make those 30 seconds easy:

> "There's this iDEX platform — runs on our own hardware, no cloud —
> it monitors dark web, Telegram, news, DRI, Coast Guard feeds simultaneously.
> Found the same phone number across a dark web drug listing, a Punjab border
> handler tip, and a Coast Guard intercept — linked them automatically across
> three separate operations. Tracks when dealers change Telegram channels.
> Generates NDPS-ready intelligence briefs. Rs 25 lakh per year per workstation."

That's your demo. Everything else is scaffolding.
