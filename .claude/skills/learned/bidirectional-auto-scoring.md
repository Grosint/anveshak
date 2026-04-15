# Bidirectional Auto-Scoring with Separate Thresholds

## When to load: any system that automatically adjusts a score in both directions (up and down)

---

## The Problem

A scoring system has a "minimum delta to act" threshold to prevent audit log noise from
tiny fluctuations. When the system also supports boosts (score increases), applying the
same threshold to both directions silently kills the boost path if the boost amount is
smaller than the drop threshold.

**Real failure (Phase 7):**
```python
# settings.py
credibility_min_auto_drop: float = 10.0    # minimum drop to write audit log
credibility_cross_verify_boost: float = 2.0  # boost amount

# In run_cross_verification_update():
if abs(new_score - old_score) < settings.credibility_min_auto_drop:
    continue   # 2.0 < 10.0 → ALWAYS SKIPS. Feature is dead by default.
```

The feature appeared implemented and tested, but would never fire with default settings.
No error, no log — silent skip on every cycle.

---

## The Fix: One threshold per direction

```python
# settings.py — separate thresholds, separate semantics
credibility_min_auto_drop: float = 10.0    # governs drops: deepfake penalty, contradiction
credibility_min_auto_boost: float = 1.0    # governs boosts: cross-verification
credibility_cross_verify_boost: float = 5.0  # must be >= credibility_min_auto_boost
```

```python
# In drop function:
if abs(new_score - old_score) < settings.credibility_min_auto_drop:
    continue

# In boost function:
if abs(new_score - old_score) < settings.credibility_min_auto_boost:
    continue
```

---

## Mandatory invariant test

After setting defaults, always assert the invariant in a unit test:

```python
def test_cross_verify_boost_uses_separate_min_threshold():
    """credibility_min_auto_boost must be < credibility_cross_verify_boost
    or every boost will be silently skipped.
    """
    s = AnalystSettings()
    assert s.credibility_min_auto_boost < s.credibility_cross_verify_boost, (
        "min_auto_boost must be less than cross_verify_boost — "
        "otherwise every boost is silently skipped by default settings"
    )
```

This test catches any future change that accidentally raises `credibility_min_auto_boost`
above the boost amount.

---

## Clamp scores symmetrically

Both directions must use the same clamp function to enforce hard bounds:

```python
def clamp_score(score: float) -> float:
    """Clamp credibility score to [0.0, 100.0]. Pure function."""
    return round(max(0.0, min(100.0, score)), 2)

# Drops: floor at 0.0
new_score = clamp_score(old_score - drop_amount)

# Boosts: ceiling at 100.0
new_score = clamp_score(old_score + boost_amount)
```

A common bug is applying only `max(0.0, ...)` (floor) without the `min(100.0, ...)` ceiling.
Test both directions explicitly.

---

## Don't reuse a single function — add alongside

If an existing `apply_credibility_drop()` function handles the audit log atomically,
do NOT rename it to `apply_credibility_change()` to handle both directions.
Renaming breaks all existing callers. Instead, add a new `apply_credibility_boost()`
with identical structure:

```python
# Keep existing:
async def apply_credibility_drop(conn, source_id, old_score, new_score, reason, now):
    await conn.execute(SQL_UPDATE_SOURCE_SCORE, new_score, now, source_id)
    await conn.execute(SQL_INSERT_AUDIT_LOG, uuid4(), source_id, old_score, new_score, reason, ...)

# Add new — same pattern, different name:
async def apply_credibility_boost(conn, source_id, old_score, new_score, reason, now):
    await conn.execute(SQL_UPDATE_SOURCE_SCORE, new_score, now, source_id)
    await conn.execute(SQL_INSERT_AUDIT_LOG, uuid4(), source_id, old_score, new_score, reason, ...)
```

The naming is intentional: at the call site, it's clear whether a boost or drop is happening.
A single `apply_credibility_change()` obscures direction and makes code review harder.

---

## Implementation reference
`services/analyst/anveshak/analyst/credibility.py` — `clamp_score`, `apply_credibility_boost`, `run_cross_verification_update`
`services/analyst/anveshak/analyst/settings.py` — `credibility_min_auto_boost` vs `credibility_min_auto_drop`
`tests/unit/test_credibility_hardening.py` — invariant test + clamp tests
