# ANVESHAK DEMO — NAGALAND POLICE (DIG)

**Audience:** DIG, Nagaland Police
**Duration:** 12-15 minutes
**Objective:** DIG walks out with ONE retellable story for DGP + agrees to a 30-day pilot
**Primary concern:** Drug trafficking, social media monitoring across Nagaland
**Your edge:** Already in Nagaland (Cognecto with PWD/PMGSY), Grosint used by police across India

---

## PRE-DEMO CHECKLIST (30 min before)

```
□ make ps                                    — all containers green
□ curl localhost:11434/api/tags              — qwen2:7b loaded
□ http://localhost:3000                      — frontend accessible
□ Login as demo_cyber@anveshak.local         — verify topic loads
□ Navigate to Nagaland topic, verify content — 3,300+ items visible
□ Check Signals tab has entries              — 50 signals visible
□ Pre-generate one report (if not done)      — so you can show instantly
□ Browser: dark mode, full screen, no bookmarks bar
□ Close Slack, email, all notifications
□ Phone on silent
```

---

## THE DEMO

---

### BEAT 0 — BEFORE THE SCREEN (2 min)

Do NOT open the laptop yet. Stand or sit facing the DIG. Make eye contact.

**SAY:**

> "Sir, thank you for making the time. Before I show you anything —
>
> We're already working in Nagaland. Cognecto is deployed with Nagaland PWD
> and PMGSY. And Grosint — our OSINT tool — is being used by police officers
> across multiple states in India.
>
> Anveshak is our AI intelligence platform. Built under iDEX ADITI for defence,
> now adapted for law enforcement. What I'm about to show you is not a
> presentation — it's a live system monitoring Nagaland social media right now.
>
> We loaded your local sources — Nagaland Tribune, Eastern Mirror, Morung Express,
> HornbillTV, local Telegram channels — and let the system run. Let me show you
> what it found on its own."

**WHY THIS WORKS:**
- "Already in Nagaland" — you're not an outsider [L1-Coalition: in-tribe]
- "Police across India" — peer validation [L3-Status: relative position]
- "iDEX ADITI" — government-vetted, not random startup [L2-Signaling: costly signal]
- "Let me show what it found on its own" — creates curiosity, not a feature list

**PAUSE.** Let him react. If he nods or says "show me" — open the laptop.

---

### BEAT 1 — LOGIN (30 sec)

1. Open http://localhost:3000
2. Point at the login screen briefly:
   - "For Official Use Only" classification bar
   - अन्वेषक — "the seeker" in Devanagari
3. Login: `demo_cyber@anveshak.local`
4. Land on Topics Dashboard

**SAY:**

> "This is the analyst workbench. One topic per mission. Right now we have
> one topic running — Nagaland Social Media Monitoring. Your cyber cell could
> have five running simultaneously — drugs, border, unrest, each independent."

**DO NOT** linger on the dashboard. Click into the topic immediately.

---

### BEAT 2 — THE CONTENT FEED (2 min)

5. Click **"Nagaland Social Media Monitoring"** → Content Feed opens
6. Scroll slowly. Let him SEE the volume.

**SAY (while scrolling):**

> "3,300 items collected. 17 sources. Nagaland Tribune, Eastern Mirror,
> Morung Express, HornbillTV, Voice of Nagaland News, local Telegram channels.
> The system has been running for a few days — this is what it crawled
> automatically."

7. Point at specific cards as you scroll:
   - A YouTube item from HornbillTV or Nagaland News Network
   - An RSS item from Morung Express or Eastern Mirror
   - A Telegram item (if visible)

> "See the platform badges — YouTube, RSS, Telegram. Every item has a
> timestamp showing when it was captured. This runs 24/7 without any
> officer touching it."

8. **Point at a credibility score** on a card:

> "Every item carries the credibility of its source. Eastern Mirror scores
> higher than an anonymous Telegram channel. The analyst sees this at a
> glance — no guesswork."

**DO NOT** explain how scraping works. DO NOT mention Crawl4AI, embeddings, or NLP.

---

### BEAT 3 — CLUSTER VIEW (2.5 min) — THE CORE DEMO

9. **Switch to Cluster View**

**SAY:**

> "Now this is where it gets interesting. The AI reads every article and
> groups them by narrative — which stories are related."

10. Point out clusters. Walk through them top to bottom:

**Cluster: "Nagaland Production Ban & Health System Critique" (15 items, 6 sources)**

> "15 items from 6 independent sources — citizens calling for a ban on
> non-local production AND criticizing the healthcare system. Two separate
> issues, but the system linked them because the same people are talking
> about both on social media. That's a sentiment pattern."

**Cluster: "Nagaland Identity Disparagement" (10 items, 6 sources)**

> "A journalist used offensive terminology about Naga people — the term
> 'kacha Naga.' The system detected 10 posts across 6 sources reacting to
> this. That's a communal tension signal building up. Your cyber cell would
> want to watch this."

**Cluster: "Nagaland Tobacco Ban Impact" (9 items, 3 sources)**

> "The tobacco ban. 9 items — shopkeepers in Dimapur confused about what's
> actually banned, prices doubling, public frustration. Three independent
> sources picked this up. The system clustered it automatically."

**Cluster: "Wokha Town Drug Problem Response" (2 items, 2 sources)**

> "And here's the drug angle. Wokha town — citizens calling for strict
> community action against drug users and destruction of property. Two
> independent sources. This is a forming narrative — it's small now, but
> the system is tracking it. With more sources — the Telegram channels
> your officers actually monitor — this grows fast."

**THIS IS YOUR TRANSITION LINE:**

> "Sir, nobody searched for any of this. Nobody typed a keyword. The system
> read 3,300 items, grouped them into narratives, and told you: here are the
> stories forming in your state right now."

**PAUSE.** Let that land. 3 seconds of silence.

---

### BEAT 4 — SIGNALS (1.5 min)

11. Click **Signals** in sidebar
12. Show the badge count (50 signals)

**SAY:**

> "When multiple independent sources report the same narrative, the system
> fires a signal. 50 signals generated automatically."

13. Point at a specific signal:
    - **"Healthcare Staff Shortage in Nagaland — confirmed by 6 independent sources"**

> "Six independent sources — newspapers, YouTube channels, social media —
> all talking about healthcare staffing problems. This isn't one person
> complaining. This is a verified pattern. The system tells your analyst:
> pay attention to this."

14. Point at another:
    - **"Nagaland Tobacco Ban Concerns — 3 independent sources"**

> "Tobacco ban confusion — 3 sources. If this grows to 5 or 6, it could
> become a law and order situation in Dimapur. The system is watching."

15. **Acknowledge** one signal (click). **Dismiss** another (click).

> "Every signal is triaged by the analyst. Acknowledged, dismissed, or
> escalated. Full audit trail — who saw it, when, what action."

**DO NOT** explain ISC (independent source count) in technical terms.
Say "independent sources" — the DIG understands that language.

---

### BEAT 5 — IDENTIFIER INTELLIGENCE (1.5 min)

16. Navigate to **Identifier Clusters** (if available in workspace tab)

**SAY:**

> "The system doesn't just read text. It extracts phone numbers, Telegram
> handles, and links them across sources."

17. Show the real phone number `8413899928`:

> "This phone number was extracted from 2 different news sources — it appeared
> in content about the Inner Line Regulation consultation meeting in Dimapur.
> The system linked it automatically."

18. Frame the capability, not this specific result:

> "Now imagine this with the Telegram channels your cyber cell actually
> monitors. A phone number appears in a drug discussion on one channel, then
> in a transaction post on another channel, then in a recruitment message
> on a third. The system connects those dots. No officer searched for it —
> the machine linked it."

**THIS IS THE RETELLABLE MOMENT.** If the DIG remembers one thing, it should be:
"The system finds phone numbers across channels automatically."

**DO NOT** say this is dummy data. Everything you showed is REAL scraped data.
The phone number is real. The mechanism is real. Frame the drug use case
as what happens when HIS sources are added.

---

### BEAT 6 — SOURCE CREDIBILITY (1 min)

19. Click **Sources** in sidebar
20. Show the list — credibility bars, health indicators

**SAY:**

> "Every source has a credibility score. Eastern Mirror: 82. An anonymous
> Telegram channel: 35. The system auto-adjusts — if a source's reports
> are confirmed by other independent sources, score goes up. If it publishes
> noise, score drops."

21. Click on one source → show audit log tab

> "Every credibility change is logged. Timestamp, old score, new score,
> reason. Immutable. Nobody can silently change a source's trustworthiness.
> When a report cites this source, the credibility at that exact moment
> is frozen into the report."

**DO NOT** demo a credibility update manually. Just show the audit trail exists.

---

### BEAT 7 — REPORT (1.5 min)

22. Click **Reports** in sidebar
23. Show the existing report (or generate live if confident in timing)

**SAY:**

> "This is the output. An AI-generated intelligence brief."

24. Show:
    - Markdown-rendered report with source citations
    - Confidence score
    - **PDF download button**

> "Every claim cites a source. Every source has a credibility score.
> The report is generated by an AI running on THIS machine — qwen2,
> a 7-billion parameter model running locally via Ollama. No data leaves
> this deployment. No cloud API. Fully sovereign."

25. Click PDF download

> "This is what goes up the chain. Your SP or DIG gets a structured,
> sourced intelligence brief — not a verbal summary from memory."

**SAY (only if report was generated live):**

> "That took about 30 seconds. An analyst writing this manually — an hour?"

---

### BEAT 8 — THE CLOSE (1.5 min, no clicks)

Close the laptop lid halfway or lean back. Signal: demo is over, conversation begins.

**SAY:**

> "Sir, what you saw is the full cycle — automated:
>
> **Collect** — 17 sources, 3,300 items, running 24/7
> **Cluster** — AI grouped narratives: drug concerns, tobacco ban confusion,
>   identity tensions, healthcare frustration, insurgent activity
> **Alert** — 50 signals fired. Healthcare crisis across 6 sources.
>   Tobacco ban across 3. Drug problem forming in Wokha.
> **Link** — Phone numbers and Telegram handles extracted and connected
>   across sources automatically
> **Report** — AI-generated, source-grounded, auditable, PDF-ready
>
> All on one machine. No cloud. No data leaves your network.
>
> For 6-8 workstations with full capability — ₹22 lakh per year.
> We can have it running on your hardware within a week."

**THEN SHUT UP.**

Let the DIG speak. Whatever he says next tells you exactly where he is.

---

## READY ANSWERS

Read these. Memorize the short version. Long version is backup.

---

**Q: "Can it monitor WhatsApp?"**

SHORT: "Yes. Next release. Baileys bridge — analyst scans QR from phone,
system auto-ingests group messages. Same sovereign approach."

LONG: "We have the architecture built — a self-hosted WhatsApp Web bridge
using Baileys. It runs as a Docker sidecar. The analyst pairs their phone
via QR code, and the system automatically ingests all group messages.
No Meta Business API, no cloud callbacks. Everything stays on your hardware.
It's the same sovereign approach as everything else — just the next module
to deploy."

---

**Q: "Can it monitor Instagram?"**

SHORT: "Yes. Instagram adapter is live. Profile monitoring and hashtag search."

LONG: "The Instagram adapter is built and deployed. It monitors profiles —
fetches recent posts from registered handles — and searches by hashtag.
It uses conservative rate limits because Meta's API is strict. We already
have Nagaland Instagram sources configured."

---

**Q: "What about Facebook?"**

SHORT: "Facebook requires official law enforcement access via Meta's LEA portal.
Once you have that, we integrate. The adapter pattern is the same."

---

**Q: "Is data stored on our servers?"**

SHORT: "Everything. PostgreSQL database, AI models, Ollama LLM — all on your
hardware. Zero cloud dependency. Air-gap deployable."

---

**Q: "What languages?"**

SHORT: "Hindi, English, plus 200 languages via NLLB translation model. All
translated on-device."

LONG: "The translation model — NLLB-200 from Meta — supports 200 languages.
Currently configured for Hindi, Chinese, Arabic, Urdu to English. Nagamese
content written in Hindi script works. Adding a language is a config change."

---

**Q: "Can we add our own sources?"**

SHORT: "30 seconds. Add any RSS feed, Telegram channel, YouTube channel, or
web URL. System starts monitoring on the next poll cycle — 15 minutes."

---

**Q: "How many sources can it handle?"**

SHORT: "Tested with 17 running now. Architecturally — hundreds. Scraping is
async, add more worker containers to scale horizontally."

---

**Q: "Cost?"**

SHORT: "₹22 lakh per year for 6-8 workstations, full capability. Includes
setup, training, and support. Less than one Inspector's annual CTC — and
it works 24/7."

If he negotiates: "For Nagaland, given our existing relationship with PWD,
we can do ₹18 lakh for the first year."

Floor: ₹18L. Below that, reduce workstations (6 instead of 8).

---

**Q: "How is this different from what we do manually?"**

SHORT: "Your officer reads 50 posts a day. This read 3,300 in a few days.
It found a phone number across 2 news sources automatically. It detected
6 independent sources discussing healthcare failures — no officer searched
for that. The system sees patterns a human can't at this scale."

---

**Q: "Can different units use this for different missions?"**

SHORT: "Yes. Each topic is an independent workspace — own sources, own keywords,
own signals, own reports. Cyber cell runs drug monitoring. Intelligence runs
insurgent tracking. Same deployment, isolated workspaces."

---

**Q: "What if the LLM is slow on CPU?"**

SHORT: "Works on CPU — you saw the report generate. Drop in a GPU, change one
environment variable. No code changes. We have the full hardware upgrade
matrix documented."

---

**Q: "Who else is using this?"**

SHORT: "Grosint is used by police officers across multiple states. Anveshak
is built for deeper AI-driven analysis. You'd be among the first law
enforcement deployments of Anveshak — which means direct input into the
product roadmap."

Frame "first" as an advantage (shapes the product), not a risk.

---

**Q: "Can it detect fake news / deepfakes?"**

SHORT: "Yes. Image analysis module — deepfake probability scoring, object
detection via YOLO, EXIF metadata forensics. Happy to show that separately."

Only demo vision if he explicitly asks. It's not his priority today.

---

**Q: "What about data security / classification?"**

SHORT: "Every item carries a classification label. Labels are mandatory in
every data model — not optional. Source credibility is audited. Reports
are immutable snapshots. And everything runs on your hardware — no
external data flow."

---

**Q: "Send me a proposal"**

This is GOOD. Say: "Absolutely, sir. We'll send a proposal with pilot scope
by [day after tomorrow]. Could we also schedule a brief session with your
cyber cell team to identify the specific sources and topics they'd want
to monitor?"

This does two things: creates urgency (specific date) and gives you a
second meeting with the working-level officers who become daily users.

---

**Q: "Let me check with DGP"**

This is EXPECTED. Say: "Of course, sir. Would it help if we did a brief
joint presentation for the DGP? We can tailor it to his priorities —
happy to come back."

DO NOT let him be the sole messenger. The demo degrades in retelling.

---

## WHAT TO ABSOLUTELY AVOID

| Don't | Why |
|-------|-----|
| Don't explain embeddings, vectors, cosine similarity | He doesn't care about the engine, only the output |
| Don't say "AI" more than 3 times total | Say "the system." AI sounds like marketing |
| Don't show dummy/seed data as if it's real | If caught, total trust collapse. Everything you show IS real |
| Don't demo semantic search unless asked | Engineers love it, police officers don't care |
| Don't demo vision/deepfake unless asked | Not his problem today. Keep in back pocket |
| Don't give pricing in this meeting | "After the pilot" keeps the door open |
| Don't apologize for anything being "early" | You're showing a WORKING system. Confidence |
| Don't demo creating a new topic live | Too risky. Things can break. Show the one that works |
| Don't read from notes during the demo | Practice 3 times. Know the flow cold |
| Don't let the demo go past 15 minutes | Respect his time. A DIG who wants more will ask |

---

## PRACTICE CHECKLIST

Run through this 3 times before the meeting:

```
□ Run 1: Full demo with script open. Time yourself. Target: 12 min
□ Run 2: Demo with script closed. Note where you hesitate
□ Run 3: Demo with a colleague playing DIG asking hard questions
□ Verify: every click works, every page loads, report exists
□ Backup: screenshot every key screen in case live demo fails
```

---

## IF LIVE DEMO FAILS

Technology fails. Have a plan:

1. **Internet down / containers crashed:** Use screenshots (take them now)
2. **Report generation hangs:** Show the existing report, say "let me show one
   we generated earlier — same content"
3. **Page loads slowly:** Fill the silence: "The system is running 17 sources
   in real-time on this machine — processing power is shared"
4. **Login fails:** Have the password written down separately. Don't type it
   wrong in front of a DIG.

---

## THE ONE THING

If you remember nothing else from this script:

**The DIG will evaluate Anveshak in the 30 seconds he describes it to DGP.**

Make those 30 seconds easy:

> "There's this system — already being used by police in other states,
> the company is already in Nagaland with PWD — it monitors social media
> automatically. It found a healthcare crisis across 6 sources, drug
> concerns forming in Wokha, and it extracts phone numbers from Telegram
> channels and links them across posts. Everything runs on our own
> hardware. No cloud."

That's your demo. Everything else is scaffolding.
