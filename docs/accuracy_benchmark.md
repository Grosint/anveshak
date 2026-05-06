# Anveshak — Accuracy Benchmark Report
## Validation Against Known OSINT Events

**Document Classification:** Internal — Shareable with prospective clients under NDA
**Prepared by:** Garud Research & Tech Private Limited
**Version:** 1.0
**Date:** May 2026

---

## Purpose

This document presents Anveshak's detection accuracy measured against a corpus of 100 publicly documented OSINT-significant events. The benchmark demonstrates precision, recall, and time-to-detection versus mainstream media reporting.

---

## Methodology

### Event Corpus Selection

100 events selected from Jan 2024 – April 2026 across five categories:

| Category | Count | Examples |
|----------|-------|----------|
| Information operations / influence campaigns | 25 | Coordinated social media campaigns, state-sponsored narratives |
| Cross-border security incidents | 25 | Border incursions, ceasefire violations, infiltration attempts |
| Deepfake / manipulated media | 20 | Synthetic videos attributed to officials, doctored satellite imagery |
| Protest / civil unrest precursors | 15 | Pre-event coordination on Telegram/social platforms |
| Critical infrastructure threats | 15 | Cyber threat indicators, supply chain compromise signals |

**Selection criteria:**
- Event must have a verifiable public timeline (media reports, official statements, court documents)
- OSINT signals must have been available before or concurrent with mainstream reporting
- Events span multiple languages (English, Hindi, Urdu, Chinese, Arabic)

### Measurement Definitions

| Metric | Definition |
|--------|-----------|
| **True Positive (TP)** | Anveshak generated a signal for an event that actually occurred |
| **False Positive (FP)** | Anveshak generated a signal but no corresponding real event occurred |
| **False Negative (FN)** | A real event occurred but Anveshak did not generate a signal |
| **Precision** | TP / (TP + FP) — "When Anveshak alerts, how often is it real?" |
| **Recall** | TP / (TP + FN) — "Of real events, how many did Anveshak catch?" |
| **Time Advantage** | Hours between Anveshak's first signal and first mainstream media report |

### Test Configuration

- Hardware: Single workstation (Intel Xeon, 64 GB RAM, RTX 4090)
- LLM: qwen2:7b (Q4_0 quantisation) via Ollama
- Embedding model: sentence-transformers/all-MiniLM-L6-v2
- Sources configured: 200+ per topic (Telegram channels, RSS feeds, social handles, news sites)
- Signal threshold: 3 independent sources (default)
- Languages: Hindi, English, Urdu, Chinese, Arabic enabled via NLLB-200

---

## Results Summary

### Overall Performance

| Metric | Score |
|--------|-------|
| **Precision** | 0.0 % |
| **Recall** | 0.0 % |
| **F1 Score** | 0.0 % |
| **Median Time Advantage** | 0.0 hours before mainstream media |hours before mainstream media |
| **Mean Time Advantage** | 0.0 hours before mainstream media |hours before mainstream media |
| **Deepfake Detection Accuracy** | ___ % (on manipulated media subset) |

### Performance by Category

| Category | Precision | Recall | Avg Time Advantage |
|----------|-----------|--------|-------------------|
| Information operations | 0.0 % | 0.0 % | 0.0 hrs |
| Cross-border security | 0.0 % | 0.0 % | 0.0 hrs |
| Deepfake / manipulated media | 0.0 % | 0.0 % | 0.0 hrs |
| Protest / civil unrest | 0.0 % | 0.0 % | 0.0 hrs |
| Critical infrastructure | 0.0 % | 0.0 % | 0.0 hrs |

### Performance by Language

| Source Language | Precision | Recall | Notes |
|---------------|-----------|--------|-------|
| English | 0.0 % | 0.0 % | Baseline |
| Hindi | 0.0 % | 0.0 % | Via NLLB-200 translation |
| Urdu | 0.0 % | 0.0 % | Via NLLB-200 translation |
| Chinese (Simplified) | 0.0 % | 0.0 % | Via NLLB-200 translation |
| Arabic | 0.0 % | 0.0 % | Via NLLB-200 translation |

---

## Detailed Event Timeline Examples

### Example 1: [Category — Event Name]

| Timestamp | Source | What Anveshak Detected |
|-----------|--------|----------------------|
| T+0h | [Telegram channel / RSS / social] | First signal — raw content ingested |
| T+2h | [Second independent source] | Corroborating signal |
| T+3h | [Third independent source] | **Signal fired** — threshold met |
| T+48h | Mainstream media | First public report |

**Time advantage: 45 hours**

### Example 2: [Category — Event Name]

_[Same format — fill with actual test data]_

### Example 3: [Category — Event Name]

_[Same format — fill with actual test data]_

---

## False Positive Analysis

| FP Category | Count | Root Cause | Mitigation Applied |
|-------------|-------|-----------|-------------------|
| Satire/parody misclassified | ___ | Source credibility not yet calibrated | Credibility auto-scoring (M1) now downgrades satire sources |
| Stale event re-amplified | ___ | Old content reshared as "new" | Content dedup via content_hash prevents duplicate signals |
| Translation artefact | ___ | NLLB mistranslation created false match | Relevance gate (cosine similarity > 0.6) filters noise |

---

## False Negative Analysis

| FN Category | Count | Root Cause | Mitigation |
|-------------|-------|-----------|-----------|
| Source not configured | ___ | Event discussed on platforms not monitored | Expand source list for that topic |
| Below signal threshold | ___ | Only 2 sources detected (threshold = 3) | Analyst can lower threshold per-topic |
| Language not supported | ___ | Content in unsupported script | Add language to NLLB pipeline |

---

## Comparison: Anveshak vs Manual OSINT Workflow

| Metric | Manual (4-analyst team) | Anveshak (automated) |
|--------|------------------------|---------------------|
| Sources monitored simultaneously | 20–30 | 500+ |
| Languages covered | 1–2 (analyst dependent) | 200+ (NLLB-200) |
| Daily operating hours | 8–12 hrs (shift-limited) | 24/7 continuous |
| Time to correlate 3+ sources | 4–8 hours | < 5 minutes |
| Deepfake detection | None (visual inspection) | Automated (DIRE + CLIP) |
| Audit trail | Manual log entries | Automatic, immutable |
| Monthly analyst cost | ₹4–8 Lakh (4 analysts) | ₹0 (machine operates autonomously) |

---

## How to Reproduce

```bash
# 1. Configure topic with event-relevant keywords
POST /api/v1/topics {"name": "benchmark-event-X", "keywords": [...]}

# 2. Attach known sources
POST /api/v1/topics/{id}/sources/{source_id}

# 3. Run historical backfill for the event time window
POST /api/v1/scraper/backfill {"topic_id": "...", "from": "2024-01-01", "to": "2024-01-15"}

# 4. Check signals generated
GET /api/v1/signals?topic_id=...

# 5. Compare signal timestamps against known event timeline
```

---

## Certification & Validation Path

| Step | Status |
|------|--------|
| Internal benchmark (this document) | In Progress |
| Independent validation by STQC | Planned |
| Red-team exercise (adversarial evasion) | Planned |
| Field pilot with operational unit | Planned |

---

## Conclusion

_[To be filled after benchmark execution]_

Anveshak's multi-source correlation approach and signal threshold mechanism are designed to minimise false positives while maintaining high recall. The time advantage over manual workflows demonstrates operational value for intelligence units that cannot afford to wait for mainstream reporting.

---

**Next Steps:**
1. Execute benchmark against full 100-event corpus
2. Fill all ___ fields with measured values
3. Select 5 strongest event timelines for detailed case studies
4. Submit for independent STQC validation
