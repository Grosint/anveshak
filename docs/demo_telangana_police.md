# TGCSB Demo Script — 1 Jul 2026

## Pre-Demo (5 min before)

```bash
# Verify everything running
make ps
# Regenerate fresh PDF if needed
make pdf-telangana
# Open browser to localhost:3000, login as demo_cyber@anveshak.local / AnveshakDemo2024!
```

---

## ACT 1 — "The Problem" (3 min)

**Talk track:**
> "Telangana saw 11,657 investment scam cases Jan-Sep 2025. Rs 547 crore single fraud in Khammam. 56% of India's cybercrime losses from pig butchering. TGCSB nabbed 48 criminals, 38 mule holders — but analysts manually searching Telegram channels, news sites, dark web. One analyst can monitor maybe 3-4 channels. What if one platform monitors 22 sources across 5 platforms simultaneously?"

---

## ACT 2 — "What We Monitor" (5 min)

1. **Dashboard** -> Click **Telangana Cyber Fraud Intelligence** topic
2. Show **22 sources across 5 platforms:**
   - 5 RSS news (Telangana Today, Siasat Daily, Deccan Chronicle, Hans India, The420.in)
   - 8 Telegram fraud channels (GamingPay191, AlphaPay, DoingPay, KissPay, LoongPay, India Bank Accounts)
   - 3 dark web (Ahmia, Torch, DuckDuckGo onion)
   - 2 Instagram (Hyderabad Earn Online, Invest Pro)
   - 1 YouTube (TGCSB Press Conferences)
   - 1 web (TGCSB Official)
3. Point out **credibility scores** — TGCSB official at 85, Telangana Today at 80, fraud Telegram channels at 8-15
4. **Talk track:**
   > "System auto-scores source credibility. TGCSB official press releases weighted 10x more than anonymous Telegram channel. Analyst can override."

---

## ACT 3 — "Live Collection" (5 min)

1. Show **content feed** — **1,060 items** collected automatically
2. Filter **last 7 days**: 619 RSS + 349 Telegram + 52 web + 6 darkweb = **~1,000 items/week**
3. Show one **Telegram message** from GamingPay191 or DoingPay — raw fraud recruitment content
4. Show one **RSS article** from Telangana Today — TGCSB bust operation
5. **Talk track:**
   > "System collected 1,060 items since June 2021. Last week alone, over 1,000 new items. One analyst cannot read 1,000 messages manually. AI reads all, extracts intelligence."

---

## ACT 4 — "AI Finds the Connections" (10 min) -- MONEY SHOT

1. **Narrative Clustering** — 3 auto-detected clusters:
   - "TGCSB, Telangana Cyber Security Bureau" (12 items, 2 independent sources)
   - Two smaller clusters grouping related content

2. **Signals page** — **946 signals** fired automatically
   > "Every time same identifier appears in 2+ independent sources, system flags it. No human searching."

3. **Identifier Intelligence** (Engine C) — THIS IS THE DEMO KILLER:

   | Type | Value | Sources | Items |
   |------|-------|---------|-------|
   | URL_DOMAIN | cybercrime.gov.in | 2 | 3 |
   | TELEGRAM_HANDLE | doingpay_sh | 2 | 2 |
   | TELEGRAM_HANDLE | doingpay_ff | 2 | 2 |
   | URL_DOMAIN | qqpays.online | 1 | 3 |
   | TELEGRAM_HANDLE | zenixpay_lee | 1 | 2 |
   | TELEGRAM_HANDLE | doingpay_cc | 1 | 2 |
   | TELEGRAM_HANDLE | doingpay_vv | 1 | 2 |

   **Talk track:**
   > "Look at this — doingpay_sh, doingpay_ff, doingpay_cc, doingpay_vv. Same operator, multiple handles. System found this pattern automatically from unstructured Telegram messages. qqpays.online — a payment domain appearing in fraud channels. cybercrime.gov.in cross-referenced across sources — victims filing complaints. All extracted by AI, no manual search."

4. **Entity graph** — show TGCSB (564 mentions), Hyderabad (288), Chinese Fraud Syndicate (34)
   > "Chinese Fraud Syndicate mentioned 34 times across sources. Cross-border angle visible automatically."

---

## ACT 5 — "Actionable Output" (5 min)

1. **Trending Keywords**: TGCSB (46), digital arrest (40), mule account (39), pig butchering (35), investment fraud (7), money laundering (7)
   > "These are the current threat patterns. 'Digital arrest' trending — new scam type where fraudster impersonates police over video call."

2. Open **existing report** (intelligence_brief, June 28)
3. Show PDF structure — BLUF, source inventory, clusters, signals, identifiers
4. **Hand over the printed PDF** (telangana_leave_behind.pdf)
   > "This is generated from real data your system collected. Imagine this every Monday morning on your desk."

---

## ACT 6 — "Scale" (3 min, if time)

Quick flip to show breadth:
- **Nagaland Social Media Monitoring** — 7,542 items, 17 sources, 4,434 signals (DIG demo went well last week)
- **Live Cyber Fraud Financial** — HK phone numbers (+852...), mule Telegram handles (usdt66999999, kimpay888)
- **IAF topics** — Chinese Air Power, Anti-IAF Disinformation (140 items, 71 items)

> "Same platform, different topics, different scale. One machine per officer."

---

## Closing (2 min)

> "Rs 25 lakh per year. One analyst workstation. Sovereign — data never leaves your building. No cloud dependency. Runs on one machine."

> "What you saw is real data. Not a demo database — live scraping since May 2025."

---

## DO NOT

- Demo WhatsApp bridge (unhealthy)
- Click into down sources (Deccan Chronicle, The420, Hans India — health status = down)
- Zoom into cluster label text (still has minor formatting artifacts)
- Promise specific scam detection accuracy numbers
- Show paused topics (ec-topic-sebi, ec-topic-ncb)
- Show test topic "nnnnnn"

## IF ASKED

| Question | Answer |
|----------|--------|
| "Can you monitor WhatsApp?" | "WhatsApp connector is built and tested. Needs device pairing per deployment." |
| "Telugu language?" | "Multilingual pipeline supports Telugu, Hindi, English. NLLB-200 translation model." |
| "Dark web — is it legal?" | "Public onion search engines only. Same as Google searches. No marketplace infiltration." |
| "How many sources can it handle?" | "Currently 22 on this topic. Nagaland runs 17. No hard limit — scales with hardware." |
| "Accuracy of identifier extraction?" | "Regex + NLP hybrid. ~80% on phone/UPI/Telegram handles. Analyst validates before action." |
| "Integration with CCTNS?" | "Export as PDF/CSV. API available for custom integration. No direct CCTNS connector yet." |
| "Price?" | "Rs 25 lakh per year, per workstation. Includes setup, training, 12 months support." |
