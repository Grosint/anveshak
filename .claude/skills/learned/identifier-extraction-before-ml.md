# Regex Identifiers First, ML Classification Later

## Pattern
For fraud/narco/financial crime detection, start with deterministic regex extraction
+ keyword template matching. Add ML classification only after 6+ months of analyst-
labeled data from production use.

```
Phase 1 (ship now):
  Identifiers = regex (phone, UPI, crypto wallet, GSTIN, etc.)
  Classification = keyword overlap + embedding cosine similarity
  Speed: < 10ms per content item, zero GPU
  Accuracy: ~75-80% for known patterns

Phase 2 (month 6+):
  Identifiers = same regex (works fine)
  Classification = fine-tuned DistilBERT on analyst-confirmed labels
  Training data: 6 months of confirm/dismiss from production
  Accuracy: ~85-90%
```

## When to apply
- When someone suggests "use AI/ML to detect fraud patterns"
- When accuracy of keyword matching seems low
- When deciding between shipping now vs building ML pipeline

## Why
- No labeled training data exists at project start
- Keyword matching at 75% + analyst confirmation > ML at 90% with no human review
- Analyst dismiss/confirm actions become training labels for Phase 2
- High recall (catch everything) matters more than high precision early on
- Regex: <1ms, zero GPU. LLM classification: 2-5s, GPU time consumed

## Anti-pattern
Building ML classification pipeline before having production deployments.
The training data comes FROM deployments — you can't skip ahead.
