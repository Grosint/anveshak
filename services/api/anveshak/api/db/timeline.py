"""Sentiment Timeline aggregate — issue #29.

Supporting and opposing volume as separate series over publication time,
with mean hostility overlaid. Two diverging volume curves show polarisation;
a rising hostility line shows escalation independent of which side is
growing. A single sentiment score expresses neither, which is why #28
produces two measures.

Three properties are load-bearing rather than cosmetic:

  - The chart plots published_at. Items with none are excluded and counted,
    so a collection artefact never appears as a spike at today's date.
  - NULL hostility is excluded from the mean. Averaging it as 0.0 would
    invent calm that nobody observed.
  - Content the models could not read is counted separately, so an analyst
    knows which part of the chart to distrust.
"""

from __future__ import annotations

from typing import Any

from anveshak.db import DBConnection

from ..settings import settings

# stance and hostility are columns rather than labels JSONB precisely so this
# query can group by day across the whole content table. See migration 006.
SQL_TIMELINE_BUCKETS = """
    SELECT
        DATE_TRUNC($4, ci.published_at)                          AS bucket,
        COUNT(*) FILTER (WHERE ci.stance = 'supporting')         AS supporting,
        COUNT(*) FILTER (WHERE ci.stance = 'opposing')           AS opposing,
        COUNT(*) FILTER (WHERE ci.stance = 'neutral')            AS neutral,
        COUNT(*) FILTER (WHERE ci.stance = 'unsupported_language')
                                                                 AS unsupported_language,
        COUNT(*) FILTER (WHERE ci.stance IS NULL)                AS unscored,
        COUNT(*)                                                 AS total,
        AVG(ci.hostility) FILTER (WHERE ci.hostility IS NOT NULL) AS mean_hostility,
        COUNT(*) FILTER (WHERE ci.hostility IS NOT NULL)          AS hostility_sample_count
    FROM content_items ci
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.org_id = $2
      AND ci.published_at IS NOT NULL
      AND ci.published_at >= NOW() - make_interval(days => $3)
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
    GROUP BY 1
    ORDER BY 1
"""

# Reported as a footnote, never silently dropped. An analyst who cannot see
# how much was excluded cannot judge the chart.
SQL_TIMELINE_EXCLUDED_COUNT = """
    SELECT COUNT(*) AS excluded_count
    FROM content_items ci
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.org_id = $2
      AND ci.published_at IS NULL
      AND ci.captured_at >= NOW() - make_interval(days => $3)
      AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
"""

# Earliest publication time held per platform. Where a platform exposes only
# a recent search window, the chart before that point is a data gap rather
# than silence, and the analyst has to be told which is which.
SQL_TIMELINE_PLATFORM_WINDOWS = """
    SELECT s.platform,
           MIN(ci.published_at) AS earliest_published_at,
           COUNT(*)             AS item_count
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE (ci.topic_id = $1
       OR ci.id IN (SELECT content_item_id FROM topic_content_items WHERE topic_id = $1))
      AND ci.org_id = $2
      AND ci.published_at IS NOT NULL
    GROUP BY s.platform
"""


def choose_bucket(*, days: int) -> str:
    """Daily buckets, rolling up to weekly over a long range.

    A movement running for months is unreadable at daily resolution, and a
    fortnight is unreadable at weekly.
    """
    return "day" if days <= settings.timeline_daily_bucket_max_days else "week"


def to_percentages(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert stance counts to shares of each bucket's total.

    Absolute volume stays the default view, so a volume explosion is never
    hidden by normalisation; this is the opt-in second view. The original
    total is kept on each bucket so the absolute figure is still readable,
    and mean hostility passes through untouched because it is already a 0.0
    to 1.0 measure rather than a share of volume.
    """
    converted: list[dict[str, Any]] = []
    for bucket in buckets:
        counted = sum(
            int(bucket.get(key) or 0)
            for key in ("supporting", "opposing", "neutral", "unsupported_language")
        )
        row = dict(bucket)
        row["total"] = counted
        for key in ("supporting", "opposing", "neutral", "unsupported_language"):
            if key not in bucket:
                continue
            value = int(bucket.get(key) or 0)
            row[key] = round(100.0 * value / counted, 2) if counted else 0.0
        converted.append(row)
    return converted


async def get_timeline(
    conn: DBConnection,
    topic_id: str,
    *,
    org_id: str,
    days: int = 90,
    as_percentage: bool = False,
) -> dict[str, Any]:
    """Timeline buckets, the excluded count, and the data-availability note.

    org_id is keyword-only so it cannot be forgotten at a call site.
    """
    bucket = choose_bucket(days=days)

    rows = await conn.fetch(SQL_TIMELINE_BUCKETS, topic_id, org_id, days, bucket)
    buckets = [dict(r) for r in rows]

    excluded = await conn.fetchval(SQL_TIMELINE_EXCLUDED_COUNT, topic_id, org_id, days)
    windows = await conn.fetch(SQL_TIMELINE_PLATFORM_WINDOWS, topic_id, org_id)

    constrained = [
        {
            "platform": row["platform"],
            "earliest_published_at": row["earliest_published_at"],
            "item_count": row["item_count"],
        }
        for row in windows
        if row["platform"] in settings.timeline_constrained_platforms
    ]

    return {
        "topic_id": topic_id,
        "bucket": bucket,
        "days": days,
        "as_percentage": as_percentage,
        "buckets": to_percentages(buckets) if as_percentage else buckets,
        # Excluded rather than plotted at today. The count is the footnote.
        "excluded_no_publication_time": int(excluded or 0),
        # Platforms whose search window bounds how far back the chart can
        # reach. Before the earliest point here, absence is a data gap
        # rather than silence.
        "constrained_platforms": constrained,
    }
