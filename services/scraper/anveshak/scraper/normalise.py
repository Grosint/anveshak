"""Text normalisation and content hash computation.

SHA-256 of normalised clean_text is the mandatory deduplication key (AGENTS.md rule 3).
"""

import hashlib
import re


def normalise_text(text: str) -> str:
    """Lowercase and collapse whitespace — canonical form for content hashing."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of normalised text.

    This is the content_hash stored in content_items and used for
    ON CONFLICT(content_hash) DO NOTHING deduplication.
    """
    return hashlib.sha256(normalise_text(text).encode("utf-8")).hexdigest()
