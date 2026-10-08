"""Script-aware word counting, shared by every quality gate.

A character count is not a measure of content volume. Devanagari carries the
same meaning as Latin in roughly half the characters, so a character floor
rejects a complete Hindi sentence while passing the English sentence that says
the same thing. Words are the script-neutral unit, so the gates count words.

This lives in the SDK because the analyst and the scraper each hold a quality
gate, and a regex copied into two services drifts. It already did once: the
analyst's pattern shipped without Devanagari, and every Hindi-only article was
silently dropped at zero words. See
.agents/skills/learned/references/quality-gate-unicode-ranges.md.

Adding a language to the platform means adding its script here, and only here.
tests/unit/test_word_counter.py holds one real sentence per language in
AnalystSettings.stance_supported_languages and fails if any of them counts
fewer words than the quality gate's floor, so a language added to that list
without a script here fails the suite rather than silently scoring zero.

Two things that look like simplifications and are not:

A generic "any Unicode letter" class must NOT be substituted for the tables
below. Combining marks are not letters, so `[^\\W\\d_]` splits every Indic word
at its vowel signs: measured, it takes one real Hindi sentence from 19 words to
9 and counts the word "\u0915\u0940" as zero. The tables carry whole blocks
precisely so that a script's marks travel with its letters.

The ranges are written as hex code points rather than as literal characters or
as backslash-u escapes inside a pattern string. A literal range is unreviewable
at a glance and a stray editor or normalisation pass can alter it silently, and
the failure mode of an altered range is a zero word count with no error.
"""

from __future__ import annotations

import re

# Scripts that separate words with a space. Two or more characters count as one
# word, which discards stray diacritics and single letters. Whole blocks rather
# than letter-only subsets, so that combining marks stay inside their word.
_SPACED_SCRIPTS: tuple[tuple[str, int, int, str], ...] = (
    ("Latin", 0x0041, 0x005A, "en, and every Latin-script language"),
    ("Latin lowercase", 0x0061, 0x007A, "en"),
    ("Latin-1 and extended", 0x00C0, 0x024F, "fr, de, es, tr"),
    ("Greek", 0x0370, 0x03FF, "el"),
    ("Cyrillic", 0x0400, 0x052F, "ru"),
    ("Hebrew", 0x0590, 0x05FF, "he"),
    ("Arabic", 0x0600, 0x06FF, "ar, ur, fa"),
    ("Arabic supplement", 0x0750, 0x077F, "ur"),
    ("Arabic presentation A", 0xFB50, 0xFDFF, "ar, ur"),
    ("Arabic presentation B", 0xFE70, 0xFEFF, "ar, ur"),
    ("Devanagari", 0x0900, 0x097F, "hi, mr, ne"),
    ("Bengali", 0x0980, 0x09FF, "bn, as"),
    ("Gurmukhi", 0x0A00, 0x0A7F, "pa"),
    ("Gujarati", 0x0A80, 0x0AFF, "gu"),
    ("Odia", 0x0B00, 0x0B7F, "or"),
    ("Tamil", 0x0B80, 0x0BFF, "ta"),
    ("Telugu", 0x0C00, 0x0C7F, "te"),
    ("Kannada", 0x0C80, 0x0CFF, "kn"),
    ("Malayalam", 0x0D00, 0x0D7F, "ml"),
    ("Sinhala", 0x0D80, 0x0DFF, "si"),
    ("Hangul jamo", 0x1100, 0x11FF, "ko"),
    ("Hangul compatibility", 0x3130, 0x318F, "ko"),
    ("Hangul syllables", 0xAC00, 0xD7AF, "ko"),
)

# Scripts with no word separator, counted one character per word. A sentence in
# these scripts is one unbroken run, so a two-or-more rule would score a whole
# sentence as a single word. The cost is the reverse: a short item in one of
# these scripts clears the word floor on very little content, which
# tests/unit/test_content_quality.py pins rather than leaves to be discovered.
_UNSPACED_SCRIPTS: tuple[tuple[str, int, int, str], ...] = (
    ("CJK Unified", 0x4E00, 0x9FFF, "zh, ja kanji"),
    ("CJK extension A", 0x3400, 0x4DBF, "zh"),
    ("CJK compatibility", 0xF900, 0xFAFF, "zh"),
    ("Kana", 0x3040, 0x30FF, "ja"),
    ("Thai", 0x0E00, 0x0E7F, "th"),
    ("Lao", 0x0E80, 0x0EFF, "lo"),
    ("Myanmar", 0x1000, 0x109F, "my"),
    ("Khmer", 0x1780, 0x17FF, "km"),
)


def _character_class(ranges: tuple[tuple[str, int, int, str], ...]) -> str:
    """Render a range table as the inside of a regex character class."""
    return "".join(f"\\u{low:04x}-\\u{high:04x}" for _name, low, high, _langs in ranges)


_WORD_RE = re.compile(
    f"[{_character_class(_UNSPACED_SCRIPTS)}]" f"|[{_character_class(_SPACED_SCRIPTS)}]{{2,}}"
)


def extract_words(text: str) -> list[str]:
    """Return the lowercased word tokens in text, across every supported script.

    Returns an empty list for empty or wordless input, so callers must guard a
    division by the token count rather than assume at least one token.

    Use count_words when only the count is wanted. This builds the whole token
    list, which on a 16 MB scraped page is hundreds of megabytes of transient
    strings.
    """
    return _WORD_RE.findall(text.lower())


def count_words(text: str) -> int:
    """Return how many words text carries, across every supported script.

    Streams the matches rather than materialising them, because this runs on
    scraped pages that choose their own size. Lowercasing is not needed in order
    to count, only in order to compare tokens, so it is left to extract_words.
    """
    return sum(1 for _ in _WORD_RE.finditer(text))
