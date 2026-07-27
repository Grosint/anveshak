"""Vision repository — media_assets and vision_results SQL for the API gateway."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, UTC
from typing import Any, Optional

import asyncpg

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_INSERT_MEDIA_ASSET = """
    INSERT INTO media_assets (
        id, content_item_id, asset_type, storage_path, content_hash, labels
    )
    VALUES ($1, $2, $3, $4, $5,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (content_hash) DO NOTHING
    RETURNING id
"""

SQL_GET_MEDIA_ASSET_BY_HASH = "SELECT id FROM media_assets WHERE content_hash = $1"

SQL_PHASH_REVERSE_SEARCH = """
    SELECT ma.id, ma.content_item_id, ma.storage_path, ma.asset_type,
           ma.content_hash,
           ci.url, ci.topic_id,
           BIT_COUNT(ma.phash # $1::bigint) AS hamming_distance
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.phash IS NOT NULL
      AND BIT_COUNT(ma.phash # $1::bigint) <= $2
    ORDER BY BIT_COUNT(ma.phash # $1::bigint)
    LIMIT 20
"""

_MANUAL_SOURCE_ID = "00000000-0000-0000-0000-000000000001"

SQL_UPSERT_MANUAL_SOURCE = """
    INSERT INTO sources (id, name, url_or_handle, platform, credibility_score,
                         auto_score_enabled, labels)
    VALUES ($1, 'Manual Upload', 'manual://upload', 'manual', 50.0, false,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (id) DO NOTHING
"""

SQL_INSERT_STUB_CONTENT_ITEM = """
    INSERT INTO content_items (id, source_id, raw_text, clean_text, content_hash, topic_id, labels)
    VALUES ($1, $2, $3, $3, $4, $5,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (content_hash) DO NOTHING
    RETURNING id
"""

SQL_GET_STUB_CONTENT_ITEM_BY_HASH = """
    SELECT id FROM content_items WHERE content_hash = $1
"""

SQL_UPSERT_TOPIC_CONTENT_ITEM = """
    INSERT INTO topic_content_items (topic_id, content_item_id, similarity_score, assigned_at)
    VALUES ($1, $2, 1.0, NOW())
    ON CONFLICT (topic_id, content_item_id) DO NOTHING
"""

SQL_GET_VISION_RESULTS_FOR_CONTENT = """
    SELECT vr.id, vr.media_asset_id, vr.yolo_detections, vr.clip_labels,
           vr.deepfake_score, vr.deepfake_model, vr.synthetic_probability,
           vr.processed_at,
           ma.storage_path, ma.asset_type, ma.exif_data, ma.phash, ma.content_hash
    FROM vision_results vr
    JOIN media_assets ma ON ma.id = vr.media_asset_id
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ci.id = $1
"""

# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------

async def get_media_asset_by_hash(
    conn: asyncpg.Connection, content_hash: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(SQL_GET_MEDIA_ASSET_BY_HASH, content_hash)
    return dict(row) if row else None


async def insert_media_asset(
    conn: asyncpg.Connection,
    asset_id: str,
    content_item_id: Optional[str],
    asset_type: str,
    storage_path: str,
    content_hash: str,
) -> dict[str, Any] | None:
    """Insert media asset with ON CONFLICT DO NOTHING. Returns row if inserted."""
    row = await conn.fetchrow(
        SQL_INSERT_MEDIA_ASSET,
        asset_id, content_item_id, asset_type, storage_path, content_hash,
    )
    return dict(row) if row else None


async def phash_reverse_search(
    conn: asyncpg.Connection,
    phash_int: int,
    threshold: int,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_PHASH_REVERSE_SEARCH, phash_int, threshold)
    return [dict(r) for r in rows]


async def get_vision_results_for_content(
    conn: asyncpg.Connection, content_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(SQL_GET_VISION_RESULTS_FOR_CONTENT, content_id)
    return [dict(r) for r in rows]


async def get_or_create_stub_content_item(
    conn: asyncpg.Connection,
    content_hash: str,
    filename: str,
    topic_id: Optional[str] = None,
) -> str:
    """Return content_item.id for an ad-hoc upload.

    Creates a 'manual-upload' source stub and a minimal content_item so that
    media_assets.content_item_id (NOT NULL FK) is always satisfied for standalone
    vision analysis requests.

    When topic_id is provided, the content_item is linked to the topic so it
    appears in the topic workspace.
    """
    await conn.execute(SQL_UPSERT_MANUAL_SOURCE, _MANUAL_SOURCE_ID)

    stub_text = f"[manual upload: {filename}]"
    stub_hash = hashlib.sha256(f"manual:{content_hash}".encode()).hexdigest()
    stub_id = str(uuid.uuid4())

    row = await conn.fetchrow(
        SQL_INSERT_STUB_CONTENT_ITEM,
        stub_id, _MANUAL_SOURCE_ID, stub_text, stub_hash, topic_id,
    )
    if row:
        content_item_id = str(row["id"])
    else:
        # ON CONFLICT — fetch existing
        existing = await conn.fetchrow(SQL_GET_STUB_CONTENT_ITEM_BY_HASH, stub_hash)
        content_item_id = str(existing["id"])

    # Link to topic via join table (Pipeline Data Threading — dual-path query)
    if topic_id:
        await conn.execute(SQL_UPSERT_TOPIC_CONTENT_ITEM, topic_id, content_item_id)

    return content_item_id
