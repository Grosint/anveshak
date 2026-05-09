# Threshold & Setting Invariants

## When to load: any feature with configurable thresholds, penalties, or noise filters

Merged from: `bidirectional-auto-scoring.md`, `credibility-settings-separation.md`

---

## Rule 1: One setting, one purpose

Never use one setting for two unrelated purposes. If a value is checked in two
different contexts with different semantics, create two settings — even if the
values happen to be the same today.

Example: `credibility_deepfake_drop` (penalty per item) vs `credibility_min_auto_drop`
(noise filter threshold). Using one setting for both silently killed the feature.

## Rule 2: Separate thresholds for separate directions

When a feature has both positive and negative paths (boost vs drop), use separate
thresholds. A single threshold silently blocks whichever direction has a smaller delta.

Example: `credibility_min_auto_drop=10.0` killed `credibility_cross_verify_boost=2.0`
because `2.0 < 10.0` → always skipped. Fix: separate `credibility_min_auto_boost=1.0`.

## Rule 3: Invariant tests for settings

After setting defaults, always assert that settings don't defeat themselves:

```python
def test_settings_dont_self_defeat():
    s = Settings()
    assert s.credibility_min_auto_boost <= s.credibility_cross_verify_boost
    assert s.credibility_contradiction_drop >= s.credibility_min_auto_drop
```

This catches future default changes that accidentally disable features.

## Implementation reference

- `services/analyst/anveshak/analyst/settings.py`
- `services/analyst/anveshak/analyst/credibility.py`
- `tests/unit/test_credibility_hardening.py`
