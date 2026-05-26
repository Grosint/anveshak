---
name: Quality ratio bypass for substantial clean text
description: If clean_text >= 500 chars, skip the clean/raw ratio check — HTML-heavy sites produce low ratios on real articles
type: pattern
confidence: high
---

## Problem

The content quality ratio gate (`clean_text / raw_text < threshold`) falsely rejected real articles from HTML-heavy news sites. Modern sites serve 20-90KB of HTML for a 3-5KB article — ratio of 0.06-0.12 is normal for legitimate content on sites like idrw.org, NDTV, Al Jazeera.

## Solution

Add a length bypass in `score_content_quality()`:

```python
_RATIO_BYPASS_MIN_CHARS = 500

def score_content_quality(raw_text, clean_text):
    if not clean_text or len(clean_text) < _MIN_CLEAN_CHARS:  # Gate 1: too short
        return "low_quality"
    if is_paywall_page(raw_text) or is_paywall_page(clean_text):  # Gate 2: paywall
        return "low_quality"
    if is_nav_icon_garbage(clean_text):  # Gate 3: nav icons
        return "low_quality"
    if not raw_text:
        return "good"
    # Gate 4: length bypass — substantial text is always good
    if len(clean_text) >= _RATIO_BYPASS_MIN_CHARS:
        return "good"
    # Gate 4b: ratio check for short texts only
    ratio = len(clean_text) / len(raw_text)
    if ratio < _MIN_QUALITY_RATIO:
        return "low_quality"
    return "good"
```

## Critical ordering constraint

The bypass MUST fire AFTER paywall and nav-icon gates. A 500-char paywall page or a 500-char nav-icon dump is still garbage. The bypass only rescues items that passed structural quality checks but have a low ratio due to bloated HTML.

**Test this invariant explicitly:**
```python
def test_paywall_with_long_text_still_rejected():
    """Paywall check fires before length bypass."""
    paywall_text = "...3+ paywall indicators, 500+ chars..."
    assert score_content_quality(paywall_text, paywall_text) == "low_quality"
```

## Why 500 chars

500 chars ≈ 3-4 paragraphs of text. Below 500, the ratio check is a useful signal (very short text from a heavy page is likely a nav fragment). Above 500, the text is substantial enough that the ratio is irrelevant.

## See also

- `docs/tuning_history.md` — full evidence and data behind the 0.15 → 0.08 ratio threshold change
- `quality-gate-all-consumers.md` — every consumer must apply quality filters
