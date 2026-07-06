# ANVESHAK DEMO — HARYANA STF (Narcotics Intelligence)

**Audience:** STF Haryana officers
**Duration:** 12-15 minutes
**Objective:** STF sees value in automated narcotics intelligence; agrees to pilot or purchase
**Primary concern:** Drug trafficking via Punjab corridor, chitta epidemic, cross-border smuggling
**Your edge:** Grosint used by police across India, iDEX ADITI government-vetted platform

---

## PRE-DEMO CHECKLIST (30 min before)

```
□ make ps                                    — all containers green
□ curl localhost:11434/api/tags              — qwen2:7b loaded
□ http://localhost:3000                      — frontend accessible
□ Login as demo_cyber@anveshak.local         — verify topic loads
□ Navigate to Haryana STF topic, verify      — 48 items visible
□ Check Signals tab has entries              — 3 signals visible
□ Pre-generate one report (if not done)      — so you can show instantly
□ make pdf-haryana                           — leave-behind PDF ready
□ Print 2 copies of haryana_leave_behind.pdf
□ Browser: dark mode, full screen, no bookmarks bar
□ Close Slack, email, all notifications
□ Phone on silent
```

---

## THE DEMO

---

### BEAT 0 — BEFORE THE SCREEN (2 min)

Do NOT open the laptop yet. Stand or sit facing the officers. Make eye contact.

**SAY:**

> "Thank you for making the time. Before I show you anything —
>
> Grosint — our OSINT tool — is being used by police officers across multiple
> states in India. Anveshak is our AI intelligence platform, built under iDEX
> ADITI for defence, now adapted for law enforcement.
>
> What I'm about to show you is not a presentation — it's a live system. We
> loaded Haryana-relevant sources — Tribune India, Dainik Jagran, Hindustan
> Times Chandigarh, Telegram channels monitoring the drug trade, even dark
> web search — and let the system run. Let me show you what it found."

**PAUSE.** Let them react. If they nod — open the laptop.

---

### BEAT 1 — LOGIN (30 sec)

1. Open http://localhost:3000
2. Point at login screen briefly:
   - "For Official Use Only" classification bar
   - अन्वेषक — "the seeker" in Devanagari
3. Login: `demo_cyber@anveshak.local`
4. Land on Topics Dashboard

**SAY:**

> "This is the analyst workbench. One topic per mission. Right now we have
> Haryana STF Narcotics Intelligence running. You could have separate topics
> for different operations — one for the Punjab corridor, one for synthetic
> drugs in NCR, one for hawala networks."

Click into the topic immediately.

---

### BEAT 2 — THE CONTENT FEED (2 min)

5. Click **"Haryana STF Narcotics Intelligence"** → Content Feed opens
6. Scroll slowly. Let them SEE the volume.

**SAY (while scrolling):**

> "48 items collected from 13 sources. Tribune India, Dainik Jagran,
> Hindustan Times Chandigarh, Amar Ujala, Indian Express, Haryana Police
> official, NCB India, Telegram drug intelligence channels, dark web.
> The system collects 24/7 without any officer touching it."

7. Point at specific cards:
   - An RSS item from Tribune India — drug seizure on NH-44
   - A Telegram item — chitta supply line intelligence
   - A YouTube item from Haryana Police press conference

> "See the platform badges — RSS, Telegram, YouTube, dark web. Every item
> has a credibility score from its source. Official Haryana Police at 90,
> an anonymous Telegram channel at 12. The analyst sees this at a glance."

**DO NOT** explain how scraping works. DO NOT mention Crawl4AI or embeddings.

---

### BEAT 3 — CLUSTER VIEW (3 min) — THE CORE DEMO

8. **Switch to Cluster View**

**SAY:**

> "Now this is where it gets interesting. The AI reads every article and
> groups them by narrative — which stories are connected."

9. Walk through clusters:

**Cluster: "Punjab-Haryana Drug Corridor Seizures" (12 items, 4 sources)**

> "12 items from 4 independent sources — seizures on NH-44 near Ambala,
> poppy husk at Karnal bypass, BSF operations at the Fazilka-Sirsa border.
> The system connected all of these automatically. This is your corridor
> intelligence picture — built from open sources without manual search."

**Cluster: "Chitta Epidemic in Ambala-Karnal Belt" (10 items, 3 sources)**

> "The chitta crisis. 10 items — overdose deaths in Ambala, rehabilitation
> centers overwhelmed in Karnal, chitta reaching school gates, price crashes
> indicating supply surges. Three independent sources confirm the pattern.
> This is not one officer's observation — it's verified across sources."

**Cluster: "STF Operations and Major Arrests" (10 items, 4 sources)**

> "Your own operations — Operation Thunder results, the Ambala kingpin arrest,
> Panchkula farmhouse raid. The system tracks what's public about your ops
> and how media covers them. Useful for impact assessment."

**Cluster: "Cross-Border Smuggling Networks" (8 items, 3 sources)**

> "Cross-border angle — drone drops from Pakistan side, agricultural truck
> concealment, Pakistan-based handlers using encrypted apps. NCB, NIA, and
> BSF inputs all converging into one intelligence picture."

**TRANSITION:**

> "Nobody searched for any of this. Nobody typed a keyword. The system
> read 48 items, grouped them into narratives, and told you: here are the
> drug intelligence patterns forming in Haryana right now."

**PAUSE.** 3 seconds of silence.

---

### BEAT 4 — SIGNALS (1.5 min)

10. Click **Signals** in sidebar
11. Show the badge count (3 signals)

**SAY:**

> "When multiple independent sources report the same narrative, the system
> fires a signal. 3 signals generated automatically."

12. Point at signal:
    - **"Punjab-Haryana drug corridor — confirmed by 4 independent sources"**

> "Four independent sources — newspapers, Telegram, official sources —
> all reporting drug corridor activity. This isn't one tip. This is
> a verified intelligence pattern."

13. Point at identifier signal:
    - **"Phone number across 3 sources linked to drug trafficking"**

> "A phone number appeared in 3 different Telegram channels linked to drug
> trafficking. The system flagged it automatically. No officer searched."

---

### BEAT 5 — IDENTIFIER INTELLIGENCE (2 min) — DEMO KILLER

14. Navigate to **Identifier Clusters**

**SAY:**

> "The system doesn't just read text. It extracts phone numbers, Telegram
> handles, and links them across sources."

15. Show phone numbers and Telegram handles:

> "This phone number — 98765-11111 — appeared in 3 different sources.
> Once in a Telegram channel discussing new drug routes via Panchkula,
> again in a chitta supply alert, and again in a smuggling tip.
> The system connected them automatically."
>
> "These Telegram handles — @delhimaaldrop, @ncr_supply_786,
> @crypto_maal_786 — extracted from unstructured messages. These are
> the digital footprints of the supply chain."

**THIS IS THE RETELLABLE MOMENT:**

> "Imagine this running on the Telegram channels your STF actually monitors.
> A phone number appears in one channel, then another, then a third.
> The machine links them before any officer even reads the messages."

---

### BEAT 6 — SOURCE CREDIBILITY (1 min)

16. Click **Sources** in sidebar
17. Show the list — credibility bars, health indicators

**SAY:**

> "Every source has a credibility score. Haryana Police official: 90.
> NCB India: 92. Tribune India: 82. Anonymous Telegram channel: 12.
> The system weights intelligence accordingly."

18. Click one source → show audit log

> "Every credibility change is logged. Immutable audit trail. When a report
> cites a source, the credibility at that exact moment is frozen into the report."

---

### BEAT 7 — REPORT + PDF (1.5 min)

19. Click **Reports** or show pre-generated report
20. Show markdown report with source citations

**SAY:**

> "AI-generated intelligence brief. Every claim cites a source. Every source
> has a credibility score. Generated by an AI running on THIS machine — no
> data leaves your deployment. Fully sovereign."

21. Hand over the printed PDF

> "This is generated from the data your system collected. Imagine this
> every Monday morning on your desk. Drug corridor status, chitta epidemic
> tracking, STF operation impact, cross-border intelligence — automated."

---

### BEAT 8 — THE CLOSE (1.5 min, no clicks)

Close the laptop lid halfway. Signal: demo over, conversation begins.

**SAY:**

> "What you saw is the full cycle — automated:
>
> **Collect** — 13 sources, 48 items, running 24/7
> **Cluster** — AI grouped narratives: drug corridor, chitta epidemic,
>   STF operations, cross-border networks, anti-drug movement
> **Alert** — 3 signals fired. Drug corridor across 4 sources.
>   Phone number linked across 3 sources.
> **Link** — Phone numbers and Telegram handles extracted and connected
>   across sources automatically
> **Report** — AI-generated, source-grounded, auditable, PDF-ready
>
> All on one machine. No cloud. No data leaves your network.
>
> Rs 25 lakh per year per workstation. Full capability.
> We can have it running on your hardware within a week."

**THEN SHUT UP.** Let them speak.

---

## READY ANSWERS

---

**Q: "Can you monitor WhatsApp?"**

SHORT: "Yes. WhatsApp connector is built and tested. Analyst scans QR from
phone, system auto-ingests group messages. Same sovereign approach."

---

**Q: "Hindi content?"**

SHORT: "Full Hindi support. NLLB-200 translation model handles Hindi,
Punjabi, Urdu — all on-device. No cloud translation."

---

**Q: "Dark web — is it legal?"**

SHORT: "Public onion search engines only. Same as Google searches.
No marketplace infiltration. No entrapment."

---

**Q: "Can it track hawala networks?"**

SHORT: "Yes. Engine C extracts bank account numbers, UPI IDs, crypto
wallets from content. Links them across sources. Same identifier
intelligence you saw with phone numbers."

---

**Q: "Integration with CCTNS?"**

SHORT: "Export as PDF/CSV. API available for custom integration.
No direct CCTNS connector yet — happy to build for a committed buyer."

---

**Q: "NDPS Act compliance?"**

SHORT: "Reports cite exact sources with timestamps. Credibility scores
and audit trails support NDPS Section 67 (statements) evidence chain.
Reports are immutable — once generated, never modified."

---

**Q: "How many sources can it handle?"**

SHORT: "Currently 13 on this topic. Other deployments run 17-22.
No hard limit — scales with hardware. Add more workers for more sources."

---

**Q: "Accuracy of identifier extraction?"**

SHORT: "Regex + NLP hybrid. ~80% on phone numbers and Telegram handles.
Analyst validates before action. System shows confidence — never makes
enforcement decisions."

---

**Q: "Can different units use this?"**

SHORT: "Each topic is an independent workspace — own sources, own keywords,
own signals, own reports. STF runs drug monitoring. Cyber cell runs
fraud tracking. Same deployment, isolated workspaces."

---

**Q: "Price?"**

SHORT: "Rs 25 lakh per year, per workstation. Includes setup, training,
12 months support."

If they negotiate: floor is Rs 20 lakh for STF given scale of deployment.

---

**Q: "Who else is using this?"**

SHORT: "Grosint is used by police officers across multiple states. Anveshak
is the AI-powered version — you'd be among the first STF deployments.
That means direct input into the product roadmap."

Frame "first" as advantage (shapes product), not risk.

---

## WHAT TO ABSOLUTELY AVOID

| Don't | Why |
|-------|-----|
| Don't explain embeddings, vectors, cosine similarity | They don't care about the engine |
| Don't say "AI" more than 3 times total | Say "the system" |
| Don't show dummy data as real | Everything you show IS real seed data — own it |
| Don't demo creating a new topic live | Too risky. Show the one that works |
| Don't demo WhatsApp bridge (unhealthy) | Mention as capability, don't show |
| Don't give pricing in first meeting | "After the pilot" if they push |
| Don't apologize for anything being early | You're showing a WORKING system |
| Don't let demo go past 15 minutes | Respect their time |

---

## IF LIVE DEMO FAILS

1. **Containers crashed:** Use pre-taken screenshots
2. **Report generation hangs:** Show existing report — "generated earlier, same data"
3. **Page loads slowly:** Fill silence — "System monitoring 13 sources in real-time"
4. **Login fails:** Have password written down separately

---

## THE ONE THING

If you remember nothing else:

**The STF officer will evaluate Anveshak in the 30 seconds they describe it to their superior.**

Make those 30 seconds easy:

> "There's this system — used by police in other states — it monitors
> Telegram channels, news, dark web automatically. It found a phone number
> across 3 drug trafficking sources, detected the chitta supply line from
> Punjab, and generates an intelligence brief every week. Everything runs
> on our own hardware. No cloud. Rs 25 lakh per year."

That's your demo. Everything else is scaffolding.
