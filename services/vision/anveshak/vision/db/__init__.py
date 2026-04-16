"""Database helpers for vision service — asyncpg connection pool and SQL operations.

All SQL is defined as module-level constants (CLAUDE.md patterns + testability).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC
from typing import Optional

import asyncpg
import structlog

from ..settings import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SQL_GET_MEDIA_ASSET = """
    SELECT ma.id, ma.content_item_id, ma.asset_type, ma.storage_path,
           ma.content_hash,
           ci.topic_id
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.id = $1
"""

SQL_GET_TOPIC_CLIP_CATEGORIES = """
    SELECT clip_categories FROM topics WHERE id = $1
"""

SQL_UPDATE_MEDIA_ASSET_EXIF_PHASH = """
    UPDATE media_assets
    SET exif_data = $1::jsonb,
        phash     = $2
    WHERE id = $3
"""

SQL_INSERT_VISION_RESULT = """
    INSERT INTO vision_results (
        id, media_asset_id,
        yolo_detections, clip_labels,
        deepfake_score, deepfake_model,
        synthetic_probability,
        processed_at, labels
    )
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7, $8,
            '{"classification":"OPEN","domain":"vision","owner_org":"anveshak"}'::jsonb)
    ON CONFLICT (media_asset_id) DO UPDATE
    SET yolo_detections     = EXCLUDED.yolo_detections,
        clip_labels         = EXCLUDED.clip_labels,
        deepfake_score      = EXCLUDED.deepfake_score,
        deepfake_model      = EXCLUDED.deepfake_model,
        synthetic_probability = EXCLUDED.synthetic_probability,
        processed_at        = EXCLUDED.processed_at
"""

SQL_TAG_CONTENT_ITEM_LABELS = """
    UPDATE content_items
    SET labels = labels || $1::jsonb,
        updated_at = $2
    WHERE id = $3
"""

SQL_GET_MEDIA_ASSETS_BY_PHASH_RANGE = """
    SELECT ma.id, ma.content_item_id, ma.storage_path,
           ma.content_hash, ma.asset_type,
           ci.url, ci.topic_id,
           BIT_COUNT(ma.phash # $1::bigint) AS hamming_distance
    FROM media_assets ma
    JOIN content_items ci ON ci.id = ma.content_item_id
    WHERE ma.phash IS NOT NULL
      AND BIT_COUNT(ma.phash # $1::bigint) <= $2
    ORDER BY BIT_COUNT(ma.phash # $1::bigint)
    LIMIT 20
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
# Connection pool lifecycle
# ---------------------------------------------------------------------------

async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.postgres_url, min_size=2, max_size=5)


async def get_media_asset(conn: asyncpg.Connection, media_asset_id: str) -> Optional[asyncpg.Record]:
    return await conn.fetchrow(SQL_GET_MEDIA_ASSET, media_asset_id)


async def get_topic_clip_categories(conn: asyncpg.Connection, topic_id: str) -> list[str]:
    row = await conn.fetchrow(SQL_GET_TOPIC_CLIP_CATEGORIES, topic_id)
    return list(row["clip_categories"]) if row and row["clip_categories"] else []


async def update_media_asset_exif_phash(
    conn: asyncpg.Connection,
    media_asset_id: str,
    exif_data: Optional[dict],
    phash: Optional[int],
) -> None:
    exif_json = json.dumps(exif_data or {})
    await conn.execute(SQL_UPDATE_MEDIA_ASSET_EXIF_PHASH, exif_json, phash, media_asset_id)


async def insert_vision_result(
    conn: asyncpg.Connection,
    media_asset_id: str,
    yolo_detections: list[dict],
    clip_labels: list[dict],
    deepfake_score: float,
    deepfake_model: str,
    synthetic_probability: Optional[float],
) -> str:
    """Insert or update vision_results row. Returns the result id."""
    result_id = str(uuid.uuid4())
    await conn.execute(
        SQL_INSERT_VISION_RESULT,
        result_id,
        media_asset_id,
        json.dumps(yolo_detections),
        json.dumps(clip_labels),
        deepfake_score,
        deepfake_model,
        synthetic_probability,
        datetime.now(UTC),
    )
    return result_id


async def tag_content_item(
    conn: asyncpg.Connection,
    content_item_id: str,
    extra_labels: dict,
) -> None:
    """Merge extra_labels into content_items.labels JSONB (criteria 4.11)."""
    await conn.execute(
        SQL_TAG_CONTENT_ITEM_LABELS,
        json.dumps(extra_labels),
        datetime.now(UTC),
        content_item_id,
    )


async def reverse_search_by_phash(
    conn: asyncpg.Connection,
    phash: int,
    threshold: int,
) -> list[asyncpg.Record]:
    """Find near-duplicate media assets by Hamming distance on pHash."""
    return await conn.fetch(SQL_GET_MEDIA_ASSETS_BY_PHASH_RANGE, phash, threshold)


async def get_vision_results_for_content(
    conn: asyncpg.Connection,
    content_item_id: str,
) -> list[asyncpg.Record]:
    return await conn.fetch(SQL_GET_VISION_RESULTS_FOR_CONTENT, content_item_id)
