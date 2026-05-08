---
title: Return None on deepfake detection failure, not 0.0
created: 2026-05-08
---

## Problem

Deepfake analysis returning `0.0` on error is indistinguishable from "confirmed real image."
Downstream credibility scoring treats failed analysis as a valid finding.

## Pattern

```python
# WRONG — 0.0 looks like a valid score
except Exception as exc:
    return 0.0, "error"

# CORRECT — None forces explicit null checks
except Exception as exc:
    log.error("vision.deepfake_image.failed", error=str(exc))
    return None, "error"

# Caller must check before using
if deepfake_score is not None and deepfake_score > threshold:
    ...
if deepfake_score is not None:
    vision_deepfake_score.observe(deepfake_score)
```

## Why

CLAUDE.md rule 7: "Deepfake scores are probabilities, never booleans."
Extending: they must also never be default values that look like real probabilities.
`0.0` is a valid probability. `None` is not — it forces the caller to handle the error case.

## Applies to

Any ML inference that returns a float score. If the model fails, return `None`, not a default number.
