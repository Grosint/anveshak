---
title: Separate penalty magnitude from noise filter threshold in credibility settings
created: 2026-05-08
---

## Problem

`credibility_min_auto_drop` was used for two unrelated purposes:
1. Per-deepfake penalty multiplier in `compute_new_score()` — "how much to drop"
2. Noise filter in `run_contradiction_update()` — "ignore tiny changes"

With value 10.0, all contradiction drops (5.0 pts) were silently skipped because `5.0 < 10.0`.

## Fix

Separate into two independent settings:
```python
credibility_deepfake_drop: float = 1.0   # pts subtracted per high-risk deepfake
credibility_min_auto_drop: float = 1.0   # minimum delta to write audit log (noise filter)
```

## Rule

Never use one setting for two purposes. If you're checking `settings.X` in two places
that mean different things, create `settings.Y` for the second use case — even if
the values happen to be the same today.
