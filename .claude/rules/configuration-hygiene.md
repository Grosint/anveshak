# Configuration Hygiene

Consolidated from 3 learned instincts.

## One Setting, One Purpose

Never use one setting for two unrelated purposes. If a value is checked in two
different contexts with different semantics, create two settings — even if the
values happen to be the same today.

Example: `credibility_deepfake_drop` (penalty per item) vs `credibility_min_auto_drop`
(noise filter threshold). See: `learned/credibility-settings-separation.md`

## Separate Thresholds for Separate Directions

When a feature has both positive and negative paths (boost vs drop), use separate
thresholds. A single threshold silently blocks whichever direction has a smaller delta.

Example: `credibility_min_auto_drop` vs `credibility_min_auto_boost`
See: `learned/bidirectional-auto-scoring.md`

## Per-Component Scheduling

Track timestamps per component (per adapter, per topic) rather than using a single
global interval. Different components have different natural cadences.

See: `learned/per-adapter-interval-scheduling.md`

## Invariant Tests

Test that settings don't defeat themselves:
```python
assert settings.credibility_contradiction_drop >= settings.credibility_min_auto_drop
```
