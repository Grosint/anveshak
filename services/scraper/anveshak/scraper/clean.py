"""Post-extraction text cleaning — strip boilerplate from Crawl4AI raw markdown.

Crawl4AI's raw_markdown often includes navigation menus, ad blocks, cookie banners,
and raw markdown link syntax that make content unreadable. This module cleans the
extracted text into something an analyst can actually read.

Applied AFTER extraction (Crawl4AI/trafilatura) and BEFORE storage as clean_text.
raw_text is preserved as-is for audit trail.
"""
from __future__ import annotations

import hashlib
import re

# ---------------------------------------------------------------------------
# Regex patterns — compiled once at module load
# ---------------------------------------------------------------------------

# Markdown image syntax: ![alt](url) or ![alt](url "title") → strip entirely
_RE_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")

# Markdown link syntax: [text](url) or [text](url "title") → keep text only
_RE_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]+\)")

# Bare URLs on their own line
_RE_BARE_URL_LINE = re.compile(r"^\s*https?://\S+\s*$", re.MULTILINE)

# Asterisk-separated navigation: "* Item * Item * Item" (3+ items between asterisks)
# Matches the pattern from the first * to the last * in a nav sequence
_RE_ASTERISK_NAV = re.compile(
    r"\*\s*[\w&\-'/]+(?:\s+[\w&\-'/]+){0,3}\s*"
    r"(?:\*\s*[\w&\-'/]+(?:\s+[\w&\-'/]+){0,3}\s*){2,}\*?",
)

# Breadcrumb separators: "Home :: Military :: Systems"
_RE_BREADCRUMB = re.compile(r"(?:\w[\w\s]*\s*::\s*){2,}")

# Markdown bold: **text** → text
_RE_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")

# Lines that START with repeated boilerplate (e.g. "Advertisement Advertisement SCMP PLUS...")
_RE_BOILERPLATE_PREFIX_LINE = re.compile(
    r"^\s*(?:advertisement\s+){2,}.*$",
    re.IGNORECASE | re.MULTILINE,
)

# CamelCase-concatenated navigation — catches both standard and mixed-case:
# "ChinaEconomyAsiaWorldSport", "policyNEWUS-China", "BusinessTech", "PostSCMP"
# Detects words jammed together where case transitions mark word boundaries
_RE_CAMEL_NAV = re.compile(r"(?:[A-Z][a-z]+){4,}")

# Mixed-case concatenation: lowercase→uppercase transitions without space
# e.g. "policyNEWUS" "relationsHong" "BusinessTech" "LifestylePeople"
_RE_MIXED_CASE_CONCAT = re.compile(r"[a-z][A-Z]")

# Markdown headers that are just single words (likely nav items)
_RE_MD_HEADER_NAV = re.compile(r"^#{1,3}\s+\w{1,15}\s*$", re.MULTILINE)

# Repeated whitespace / blank lines
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")
_RE_MULTI_SPACE = re.compile(r"[ \t]{2,}")

# ---------------------------------------------------------------------------
# Boilerplate phrases — matched as complete lines (case-insensitive)
# ---------------------------------------------------------------------------

_BOILERPLATE_PHRASES = [
    "advertisement",
    "sign in",
    "sign up",
    "sign out",
    "subscribe now",
    "subscribe",
    "cookie policy",
    "cookie settings",
    "privacy policy",
    "terms of service",
    "terms of use",
    "accept cookies",
    "manage cookies",
    "newsletter",
    "download the app",
    "get the app",
    "follow us",
    "+ follow",
    "# follow",
    "share this article",
    "read more",
    "show more",
    "load more",
    "skip to content",
    "skip to main content",
    "back to top",
    "all rights reserved",
    "log in",
    "log in register",
    "register",
    "my account",
    "what's new",
    "new threads",
    "new posts",
    "new threads new posts",
    "forums",
    "hot topics",
    "you are logged in",
    "logout",
    "loading...",
    "premium content",
    "premium member",
    "subscribers only",
    "subscriber only",
    "sign in to read",
    "create an account to read",
]

_RE_BOILERPLATE_LINE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in _BOILERPLATE_PHRASES) + r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Boilerplate fragments — stripped from WITHIN lines (not just whole-line)
# These appear inline concatenated with real content.
# ---------------------------------------------------------------------------

_INLINE_JUNK_PHRASES = [
    r"log\s+in\s+register",
    r"what's\s+new\s+by:",
    r"how\s+to\s+install\s+the\s+app\s+on\s+ios[^.]*\.",
    r"follow\s+along\s+with\s+the\s+video\s+below[^.]*\.",
    r"this\s+feature\s+may\s+not\s+be\s+available\s+in\s+some\s+browsers\.",
    r"new\s+threads\s+new\s+posts\b",
    r"\d+\s+pages?\s+left",
    r"\*\s*home\s*\*\s*forums\b",
    r"edition:\s*international",
    r"highlights\b",
]

_RE_INLINE_JUNK = re.compile(
    r"(?:" + "|".join(_INLINE_JUNK_PHRASES) + r")",
    re.IGNORECASE,
)

# Lines that are just nav separators
_RE_NAV_SEPARATOR = re.compile(
    r"^[\s\-|·•►▸▹>]+$", re.MULTILINE
)


# ---------------------------------------------------------------------------
# Nav-icon garbage detection — UI element names scraped as content
# ---------------------------------------------------------------------------

# Common icon/nav element names found in scraped RSS/web pages
_NAV_ICON_WORDS = frozenset({
    # Directional icons
    "arrow-down", "arrow-up", "arrow-left", "arrow-right",
    "chevron-down", "chevron-up", "chevron-left", "chevron-right",
    "left-arrow", "right-arrow", "top-nav", "caret-down", "caret-up",
    # Action icons
    "search", "menu", "close", "hamburger", "printer", "print",
    "share", "bookmark", "copy-link", "download", "upload",
    # Social icons
    "facebook", "twitter", "whatsapp", "telegram", "instagram",
    "linkedin", "youtube", "email",
    # UI elements
    "comments", "bell", "user", "account", "cart", "settings",
    "notifications",
})

# Minimum word count and hit ratio to flag as nav-icon garbage
_NAV_ICON_MIN_WORDS = 5
_NAV_ICON_HIT_RATIO = 0.40


def is_nav_icon_garbage(text: str) -> bool:
    """Detect text dominated by UI icon names / nav element labels.

    Returns True if 40%+ of words match known icon/nav vocabulary AND
    there are at least 5 words. This catches scraped icon alt-text and
    aria-labels from news sites (e.g., NDTV RSS).
    """
    if not text:
        return False

    # Tokenise: split on whitespace and common separators
    words = re.split(r"[\s,;:()]+", text.lower().strip())
    words = [w for w in words if w]  # remove empties

    if len(words) < _NAV_ICON_MIN_WORDS:
        return False

    hits = sum(1 for w in words if w in _NAV_ICON_WORDS)
    return hits / len(words) >= _NAV_ICON_HIT_RATIO


def _strip_nav_icon_prefix(text: str) -> str:
    """Strip nav-icon word sequences from the beginning of lines.

    Handles cases like: "arrow-down comments printer search bell top-nav
    right-arrow left-arrow arrow-down , Why Reservation For Their Children?"
    → ", Why Reservation For Their Children?"
    """
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        words = line.strip().split()
        if len(words) < 3:
            cleaned.append(line)
            continue

        # Find the first word that isn't a nav-icon word
        first_real = 0
        for i, w in enumerate(words):
            # Strip leading punctuation/commas to check the core word
            core = w.lower().strip(",:;!?()[]")
            if core and core not in _NAV_ICON_WORDS:
                first_real = i
                break
        else:
            # All words are nav icons — keep line for per-line filter to remove
            cleaned.append(line)
            continue

        # Only strip if we found 3+ consecutive nav-icon words at the start
        if first_real >= 3:
            remainder = " ".join(words[first_real:]).lstrip(",;: ")
            cleaned.append(remainder)
        else:
            cleaned.append(line)

    return "\n".join(cleaned)


def _is_nav_line(line: str) -> bool:
    """Detect navigation-style lines: short capitalised word lists.

    Catches: "Latest China Economy Hong Kong Asia Business Tech Lifestyle"
    Does NOT catch normal sentences that happen to have capitalised words.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return False

    words = stripped.split()
    if len(words) < 6:
        return False

    # If most words are short and capitalised, AND there are no sentence-ending
    # punctuation marks (period, question mark), it's likely nav
    has_sentence_structure = any(c in stripped for c in ".?!")
    if has_sentence_structure:
        return False

    short_cap = sum(1 for w in words if len(w) <= 15 and w[0:1].isupper())
    if short_cap / len(words) >= 0.7 and len(words) >= 6:
        return True

    return False


def _detect_repeated_blocks(lines: list[str], threshold: int = 2) -> set[str]:
    """Find lines that appear multiple times — likely headers/footers."""
    from collections import Counter
    normalised = Counter()
    for line in lines:
        key = line.strip().lower()
        if len(key) > 10:
            normalised[key] += 1
    return {k for k, v in normalised.items() if v >= threshold}


def _strip_camel_nav(text: str) -> str:
    """Remove CamelCase-concatenated navigation.

    Handles two patterns:
    1. Standard: 'ChinaEconomyAsiaWorldSport' (4+ capitalised words jammed)
    2. Mixed: 'policyNEWUS-China relationsHong Kong economyBusinessTech'
       (lowercase→uppercase transitions indicating concatenated nav items)
    """
    # 1. Standard CamelCase (4+ title-case words)
    def _is_camel_junk(match: re.Match) -> str:
        word = match.group(0)
        parts = re.findall(r"[A-Z][a-z]+", word)
        if len(parts) >= 4:
            return ""
        return word

    text = _RE_CAMEL_NAV.sub(_is_camel_junk, text)

    # 2. Mixed-case concatenation: remove words with 3+ lower→upper transitions
    #    e.g. "policyNEWUS" "BusinessTech" "LifestylePeople" "PostSCMP"
    #    Preserve line structure by processing line-by-line
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        words = line.split()
        kept: list[str] = []
        for word in words:
            transitions = len(_RE_MIXED_CASE_CONCAT.findall(word))
            if transitions >= 3:
                continue
            kept.append(word)
        cleaned_lines.append(" ".join(kept))

    return "\n".join(cleaned_lines)


def clean_extracted_text(raw: str) -> str:
    """Clean Crawl4AI/trafilatura output into readable analyst-facing text.

    Transformations applied in order:
    1. Strip markdown images ![alt](url)
    2. Convert markdown links [text](url) → text
    3. Convert markdown bold **text** → text
    4. Remove bare URL lines
    5. Remove lines starting with repeated "Advertisement Advertisement..."
    6. Remove boilerplate phrase lines
    7. Remove inline junk fragments
    8. Remove asterisk-nav, breadcrumb, and CamelCase nav patterns
    9. Remove nav separator lines
    10. Per-line: remove nav-style lines, repeated blocks, short header nav
    11. Collapse excessive whitespace
    """
    if not raw:
        return ""

    text = raw

    # 1. Strip markdown images (before links, since ![alt](url) contains [alt](url))
    text = _RE_MD_IMAGE.sub("", text)

    # 2. Convert markdown links to plain text
    text = _RE_MD_LINK.sub(r"\1", text)

    # 3. Convert markdown bold to plain text
    text = _RE_MD_BOLD.sub(r"\1", text)

    # 4. Remove bare URL lines
    text = _RE_BARE_URL_LINE.sub("", text)

    # 5. Remove lines starting with repeated boilerplate
    text = _RE_BOILERPLATE_PREFIX_LINE.sub("", text)

    # 6. Remove boilerplate phrase lines
    text = _RE_BOILERPLATE_LINE.sub("", text)

    # 7. Remove inline junk fragments
    text = _RE_INLINE_JUNK.sub("", text)

    # 8a. Remove asterisk-nav patterns
    text = _RE_ASTERISK_NAV.sub("", text)

    # 8b. Remove breadcrumb patterns
    text = _RE_BREADCRUMB.sub("", text)

    # 8c. Remove CamelCase-concatenated nav
    text = _strip_camel_nav(text)

    # 9. Remove nav separator lines
    text = _RE_NAV_SEPARATOR.sub("", text)

    # 9b. Strip nav-icon prefixes from lines (icon labels followed by real content)
    text = _strip_nav_icon_prefix(text)

    # 10. Per-line filtering
    lines = text.split("\n")
    repeated = _detect_repeated_blocks(lines)

    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if _is_nav_line(stripped):
            continue

        if is_nav_icon_garbage(stripped):
            continue

        if stripped.lower() in repeated:
            continue

        if _RE_MD_HEADER_NAV.match(stripped):
            continue

        # Skip lines that are now just punctuation/whitespace after cleaning
        if len(stripped) < 5 and not any(c.isalpha() for c in stripped):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # 11. Collapse whitespace
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = text.strip()

    return text


# ---------------------------------------------------------------------------
# Paywall / login-wall detection
# ---------------------------------------------------------------------------

_PAYWALL_INDICATORS = [
    "you are logged in",
    "you don't have any active subscription",
    "no active subscription",
    "active subscription",
    "subscribed with another email",
    "account subscription benefits",
    "premium content",
    "premium member",
    "subscribers only",
    "subscriber only",
    "sign in to read",
    "sign in to continue",
    "create an account to read",
    "subscribe to read",
    "subscribe to continue",
    "login to continue",
    "logout and login",
    "your active subscription",
]

_PAYWALL_THRESHOLD = 3  # need 3+ indicators to flag as paywall page


def is_paywall_page(text: str) -> bool:
    """Detect when extracted text is a login/subscription paywall page.

    Returns True if the text contains 3+ distinct paywall indicator phrases.
    Designed for whole-page detection — individual boilerplate lines are
    handled separately by _RE_BOILERPLATE_LINE.
    """
    if not text:
        return False
    lower = text.lower()
    hits = sum(1 for indicator in _PAYWALL_INDICATORS if indicator in lower)
    return hits >= _PAYWALL_THRESHOLD


# ---------------------------------------------------------------------------
# Quality scoring + clean_hash
# ---------------------------------------------------------------------------

_MIN_CLEAN_CHARS = 100
_MIN_QUALITY_RATIO = 0.08   # lowered from 0.15 — rescues real articles from HTML-heavy sites
_RATIO_BYPASS_MIN_CHARS = 500  # bypass ratio check if clean_text is substantial


def compute_clean_hash(clean_text: str) -> str:
    """SHA-256 of normalised clean_text — for display-time dedup.

    Unlike content_hash (on raw_text, for insert-time dedup), this catches
    visually identical content from different URLs.
    """
    normalised = re.sub(r"\s+", " ", clean_text.lower()).strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def score_content_quality(raw_text: str, clean_text: str) -> str:
    """Return 'good' or 'low_quality' based on cleaning ratio.

    A page where 92%+ of content is stripped as boilerplate is not useful.
    A page with <100 chars of clean text has no real article content.
    A page that is a paywall/login wall is not useful.
    A page with >=500 chars of clean text is accepted regardless of ratio —
    real articles from HTML-heavy sites can have very low clean/raw ratios.
    """
    if not clean_text or len(clean_text) < _MIN_CLEAN_CHARS:
        return "low_quality"

    if is_paywall_page(raw_text) or is_paywall_page(clean_text):
        return "low_quality"

    # Check if clean text is dominated by nav-icon garbage
    if is_nav_icon_garbage(clean_text):
        return "low_quality"

    if not raw_text:
        return "good"

    # Substantial clean text is accepted regardless of ratio — HTML-heavy sites
    # produce legitimately low ratios even for real articles
    if len(clean_text) >= _RATIO_BYPASS_MIN_CHARS:
        return "good"

    ratio = len(clean_text) / len(raw_text)
    if ratio < _MIN_QUALITY_RATIO:
        return "low_quality"

    return "good"


def extract_title(clean_text: str) -> str | None:
    """Extract a title from clean text — first sentence or heading.

    Returns None if no usable title can be extracted.
    """
    if not clean_text:
        return None

    # Try markdown heading first
    heading_match = re.match(r"^#{1,3}\s+(.+?)$", clean_text, re.MULTILINE)
    if heading_match:
        title = heading_match.group(1).strip()
        if 10 <= len(title) <= 200 and not is_nav_icon_garbage(title):
            return title

    # Otherwise use first sentence (up to first period, question mark, or newline)
    first_line = clean_text.split("\n")[0].strip()
    if not first_line:
        return None

    # Reject nav-icon garbage as titles
    if is_nav_icon_garbage(first_line):
        # Try the second line instead
        lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
        for line in lines[1:]:
            if not is_nav_icon_garbage(line) and 10 <= len(line) <= 200:
                sentence_match = re.match(r"^(.+?[.?!])\s", line)
                if sentence_match:
                    return sentence_match.group(1).strip()
                return line
        return None

    # Skip "Skip links" concatenated navigation text
    if first_line.lower().startswith("skip links") or first_line.lower().startswith("skip to"):
        lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
        for line in lines[1:]:
            if not line.lower().startswith("skip") and 10 <= len(line) <= 200:
                return line
        return None

    # Split on sentence-ending punctuation
    sentence_match = re.match(r"^(.+?[.?!])\s", first_line)
    if sentence_match:
        title = sentence_match.group(1).strip()
        if 10 <= len(title) <= 200:
            return title

    # Fallback: use first line if it's a reasonable length
    if 10 <= len(first_line) <= 200:
        return first_line

    return None
