# Identifier & Entity Extraction

Consolidated from 5 learned instincts. These apply to Engine C identifier extraction and NER pipelines.

## Regex First, ML Second

Phase 1 (ship now): deterministic regex + keyword templates. 75-80% accuracy, <10ms.
Phase 2 (month 6+): fine-tuned ML model trained on analyst-validated production labels.
Never delay shipping for ML when regex covers the common cases.
See: `learned/identifier-extraction-before-ml.md`

## spaCy Entity Labels Are Abbreviated

spaCy uses abbreviated labels: FAC (not FACILITY), GPE (not Country/City),
NORP (not Nationality), LOC (not Location).
Always verify against actual stored data before writing entity type filters.
See: `learned/spacy-entity-type-naming.md`

## Social Media URL Extraction

`https://t.me/username` must extract as TELEGRAM_HANDLE, not URL_DOMAIN.
Domain-level extraction (t.me, instagram.com) creates giant hub nodes in graphs
and pollutes identifier clustering — every message links to the same domain.
Extract the path segment as the handle instead.
Skip noise paths: `s`, `share`, `joinchat`, `addstickers`.
See: `learned/telegram-url-to-handle.md`

## Dual Matching: Keyword + Embedding

For template/pattern detection, use both keyword matching AND embedding similarity.
Take the maximum score. Keyword catches exact matches; embedding catches paraphrases.
Neither alone is sufficient — keyword misses rephrasing, embedding misses exact terminology.
See: `learned/scam-template-dual-matching.md`

## Cross-Domain Identifier Intelligence

Same identifiers (mule bank accounts, crypto wallets, Telegram handles) appear
across domains: cyber fraud, narcotics, financial crime. Track identifiers as
first-class entities with cross-topic linking.
Market priority: MEA > Police > SEBI > NCB.
See: `learned/mule-account-cross-domain-indicator.md`
