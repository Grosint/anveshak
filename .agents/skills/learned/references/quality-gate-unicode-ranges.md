# Pattern: Unicode Range Coverage in Content Quality Gates

## When to load: modifying content_quality.py, adding new language support, debugging why content is silently dropped

---

## Problem

The content quality gate counts "words" using a regex to filter boilerplate. But the regex only included Latin, Cyrillic, Arabic, and CJK ranges — **Hindi (Devanagari) was missing**. All Hindi-only articles were silently dropped with 0 words detected → 0 embeddings → invisible to clustering.

## Solution

Always check the word-counting regex covers ALL supported NLLB languages:

```python
# BEFORE (missing Devanagari):
r"[a-zA-Z\u0400-\u04ff\u0600-\u06ff]{2,}|[\u4e00-\u9fff\u3400-\u4dbf]"

# AFTER (with Devanagari):
r"[a-zA-Z\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]{2,}|[\u4e00-\u9fff\u3400-\u4dbf]"
```

## Unicode Ranges for Supported Languages

The live list of supported languages is `AnalystSettings.stance_supported_languages`,
not a comment. Check the counter against that list, not against memory.

| Script | Range | Languages |
|--------|-------|-----------|
| Latin | a-zA-Z, U+00C0-024F | en, fr, de, es, tr |
| Greek | U+0370-03FF | el |
| Cyrillic | U+0400-052F | ru |
| Hebrew | U+0590-05FF | he |
| Arabic | U+0600-06FF plus supplements | ar, ur, fa |
| Devanagari | U+0900-097F | hi, mr, ne |
| Bengali | U+0980-09FF | bn, as |
| Gurmukhi | U+0A00-0A7F | pa |
| Gujarati | U+0A80-0AFF | gu |
| Odia | U+0B00-0B7F | or |
| Tamil | U+0B80-0BFF | ta |
| Telugu | U+0C00-0C7F | te |
| Kannada | U+0C80-0CFF | kn |
| Malayalam | U+0D00-0D7F | ml |
| Sinhala | U+0D80-0DFF | si |
| Hangul | U+1100-11FF, U+3130-318F, U+AC00-D7AF | ko |

Counted one character per word, because these scripts do not separate words:

| Script | Range | Languages |
|--------|-------|-----------|
| CJK | U+4E00-9FFF, U+3400-4DBF, U+F900-FAFF | zh, ja kanji |
| Kana | U+3040-30FF | ja |
| Thai | U+0E00-0E7F | th |
| Lao | U+0E80-0EFF | lo |
| Myanmar | U+1000-109F | my |
| Khmer | U+1780-17FF | km |

## This bug has been shipped twice, in two shapes

First as a missing Devanagari range in the analyst's pattern.

Then again when the character floor was replaced by a word floor: the word
counter moved into the scraper carrying only six scripts, and Tamil, Telugu,
Kannada, Malayalam, Gujarati, Gurmukhi, Odia and Sinhala all counted zero. That
second shape was worse, because the scraper persists its verdict as
`content_quality`, and the clustering SQL honours `low_quality` forever. The
character floor it replaced was at least script-neutral.

The guard is `tests/unit/test_word_counter.py`: one real sentence per language in
`stance_supported_languages`, each asserted above the gate's floor. A language
added to that list without a script in the counter now fails the suite.

## Do NOT replace the ranges with a generic Unicode letter class

`[^\W\d_]{2,}` looks like the obvious simplification and is wrong. Combining
marks are not letters, so it splits every Indic word at its vowel signs.
Measured: one real Hindi sentence drops from 19 words to 9, and the standalone
word "की" counts as zero. The tables carry whole blocks precisely so a script's
marks travel with its letters.

## A word floor is not automatically script-neutral either

Characters-per-word varies by script, which is what makes a character floor
unfair. Words-per-sentence varies too. A one-sentence Telugu item counts 8 words
where the English equivalent counts 15, because Dravidian agglutination packs
into one word what English spreads over three. Calibrate the floor against the
shortest genuine item in every supported script, not against English.

## Pitfall: Silent Failure

This bug is invisible — no error, no warning. The quality gate returns `False`,
the item is logged as "skipped_quality", and no embedding is generated. The only
symptom is missing embeddings for non-Latin content.

**Always test the quality gate with sample text from each supported language
after adding new Unicode ranges.**

## Files

- `sdk/anveshak/text.py` — the word counter, one home for the script tables
- `services/analyst/anveshak/analyst/content_quality.py` — `is_quality_content()`
- `services/scraper/anveshak/scraper/clean.py` — `score_content_quality()`, persists its verdict
- `tests/unit/test_word_counter.py` — the per-language guard
