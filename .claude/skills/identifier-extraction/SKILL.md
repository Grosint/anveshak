---
name: identifier-extraction
description: "Engine C identifier and entity extraction. Covers entity name normalisation at query time, regex before ML, spaCy abbreviated labels, social URLs as handles, dual keyword-plus-embedding template matching, cross-domain identifier intelligence, and the wiring checklist for a new identifier type. Use when extracting phone numbers, UPI IDs, crypto wallets, Telegram handles, or working on NER."
---

# Identifier & Entity Extraction

7 instincts. Engine C extraction + NER pipelines.

## Entity Name Normalization at Query Time

spaCy stores raw entity text. Same entity = multiple variants ("India"/"india", "US"/"the United States").
Fix at aggregation layer (not insert): SQL `GROUP BY LOWER(entity_text)` + Python alias merging.
Mention count: SUM. Source count: MAX (overlap). Latest mention: MAX. Different entity_type: keep separate.
Don't normalize at insert — raw text used by other features, migration would break backfill.
See: `.claude/skills/learned/entity-name-normalization.md`

## Regex First, ML Second

Phase 1 (ship now): deterministic regex + keyword templates. 75-80% accuracy, <10ms.
Phase 2 (month 6+): fine-tuned ML on analyst-validated production labels.
Never delay shipping for ML when regex covers common cases.
See: `.claude/skills/learned/identifier-extraction-before-ml.md`

## spaCy Entity Labels Are Abbreviated

spaCy uses abbreviated labels: FAC (not FACILITY), GPE (not Country/City),
NORP (not Nationality), LOC (not Location).
Verify against stored data before writing entity type filters.
See: `.claude/skills/learned/spacy-entity-type-naming.md`

## Social Media URL Extraction

`https://t.me/username` must extract as TELEGRAM_HANDLE, not URL_DOMAIN.
Domain-level extraction (t.me, instagram.com) creates hub nodes in graphs,
pollutes identifier clustering — every message links same domain.
Extract path segment as handle instead.
Skip noise paths: `s`, `share`, `joinchat`, `addstickers`.
See: `.claude/skills/learned/telegram-url-to-handle.md`

## Dual Matching: Keyword + Embedding

Template/pattern detection: use both keyword matching AND embedding similarity.
Take max score. Keyword catches exact matches; embedding catches paraphrases.
Neither alone sufficient — keyword misses rephrasing, embedding misses exact terminology.
See: `.claude/skills/learned/scam-template-dual-matching.md`

## Cross-Domain Identifier Intelligence

Same identifiers (mule bank accounts, crypto wallets, Telegram handles) appear
across domains: cyber fraud, narcotics, financial crime. Track identifiers as
first-class entities w/ cross-topic linking.
Market priority: MEA > Police > SEBI > NCB.
See: `.claude/skills/learned/mule-account-cross-domain-indicator.md`

## New Identifier Type Wiring

Adding a new type requires updating 13 files across 4 layers. Missing any one → silent breakage.
See: `.claude/skills/learned/identifier-type-wiring-checklist.md`