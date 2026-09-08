"""Actor View repository — issue #35.

An Actor View is a query, not a stored entity. There is no actor table and
no persistent per-person record: a handle is an Identifier, and everything
here is derived from content_items on demand. That is what keeps the
retention posture defensible, and it is why this module only reads.

Every query is scoped by both topic_id and org_id. A handle is reachable by
name rather than by an opaque identifier, so scoping cannot rely on the
caller having looked the row up first.
"""

from __future__ import annotations

from typing import Any

from anveshak.db import DBConnection

# Platforms whose content is publicly available.
#
# An allowlist, not a denylist. A denylist of ('tipline') would have let a
# WhatsApp group through, and the WhatsApp adapter records the display name
# of every group member as author_handle. That would build a per-person
# dossier out of a private group, which is the opposite of this view's
# stated posture. A new adapter has to be added here deliberately.
_PUBLIC_PLATFORMS = "('web', 'rss', 'twitter', 'reddit', 'bluesky', 'youtube', 'telegram')"

# Matching is on the normalised handle, so '@Someone' and 'someone' are the
# same actor. Only a leading '@' is stripped, matching normalise_handle: a
# handle is one token, and a value with an interior '@' is an address rather
# than a handle.
_HANDLE_MATCH = """
    LOWER(LTRIM(ci.labels->>'author_handle', '@')) = $3
"""

# Quality gate, applied at every consumption point rather than only on the
# content list. Without it the post count and the activity chart include
# items the content list refuses to show.
_QUALITY_GATE = """
    (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
"""

SQL_ACTOR_SUMMARY = f"""
    SELECT
        COUNT(*)                                        AS post_count,
        COUNT(DISTINCT s.id)                            AS source_count,
        COUNT(DISTINCT s.platform)                      AS platform_count,
        MIN(COALESCE(ci.published_at, ci.captured_at))  AS first_seen,
        MAX(COALESCE(ci.published_at, ci.captured_at))  AS last_seen,
        SUM(COALESCE((ci.labels->'engagement'->>'likes')::int, 0))  AS total_likes,
        SUM(COALESCE((ci.labels->'engagement'->>'views')::int, 0))  AS total_views,
        SUM(COALESCE((ci.labels->'engagement'->>'shares')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'retweets')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'reposts')::int, 0)
          + COALESCE((ci.labels->'engagement'->>'forwards')::int, 0)) AS total_shares,
        ARRAY_AGG(DISTINCT s.platform)                  AS platforms
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.topic_id = $1
      AND ci.org_id = $2
      AND {_HANDLE_MATCH}
      AND s.platform IN {_PUBLIC_PLATFORMS}
      AND {_QUALITY_GATE}
"""

SQL_ACTOR_CONTENT = f"""
    SELECT
        ci.id,
        ci.url,
        ci.title,
        ci.clean_text,
        ci.translated_text,
        ci.language,
        ci.captured_at,
        ci.published_at,
        ci.stance,
        ci.hostility,
        ci.credibility_score_at_capture,
        ci.narrative_cluster_id,
        nc.label        AS cluster_label,
        s.name          AS source_name,
        s.platform      AS platform,
        ci.labels->'engagement' AS engagement,
        ci.labels->>'classification' AS classification
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    LEFT JOIN narrative_clusters nc ON nc.id = ci.narrative_cluster_id
    WHERE ci.topic_id = $1
      AND ci.org_id = $2
      AND {_HANDLE_MATCH}
      AND s.platform IN {_PUBLIC_PLATFORMS}
      AND {_QUALITY_GATE}
    ORDER BY COALESCE(ci.published_at, ci.captured_at) DESC
    LIMIT $4 OFFSET $5
"""

# Activity over time uses publication time where the platform supplied one
# and falls back to collection time, because an empty activity chart is less
# useful than one that says which points are approximate. The API reports the
# fallback count alongside, so the analyst can tell.
SQL_ACTOR_ACTIVITY = f"""
    SELECT
        DATE_TRUNC('day', COALESCE(ci.published_at, ci.captured_at)) AS day,
        COUNT(*)                                                     AS post_count,
        COUNT(*) FILTER (WHERE ci.published_at IS NULL)              AS approximate_count,
        SUM(COALESCE((ci.labels->'engagement'->>'likes')::int, 0))   AS total_likes
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.topic_id = $1
      AND ci.org_id = $2
      AND {_HANDLE_MATCH}
      AND s.platform IN {_PUBLIC_PLATFORMS}
      AND {_QUALITY_GATE}
      AND COALESCE(ci.published_at, ci.captured_at) >= NOW() - make_interval(days => $4)
    GROUP BY 1
    ORDER BY 1
"""


def normalise_handle(handle: str) -> str:
    """Lowercase, strip whitespace, drop a leading '@'.

    Adapters store the '@' inconsistently, so the same account arrives as
    '@someone' from one platform and 'someone' from another.
    """
    if not handle:
        return ""
    return handle.strip().lstrip("@").strip().lower()


async def get_actor_summary(
    conn: DBConnection,
    topic_id: str,
    handle: str,
    *,
    org_id: str,
) -> dict[str, Any]:
    """Aggregate counts for one handle within one topic."""
    row = await conn.fetchrow(SQL_ACTOR_SUMMARY, topic_id, org_id, normalise_handle(handle))
    return dict(row) if row else {}


async def list_actor_content(
    conn: DBConnection,
    topic_id: str,
    handle: str,
    *,
    org_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Public content authored by one handle within one topic."""
    rows = await conn.fetch(
        SQL_ACTOR_CONTENT, topic_id, org_id, normalise_handle(handle), limit, offset
    )
    return [dict(r) for r in rows]


async def get_actor_activity(
    conn: DBConnection,
    topic_id: str,
    handle: str,
    *,
    org_id: str,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Daily post counts for one handle within one topic."""
    rows = await conn.fetch(SQL_ACTOR_ACTIVITY, topic_id, org_id, normalise_handle(handle), days)
    return [dict(r) for r in rows]
