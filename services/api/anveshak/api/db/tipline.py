"""Tipline DB functions — Engine C Step 6.

API key lookup, tipline source management, and content insertion
for citizen-forwarded scam messages.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_LOOKUP_API_KEY = """
    SELECT ak.org_id, ak.name
    FROM api_keys ak
    WHERE ak.api_key = $1 AND ak.is_active = TRUE
"""

SQL_GET_TIPLINE_SOURCE = """
    SELECT id, credibility_score
    FROM sources
    WHERE platform = 'tipline' AND org_id = $1 AND is_active = TRUE
    LIMIT 1
"""

SQL_CREATE_TIPLINE_SOURCE = """
    INSERT INTO sources (
        id, name, url_or_handle, platform, source_type,
        credibility_score, is_active, created_at, updated_at,
        labels, org_id
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    RETURNING id, credibility_score
"""

SQL_VERIFY_TOPIC_ORG = """
    SELECT id FROM topics WHERE id = $1 AND org_id = $2 AND status = 'active'
"""

SQL_INSERT_TIPLINE_CONTENT = """
    INSERT INTO content_items (
        id, topic_id, source_id, raw_text, clean_text, language,
        content_hash, url, captured_at, credibility_score_at_capture,
        created_at, updated_at, labels, org_id
    )
    VALUES ($1, $2, $3, $4, $5, 'en', $6, $7, $8, $9, $10, $11, $12, $13)
    ON CONFLICT(content_hash) DO NOTHING
    RETURNING id
"""

def _build_labels(source_phone: str | None, forwarded_from: str | None) -> str:
    """Build labels JSON safely — no user input in format strings."""
    return json.dumps({
        "classification": "OPEN",
        "domain": "tipline",
        "owner_org": "anveshak",
        "source_phone": source_phone or "",
        "forwarded_from": forwarded_from or "",
    })


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

async def lookup_api_key(
    conn: asyncpg.Connection,
    api_key: str,
) -> Optional[dict[str, Any]]:
    """Look up API key → org_id. Returns None if key invalid/inactive."""
    row = await conn.fetchrow(SQL_LOOKUP_API_KEY, api_key)
    if row is None:
        return None
    return dict(row)


async def verify_topic_org(
    conn: asyncpg.Connection,
    topic_id: str,
    org_id: str,
) -> bool:
    """Check topic exists and belongs to org. Returns True/False."""
    row = await conn.fetchrow(SQL_VERIFY_TOPIC_ORG, topic_id, org_id)
    return row is not None


async def get_or_create_tipline_source(
    conn: asyncpg.Connection,
    org_id: str,
) -> dict[str, Any]:
    """Get or create the canonical 'tipline' source for this org."""
    row = await conn.fetchrow(SQL_GET_TIPLINE_SOURCE, org_id)
    if row is not None:
        return dict(row)

    # Create tipline source for this org
    now = datetime.now(UTC)
    source_id = str(uuid.uuid4())
    labels = '{"classification":"OPEN","domain":"tipline","owner_org":"anveshak"}'
    row = await conn.fetchrow(
        SQL_CREATE_TIPLINE_SOURCE,
        source_id,
        "Citizen Tipline",
        "whatsapp_tipline",
        "tipline",
        "tipline",
        50.0,               # default credibility for tipline
        True,
        now,
        now,
        labels,
        org_id,
    )
    return dict(row)


async def insert_tipline_content(
    conn: asyncpg.Connection,
    *,
    content_item_id: str,
    topic_id: str,
    source_id: str,
    raw_text: str,
    content_hash: str,
    credibility_score: float,
    org_id: str,
    source_phone: Optional[str] = None,
    forwarded_from: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Insert tipline content with ON CONFLICT dedup.

    Returns dict with 'id' if new, None if duplicate.
    """
    clean_text = re.sub(r"\s+", " ", raw_text.lower()).strip()
    now = datetime.now(UTC)
    labels = _build_labels(source_phone, forwarded_from)

    row = await conn.fetchrow(
        SQL_INSERT_TIPLINE_CONTENT,
        content_item_id,
        topic_id,
        source_id,
        raw_text,
        clean_text,
        content_hash,
        None,                  # url — tipline has no external URL
        now,                   # captured_at
        credibility_score,
        now,                   # created_at
        now,                   # updated_at
        labels,
        org_id,
    )
    if row is None:
        return None
    return dict(row)
