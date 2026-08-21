"""Analytics repository — cross-topic aggregate queries for dashboard."""

from __future__ import annotations

from typing import Any

from anveshak.db import DBConnection

# ---------------------------------------------------------------------------
# SQL constants — $1 = days (integer), $2 = org_id (text)
# ---------------------------------------------------------------------------

SQL_CONTENT_VOLUME_TREND = """
    SELECT DATE(ci.captured_at) AS date, COUNT(*) AS count
    FROM content_items ci
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
    GROUP BY DATE(ci.captured_at)
    ORDER BY date ASC
"""

SQL_CONTENT_BY_PLATFORM = """
    SELECT s.platform, COUNT(ci.id) AS count
    FROM content_items ci
    JOIN sources s ON s.id = ci.source_id
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
    GROUP BY s.platform
    ORDER BY count DESC
"""

SQL_CONTENT_BY_LANGUAGE = """
    SELECT ci.language, COUNT(*) AS count
    FROM content_items ci
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
      AND ci.language IS NOT NULL
    GROUP BY ci.language
    ORDER BY count DESC
"""

SQL_TOP_ENTITIES_GLOBAL = """
    SELECT ee.entity_type,
           LOWER(ee.entity_text) AS entity_text,
           COUNT(*) AS mention_count,
           AVG(ee.confidence) AS avg_confidence
    FROM extracted_entities ee
    JOIN content_items ci ON ee.content_item_id = ci.id
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
      AND ee.entity_type NOT IN ('CARDINAL', 'ORDINAL', 'DATE', 'TIME', 'MONEY')
    GROUP BY ee.entity_type, LOWER(ee.entity_text)
    ORDER BY mention_count DESC
    LIMIT 25
"""

SQL_SENTIMENT_DISTRIBUTION = """
    SELECT
        COUNT(*) FILTER (WHERE (ci.labels->'sentiment'->>'compound')::float > 0.05) AS positive,
        COUNT(*) FILTER (WHERE (ci.labels->'sentiment'->>'compound')::float BETWEEN -0.05 AND 0.05) AS neutral,
        COUNT(*) FILTER (WHERE (ci.labels->'sentiment'->>'compound')::float < -0.05) AS negative,
        COUNT(*) AS total
    FROM content_items ci
    WHERE ci.captured_at >= NOW() - make_interval(days => $1)
      AND ci.org_id = $2
      AND ci.labels->'sentiment' IS NOT NULL
"""

SQL_SIGNAL_ACTIVITY_TREND = """
    SELECT DATE(s.created_at) AS date,
           COUNT(*) FILTER (WHERE s.status = 'new') AS new_count,
           COUNT(*) FILTER (WHERE s.status = 'acknowledged') AS ack_count,
           COUNT(*) FILTER (WHERE s.status = 'dismissed') AS dismissed_count
    FROM signals s
    JOIN topics t ON t.id = s.topic_id
    WHERE s.created_at >= NOW() - make_interval(days => $1)
      AND t.org_id = $2
    GROUP BY DATE(s.created_at)
    ORDER BY date ASC
"""

SQL_RECENT_ACTIVITY = """
    (SELECT 'signal' AS type, s.description, s.created_at AS timestamp,
            t.name AS topic_name, s.signal_type AS subtype, s.id::text AS resource_id
     FROM signals s
     JOIN topics t ON t.id = s.topic_id
     WHERE s.created_at >= NOW() - INTERVAL '7 days'
       AND t.org_id = $1
     ORDER BY s.created_at DESC LIMIT 10)
    UNION ALL
    (SELECT 'report' AS type,
            CONCAT('Report generated: ', r.report_type) AS description,
            r.generated_at AS timestamp,
            t.name AS topic_name, r.report_type AS subtype, r.id::text AS resource_id
     FROM reports r
     JOIN topics t ON t.id = r.topic_id
     WHERE r.generated_at >= NOW() - INTERVAL '7 days'
       AND r.generated_at IS NOT NULL AND r.generation_error IS NULL
       AND t.org_id = $1
     ORDER BY r.generated_at DESC LIMIT 10)
    UNION ALL
    (SELECT 'credibility_change' AS type,
            CONCAT(src.name, ': ', cal.old_score, ' -> ', cal.new_score) AS description,
            cal.created_at AS timestamp,
            NULL AS topic_name, cal.reason AS subtype, cal.source_id::text AS resource_id
     FROM credibility_audit_log cal
     JOIN sources src ON src.id = cal.source_id
     WHERE cal.created_at >= NOW() - INTERVAL '7 days'
       AND cal.org_id = $1
     ORDER BY cal.created_at DESC LIMIT 10)
    ORDER BY timestamp DESC
    LIMIT 20
"""

SQL_ACTIVE_TOPICS = "SELECT COUNT(*) FROM topics WHERE status = 'active' AND org_id = $1"


# ---------------------------------------------------------------------------
# Repository function
# ---------------------------------------------------------------------------


async def get_dashboard_data(conn: DBConnection, days: int = 30, *, org_id: str) -> dict[str, Any]:
    """Return cross-topic aggregate analytics for the dashboard, scoped to org."""
    volume_rows = await conn.fetch(SQL_CONTENT_VOLUME_TREND, days, org_id)
    platform_rows = await conn.fetch(SQL_CONTENT_BY_PLATFORM, days, org_id)
    language_rows = await conn.fetch(SQL_CONTENT_BY_LANGUAGE, days, org_id)
    entity_rows = await conn.fetch(SQL_TOP_ENTITIES_GLOBAL, days, org_id)
    sentiment_row = await conn.fetchrow(SQL_SENTIMENT_DISTRIBUTION, days, org_id)
    signal_rows = await conn.fetch(SQL_SIGNAL_ACTIVITY_TREND, days, org_id)
    activity_rows = await conn.fetch(SQL_RECENT_ACTIVITY, org_id)
    active_topics = await conn.fetchval(SQL_ACTIVE_TOPICS, org_id)

    return {
        "content_volume_trend": [dict(r) for r in volume_rows],
        "content_by_platform": [dict(r) for r in platform_rows],
        "content_by_language": [dict(r) for r in language_rows],
        "top_entities": [dict(r) for r in entity_rows],
        "sentiment_distribution": dict(sentiment_row)
        if sentiment_row
        else {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "total": 0,
        },
        "signal_activity_trend": [dict(r) for r in signal_rows],
        "recent_activity": [dict(r) for r in activity_rows],
        "active_topics": int(active_topics or 0),
    }
