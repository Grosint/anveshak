"""Intelligence endpoints — entity co-occurrence, topic similarity, source discovery.

CPU-feasible intelligence features built on existing NER output and embeddings.
"""
from __future__ import annotations

from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..auth.rbac import require_role
from ..db.pool import get_db
from ..db import audit as audit_db
from ..db import topics as topics_db

import json
from pathlib import Path

import geonamescache

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["intelligence"])

# ---------------------------------------------------------------------------
# Lightweight geocoder (reuses same geonamescache + custom overlay as reporter)
# ---------------------------------------------------------------------------
_gc = geonamescache.GeonamesCache()
_CITIES: dict[str, dict[str, Any]] = {}
_COUNTRIES: dict[str, dict[str, Any]] = {}
_CUSTOM_LOCS: dict[str, tuple[float, float]] = {}

for _k, _city in _gc.get_cities().items():
    _n = _city["name"].lower()
    if _n not in _CITIES or _city.get("population", 0) > _CITIES[_n].get("population", 0):
        _CITIES[_n] = _city

for _k, _country in _gc.get_countries().items():
    _COUNTRIES[_country["name"].lower()] = _country

_custom_path = Path(__file__).resolve().parents[5] / "infra" / "configs" / "geocoder" / "custom_locations.json"
if not _custom_path.is_file():
    _custom_path = Path("/workspace/infra/configs/geocoder/custom_locations.json")
if _custom_path.is_file():
    try:
        for _name, _coords in json.loads(_custom_path.read_text()).items():
            _CUSTOM_LOCS[_name.lower()] = (float(_coords[0]), float(_coords[1]))
    except Exception:
        pass


import re as _re

# Common aliases → canonical name (lowercase keys, lowercase values)
_ALIASES: dict[str, str] = {
    "us": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "usa": "united states",
    "the united states": "united states",
    "the us": "united states",
    "uk": "united kingdom",
    "the uk": "united kingdom",
    "the united kingdom": "united kingdom",
    "the middle east": "middle east",
    "the gulf": "gulf",
    "the caribbean": "caribbean",
    "the netherlands": "the netherlands",
    "netherlands": "the netherlands",
    "the philippines": "philippines",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "madras": "chennai",
    "trivandrum": "thiruvananthapuram",
    "pondicherry": "puducherry",
    "india delhi": "delhi",
    "new delhi": "delhi",
}

# NER noise patterns — entities that look like locations but aren't
_NOISE_RE = _re.compile(
    r"""
    ^[\W\d]+$           |  # purely punctuation/digits
    ^.{0,2}$            |  # too short (DM, US handled by alias)
    [<>"=]              |  # HTML artifacts (dir="ltr", City News">...)
    ^\+                 |  # +domian
    ^the\s*$               # bare "the"
    """,
    _re.VERBOSE | _re.IGNORECASE,
)

# Known non-location GPE/LOC false positives from spaCy
_NOISE_NAMES: set[str] = {
    "modi", "khan", "nadaprabhu", "indus", "dm", "tamil",
    "hindu", "muslim", "congress", "bjp", "aap",
}


def _normalize_location(name: str) -> str:
    """Normalize location name: strip articles, resolve aliases."""
    key = name.lower().strip()
    # Check alias table first
    if key in _ALIASES:
        return _ALIASES[key]
    # Strip leading "the " for geographic features
    if key.startswith("the "):
        stripped = key[4:]
        if stripped in _ALIASES:
            return _ALIASES[stripped]
        return stripped
    return key


def _is_noise(name: str) -> bool:
    """Return True if entity_text is clearly not a real location."""
    key = name.lower().strip()
    # Known aliases are never noise (handles "US", "UK" etc.)
    if key in _ALIASES:
        return False
    if _NOISE_RE.search(name):
        return True
    if key in _NOISE_NAMES:
        return True
    return False


def _geocode(names: list[str]) -> dict[str, tuple[float, float]]:
    """Return {name: (lat, lon)} for recognised locations. Unknown names skipped.

    Applies alias normalization (US → United States, the Gulf → Gulf),
    noise filtering (HTML artifacts, person names, too-short strings),
    and multi-tier lookup (custom → cities → countries).
    """
    result: dict[str, tuple[float, float]] = {}
    for name in names:
        if _is_noise(name):
            continue
        key = _normalize_location(name)
        if key in _CUSTOM_LOCS:
            result[name] = _CUSTOM_LOCS[key]
        elif key in _CITIES:
            c = _CITIES[key]
            result[name] = (float(c["latitude"]), float(c["longitude"]))
        elif key in _COUNTRIES:
            capital = _COUNTRIES[key].get("capital", "").lower()
            if capital in _CITIES:
                c = _CITIES[capital]
                result[name] = (float(c["latitude"]), float(c["longitude"]))
    return result


# Display names for normalized location keys
_DISPLAY_NAMES: dict[str, str] = {
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "the netherlands": "The Netherlands",
    "sri lanka": "Sri Lanka",
    "new delhi": "New Delhi",
    "middle east": "Middle East",
}


def _location_display_name(key: str) -> str:
    """Convert normalized lowercase key to display name."""
    if key in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[key]
    return key.title()


def _merge_location_rows(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge location rows by normalized name + entity_type.

    Collapses alias variants (us, united states, the united states → united states).
    SQL already case-folds via LOWER(), this handles alias merging.
    Uses (normalized_name, entity_type) as merge key to keep GPE/LOC/FAC separate.
    """
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        norm = _normalize_location(row["entity_key"])
        etype = row["entity_type"]
        merge_key = (norm, etype)
        if merge_key in merged:
            m = merged[merge_key]
            m["mention_count"] += row["mention_count"]
            # source_count: max (sources overlap across text variants)
            if row["source_count"] > m["source_count"]:
                m["source_count"] = row["source_count"]
            # latest_mention: keep most recent
            if row["latest_mention"] and (
                not m["latest_mention"] or row["latest_mention"] > m["latest_mention"]
            ):
                m["latest_mention"] = row["latest_mention"]
        else:
            merged[merge_key] = {
                "entity_key": norm,
                "entity_type": etype,
                "mention_count": row["mention_count"],
                "source_count": row["source_count"],
                "latest_mention": row["latest_mention"],
            }
    # Flatten to dict keyed by normalized name
    # Same name + different entity_type → separate entries with type suffix
    seen_names: dict[str, int] = {}
    for norm, _ in merged:
        seen_names[norm] = seen_names.get(norm, 0) + 1
    result: dict[str, dict[str, Any]] = {}
    for (norm, etype), data in merged.items():
        rkey = f"{norm}:{etype}" if seen_names[norm] > 1 else norm
        result[rkey] = data
    return result


# ---------------------------------------------------------------------------
# SQL queries
# ---------------------------------------------------------------------------

SQL_ENTITY_COOCCURRENCE = """
    SELECT e1.entity_text AS entity_a,
           e1.entity_type AS type_a,
           e2.entity_text AS entity_b,
           e2.entity_type AS type_b,
           COUNT(DISTINCT e1.content_item_id) AS count
    FROM extracted_entities e1
    JOIN extracted_entities e2
        ON e1.content_item_id = e2.content_item_id
        AND e1.id < e2.id
    JOIN content_items ci ON e1.content_item_id = ci.id
    WHERE ci.topic_id = $1
      AND e1.entity_type IN ('PERSON', 'ORG', 'FAC')
      AND e2.entity_type IN ('PERSON', 'ORG', 'FAC')
      AND e1.entity_text NOT LIKE '%%<%%' AND e1.entity_text NOT LIKE '%%>%%'
      AND e1.entity_text NOT LIKE '%%=%%' AND e1.entity_text NOT LIKE '%%href%%'
      AND e2.entity_text NOT LIKE '%%<%%' AND e2.entity_text NOT LIKE '%%>%%'
      AND e2.entity_text NOT LIKE '%%=%%' AND e2.entity_text NOT LIKE '%%href%%'
      AND LENGTH(e1.entity_text) >= 2
      AND LENGTH(e2.entity_text) >= 2
    GROUP BY e1.entity_text, e1.entity_type, e2.entity_text, e2.entity_type
    HAVING COUNT(DISTINCT e1.content_item_id) >= $2
    ORDER BY count DESC
    LIMIT $3
"""

SQL_TOPIC_SIMILARITY = """
    WITH topic_centroid AS (
        SELECT AVG(nc.embedding_centroid) AS centroid
        FROM narrative_clusters nc
        WHERE nc.topic_id = $1
          AND nc.embedding_centroid IS NOT NULL
    ),
    other_topics AS (
        SELECT t.id, t.name, t.status,
               AVG(nc2.embedding_centroid) AS centroid
        FROM topics t
        JOIN narrative_clusters nc2 ON nc2.topic_id = t.id
        WHERE t.id != $1
          AND t.status = 'active'
          AND nc2.embedding_centroid IS NOT NULL
          AND t.org_id = (SELECT org_id FROM topics WHERE id = $1)
        GROUP BY t.id, t.name, t.status
    )
    SELECT ot.id, ot.name, ot.status,
           1 - (ot.centroid <=> tc.centroid) AS similarity
    FROM other_topics ot, topic_centroid tc
    WHERE tc.centroid IS NOT NULL
    ORDER BY ot.centroid <=> tc.centroid
    LIMIT $2
"""

SQL_OUTBOUND_LINKS = r"""
    SELECT DISTINCT ci.url AS source_url,
           unnest(
               regexp_matches(ci.clean_text, 'https?://[^\s<>"'']+', 'g')
           ) AS outbound_url
    FROM content_items ci
    WHERE ci.topic_id = $1
      AND ci.clean_text ~ 'https?://'
    LIMIT 500
"""

SQL_EXISTING_SOURCE_URLS = """
    SELECT url_or_handle FROM sources WHERE is_active = TRUE
"""

SQL_TOPIC_LOCATION_MAP = """
    SELECT LOWER(ee.entity_text) AS entity_key,
           ee.entity_type,
           COUNT(DISTINCT ee.content_item_id) AS mention_count,
           COUNT(DISTINCT ci.source_id) AS source_count,
           MAX(ci.captured_at) AS latest_mention
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ee.entity_type IN ('GPE', 'LOC', 'FAC')
      AND ee.confidence >= 0.8
    GROUP BY LOWER(ee.entity_text), ee.entity_type
    HAVING COUNT(DISTINCT ee.content_item_id) >= $2
    ORDER BY mention_count DESC
    LIMIT $3
"""

SQL_CLUSTER_DUPLICATES = """
    SELECT nc1.id AS cluster_a_id,
           nc1.label AS cluster_a_label,
           nc1.item_count AS cluster_a_items,
           nc2.id AS cluster_b_id,
           nc2.label AS cluster_b_label,
           nc2.item_count AS cluster_b_items,
           1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) AS similarity
    FROM narrative_clusters nc1
    JOIN narrative_clusters nc2
        ON nc1.topic_id = nc2.topic_id
        AND nc1.id < nc2.id
    WHERE nc1.topic_id = $1
      AND nc1.embedding_centroid IS NOT NULL
      AND nc2.embedding_centroid IS NOT NULL
      AND 1 - (nc1.embedding_centroid <=> nc2.embedding_centroid) >= $2
    ORDER BY similarity DESC
    LIMIT $3
"""


# ---------------------------------------------------------------------------
# Social Media Analytics — Topic Stats, Top Authors, Network Graph
# ---------------------------------------------------------------------------

SQL_TOPIC_PLATFORM_STATS = """
    SELECT s.platform,
           COUNT(*) AS post_count,
           COUNT(DISTINCT ci.source_id) AS source_count,
           MAX(ci.captured_at) AS latest_post
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.captured_at >= NOW() - make_interval(days => $2)
    GROUP BY s.platform
    ORDER BY post_count DESC
"""

SQL_TOPIC_VOLUME_TIMELINE = """
    SELECT DATE(captured_at) AS date,
           COUNT(*) AS count
    FROM content_items
    WHERE topic_id = $1
      AND captured_at >= NOW() - make_interval(days => $2)
    GROUP BY DATE(captured_at)
    ORDER BY date ASC
"""

SQL_TOPIC_ENGAGEMENT_SUMMARY = """
    SELECT
        SUM(COALESCE((labels->'engagement'->>'likes')::int, 0)) AS total_likes,
        SUM(COALESCE((labels->'engagement'->>'comments')::int, 0)) AS total_comments,
        SUM(COALESCE((labels->'engagement'->>'shares')::int, 0)
          + COALESCE((labels->'engagement'->>'retweets')::int, 0)
          + COALESCE((labels->'engagement'->>'reposts')::int, 0)
          + COALESCE((labels->'engagement'->>'forwards')::int, 0)) AS total_shares,
        SUM(COALESCE((labels->'engagement'->>'views')::int, 0)) AS total_views,
        COUNT(*) FILTER (WHERE labels->'engagement' IS NOT NULL) AS posts_with_engagement
    FROM content_items
    WHERE topic_id = $1
      AND captured_at >= NOW() - make_interval(days => $2)
"""

SQL_TOP_AUTHORS = """
    SELECT
        ci.labels->>'author_handle' AS author_handle,
        ci.labels->>'author_id' AS author_id,
        s.platform,
        COUNT(*) AS post_count,
        SUM(COALESCE((ci.labels->'engagement'->>'likes')::int, 0)) AS total_likes,
        SUM(COALESCE((ci.labels->'engagement'->>'views')::int, 0)) AS total_views,
        SUM(COALESCE((ci.labels->'engagement'->>'shares')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'retweets')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'reposts')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'forwards')::int, 0)) AS total_shares,
        AVG(COALESCE((ci.labels->'sentiment'->>'compound')::float, 0)) AS avg_sentiment
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.captured_at >= NOW() - make_interval(days => $2)
      AND ci.labels->>'author_handle' IS NOT NULL
    GROUP BY ci.labels->>'author_handle', ci.labels->>'author_id', s.platform
    ORDER BY
        SUM(COALESCE((ci.labels->'engagement'->>'likes')::int, 0))
        + SUM(COALESCE((ci.labels->'engagement'->>'views')::int, 0))
        + SUM(COALESCE((ci.labels->'engagement'->>'shares')::int, 0)
            + COALESCE((ci.labels->'engagement'->>'retweets')::int, 0)
            + COALESCE((ci.labels->'engagement'->>'reposts')::int, 0)
            + COALESCE((ci.labels->'engagement'->>'forwards')::int, 0)) * 5
        DESC
    LIMIT $3
"""

SQL_FORWARD_NETWORK = """
    SELECT
        REPLACE(labels->>'author_handle', '@', '') AS source_author,
        forwarded_from_channel_name AS target_author,
        'forward' AS edge_type,
        COUNT(*) AS weight
    FROM content_items
    WHERE topic_id = $1
      AND forwarded_from_channel_name IS NOT NULL
      AND labels->>'author_handle' IS NOT NULL
    GROUP BY source_author, target_author
    HAVING COUNT(*) >= $2
    ORDER BY weight DESC
    LIMIT $3
"""

SQL_AUTHOR_POST_COUNTS = """
    SELECT
        REPLACE(ci.labels->>'author_handle', '@', '') AS author_handle,
        s.platform,
        COUNT(*) AS post_count
    FROM content_items ci
    JOIN sources s ON ci.source_id = s.id
    WHERE ci.topic_id = $1
      AND ci.captured_at >= NOW() - INTERVAL '30 days'
      AND ci.labels->>'author_handle' IS NOT NULL
    GROUP BY REPLACE(ci.labels->>'author_handle', '@', ''), s.platform
    ORDER BY post_count DESC
    LIMIT $2
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/topics/{topic_id}/entity-graph")
async def get_entity_cooccurrence(
    topic_id: str,
    min_count: int = Query(2, ge=1, description="Minimum co-occurrence count"),
    limit: int = Query(100, ge=1, le=500, description="Max edges to return"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Entity co-occurrence graph — who appears with whom.

    Returns edges (entity pairs) with co-occurrence frequency.
    Useful for identifying relationships between actors, organizations, and locations.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await db.fetch(SQL_ENTITY_COOCCURRENCE, topic_id, min_count, limit)
    edges = [dict(r) for r in rows]

    # Extract unique nodes
    nodes: dict[str, str] = {}
    for edge in edges:
        nodes[edge["entity_a"]] = edge["type_a"]
        nodes[edge["entity_b"]] = edge["type_b"]

    return {
        "topic_id": topic_id,
        "nodes": [{"entity": k, "type": v} for k, v in nodes.items()],
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@router.get("/topics/{topic_id}/location-map")
async def get_location_map(
    topic_id: str,
    min_mentions: int = Query(2, ge=1, description="Minimum mention count"),
    limit: int = Query(100, ge=1, le=500, description="Max locations"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Location heatmap — geocoded GPE/LOC/FACILITY entities from NER.

    Returns GeoJSON FeatureCollection with mention_count in properties.
    Uses offline geonamescache + custom defence overlay for geocoding.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await db.fetch(SQL_TOPIC_LOCATION_MAP, topic_id, min_mentions, limit)

    # Merge case variants + aliases (India/india, US/the United States)
    merged = _merge_location_rows([dict(r) for r in rows])

    # Geocode merged normalized names
    location_names = [data["entity_key"] for data in merged.values()]
    coords = _geocode(location_names)

    features: list[dict[str, Any]] = []
    for key, data in merged.items():
        norm = data["entity_key"]
        if norm not in coords:
            continue
        lat, lon = coords[norm]
        latest = data.get("latest_mention")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "name": _location_display_name(norm),
                "entity_type": data.get("entity_type", "GPE"),
                "mention_count": data.get("mention_count", 1),
                "source_count": data.get("source_count", 1),
                "latest_mention": latest.isoformat() if latest else None,
            },
        })

    unresolved = [
        _location_display_name(data["entity_key"])
        for data in merged.values()
        if data["entity_key"] not in coords
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_extracted": len(merged),
            "geocoded": len(features),
            "unresolved": sorted(set(unresolved)),
        },
    }


@router.get("/topics/{topic_id}/similar")
async def get_similar_topics(
    topic_id: str,
    limit: int = Query(5, ge=1, le=20, description="Max similar topics"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict[str, Any]]:
    """Find topics with similar narrative clusters by centroid distance.

    Uses pgvector cosine similarity on cluster embedding centroids.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await db.fetch(SQL_TOPIC_SIMILARITY, topic_id, limit)
    return [dict(r) for r in rows]


@router.get("/topics/{topic_id}/discover-sources")
async def discover_sources(
    topic_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Extract outbound URLs from scraped content and suggest new sources.

    Returns domains sorted by citation frequency (how many content items
    reference each domain). Filters out already-registered sources.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    from urllib.parse import urlparse
    from collections import Counter

    # Fetch outbound links from content
    link_rows = await db.fetch(SQL_OUTBOUND_LINKS, topic_id)
    domain_counts: Counter[str] = Counter()
    for row in link_rows:
        url = row["outbound_url"]
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                domain_counts[parsed.netloc] += 1
        except Exception:
            pass

    # Fetch existing source domains
    existing_rows = await db.fetch(SQL_EXISTING_SOURCE_URLS)
    existing_domains = set()
    for row in existing_rows:
        try:
            parsed = urlparse(row["url_or_handle"])
            if parsed.netloc:
                existing_domains.add(parsed.netloc)
        except Exception:
            existing_domains.add(row["url_or_handle"])

    # Filter and sort by frequency
    new_domains = {
        domain: count
        for domain, count in domain_counts.items()
        if domain not in existing_domains
    }
    suggestions = sorted(new_domains.items(), key=lambda x: x[1], reverse=True)[:50]

    return {
        "topic_id": topic_id,
        "suggestions": [
            {"domain": domain, "citation_count": count}
            for domain, count in suggestions
        ],
        "total_outbound_domains": len(domain_counts),
        "already_registered": len(set(domain_counts) & existing_domains),
    }


@router.get("/topics/{topic_id}/cluster-duplicates")
async def get_cluster_duplicates(
    topic_id: str,
    min_similarity: float = Query(0.85, ge=0.5, le=1.0, description="Min cosine similarity"),
    limit: int = Query(20, ge=1, le=100, description="Max pairs"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> list[dict[str, Any]]:
    """Detect near-duplicate clusters by centroid cosine similarity.

    Returns pairs of clusters that may be duplicates, sorted by similarity.
    """
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await db.fetch(SQL_CLUSTER_DUPLICATES, topic_id, min_similarity, limit)
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Cluster merge
# ---------------------------------------------------------------------------

SQL_REASSIGN_CONTENT_ITEMS = """
    UPDATE content_items
    SET narrative_cluster_id = $1, updated_at = NOW()
    WHERE narrative_cluster_id = $2
"""

SQL_UPDATE_CLUSTER_COUNTS = """
    UPDATE narrative_clusters
    SET item_count = (
            SELECT COUNT(*) FROM content_items WHERE narrative_cluster_id = $1
        ),
        independent_source_count = (
            SELECT COUNT(DISTINCT s.platform)
            FROM content_items ci
            JOIN sources s ON ci.source_id = s.id
            WHERE ci.narrative_cluster_id = $1
        ),
        updated_at = NOW()
    WHERE id = $1
"""

SQL_DELETE_CLUSTER = """
    DELETE FROM narrative_clusters WHERE id = $1
"""

SQL_GET_CLUSTER = """
    SELECT id, topic_id, label, item_count FROM narrative_clusters WHERE id = $1
"""


@router.post("/clusters/merge")
async def merge_clusters(
    request: Request,
    keep_id: str = Body(..., description="Cluster ID to keep (absorbs items)"),
    remove_id: str = Body(..., description="Cluster ID to remove (items reassigned)"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Merge two clusters — reassign content items from remove_id to keep_id, delete remove_id.

    Both clusters must belong to the same topic.
    """
    keep = await db.fetchrow(SQL_GET_CLUSTER, keep_id)
    remove = await db.fetchrow(SQL_GET_CLUSTER, remove_id)

    if not keep:
        raise HTTPException(status_code=404, detail=f"Cluster {keep_id} not found")
    if not remove:
        raise HTTPException(status_code=404, detail=f"Cluster {remove_id} not found")
    if keep["topic_id"] != remove["topic_id"]:
        raise HTTPException(status_code=400, detail="Clusters must belong to the same topic")

    async with db.transaction():
        # Reassign content items from remove → keep
        await db.execute(SQL_REASSIGN_CONTENT_ITEMS, keep_id, remove_id)
        # Update counts on the surviving cluster
        await db.execute(SQL_UPDATE_CLUSTER_COUNTS, keep_id)
        # Delete the absorbed cluster
        await db.execute(SQL_DELETE_CLUSTER, remove_id)

    log.info(
        "intelligence.clusters_merged",
        keep_id=keep_id,
        remove_id=remove_id,
        topic_id=keep["topic_id"],
    )
    await audit_db.log_action(
        db, user["sub"], "cluster.merge", "cluster", keep_id,
        {"removed_cluster_id": remove_id, "topic_id": keep["topic_id"]},
        request.client.host if request.client else "",
    )

    return {
        "merged": True,
        "kept_cluster_id": keep_id,
        "removed_cluster_id": remove_id,
        "topic_id": keep["topic_id"],
    }


# ---------------------------------------------------------------------------
# Social Media Analytics Routes
# ---------------------------------------------------------------------------

@router.get("/topics/{topic_id}/stats")
async def get_topic_stats(
    topic_id: str,
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> dict[str, Any]:
    """Topic analytics — platform breakdown, volume timeline, engagement summary."""
    await topics_db.verify_topic_access(db, topic_id, user)

    platform_rows = await db.fetch(SQL_TOPIC_PLATFORM_STATS, topic_id, days)
    volume_rows = await db.fetch(SQL_TOPIC_VOLUME_TIMELINE, topic_id, days)
    eng_row = await db.fetchrow(SQL_TOPIC_ENGAGEMENT_SUMMARY, topic_id, days)

    return {
        "topic_id": topic_id,
        "days": days,
        "platforms": [
            {
                "platform": r["platform"],
                "post_count": r["post_count"],
                "source_count": r["source_count"],
                "latest_post": r["latest_post"].isoformat() if r["latest_post"] else None,
            }
            for r in platform_rows
        ],
        "volume_timeline": [
            {"date": str(r["date"]), "count": r["count"]}
            for r in volume_rows
        ],
        "engagement": {
            "total_likes": eng_row["total_likes"] or 0,
            "total_comments": eng_row["total_comments"] or 0,
            "total_shares": eng_row["total_shares"] or 0,
            "total_views": eng_row["total_views"] or 0,
            "posts_with_engagement": eng_row["posts_with_engagement"] or 0,
        } if eng_row else {"total_likes": 0, "total_comments": 0, "total_shares": 0, "total_views": 0, "posts_with_engagement": 0},
    }


@router.get("/topics/{topic_id}/top-authors")
async def get_top_authors(
    topic_id: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("viewer", "analyst", "admin")),
) -> list[dict[str, Any]]:
    """Top content authors ranked by engagement impact."""
    await topics_db.verify_topic_access(db, topic_id, user)
    rows = await db.fetch(SQL_TOP_AUTHORS, topic_id, days, limit)
    return [
        {
            "author_handle": r["author_handle"],
            "author_id": r["author_id"],
            "platform": r["platform"],
            "post_count": r["post_count"],
            "total_likes": r["total_likes"] or 0,
            "total_views": r["total_views"] or 0,
            "total_shares": r["total_shares"] or 0,
            "avg_sentiment": round(float(r["avg_sentiment"] or 0), 3),
        }
        for r in rows
    ]


@router.get("/topics/{topic_id}/network-graph")
async def get_network_graph(
    topic_id: str,
    min_weight: int = Query(1, ge=1, description="Minimum edge weight"),
    limit: int = Query(200, ge=1, le=500, description="Max edges"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(require_role("analyst", "admin")),
) -> dict[str, Any]:
    """Social network graph — forwarding chains between authors/channels."""
    await topics_db.verify_topic_access(db, topic_id, user)

    fwd_rows = await db.fetch(SQL_FORWARD_NETWORK, topic_id, min_weight, limit)

    # Build edges first, then only include connected nodes
    edges = []
    connected_ids: set[str] = set()
    for r in fwd_rows:
        src = r["source_author"]
        tgt = r["target_author"]
        connected_ids.add(src)
        connected_ids.add(tgt)
        # Swap: show info flow direction (origin → forwarder)
        edges.append({
            "source": tgt,
            "target": src,
            "edge_type": r["edge_type"],
            "weight": r["weight"],
        })

    # Only fetch post counts for connected authors
    author_rows = await db.fetch(SQL_AUTHOR_POST_COUNTS, topic_id, 100)

    nodes: dict[str, dict[str, Any]] = {}
    for r in author_rows:
        handle = r["author_handle"]
        if handle in connected_ids:
            nodes[handle] = {
                "id": handle,
                "platform": r["platform"],
                "post_count": r["post_count"],
            }

    # Add missing nodes referenced by edges but not in author_rows
    for nid in connected_ids:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "platform": "unknown", "post_count": 0}

    return {
        "topic_id": topic_id,
        "nodes": list(nodes.values()),
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
