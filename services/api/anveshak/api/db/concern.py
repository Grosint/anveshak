"""Concern facet repository — issue #36, ADR 0001.

Every query here orders by propagation. None of them orders by a concern
score, and none of them ever will: a concern score changes which rows come
back, never which comes first.
"""

from __future__ import annotations

import json
from typing import Any

from anveshak.concern import apply_filter, load_taxonomy
from anveshak.db import DBConnection

# Clusters with the concern categories their content carries, aggregated
# from content_items.labels. Ordering is independent source count then item
# count, identical to an unfiltered cluster list.
SQL_CLUSTERS_WITH_CONCERN = """
    SELECT nc.id,
           nc.label,
           nc.item_count,
           nc.independent_source_count,
           nc.created_at,
           COALESCE(
               jsonb_object_agg(concern.key, concern.total)
               FILTER (WHERE concern.key IS NOT NULL),
               '{}'::jsonb
           ) AS concern
    FROM narrative_clusters nc
    JOIN topics t ON t.id = nc.topic_id
    LEFT JOIN LATERAL (
        -- labels is a merge target for several writers and nothing
        -- constrains the shape of labels->'concern'. jsonb_each raises on a
        -- scalar and the ::int cast raises on a non-numeric value, either of
        -- which turns this endpoint into a 500 for the whole topic.
        SELECT kv.key, SUM(kv.value::int) AS total
        FROM content_items ci
        CROSS JOIN LATERAL jsonb_each(
            CASE
                WHEN jsonb_typeof(ci.labels->'concern') = 'object'
                    THEN ci.labels->'concern'
                ELSE '{}'::jsonb
            END
        ) AS kv
        WHERE ci.narrative_cluster_id = nc.id
          AND ci.org_id = $2
          AND jsonb_typeof(kv.value) = 'number'
          AND (ci.content_quality IS NULL OR ci.content_quality != 'low_quality')
        GROUP BY kv.key
    ) AS concern ON TRUE
    WHERE nc.topic_id = $1
      AND t.org_id = $2
      AND nc.archived_at IS NULL
    GROUP BY nc.id, nc.label, nc.item_count, nc.independent_source_count, nc.created_at
    ORDER BY nc.independent_source_count DESC, nc.item_count DESC, nc.created_at DESC
    LIMIT $3
"""


def taxonomy_payload() -> dict[str, Any]:
    """The taxonomy, shaped for the interface.

    Carries the version and owner so an analyst can see whose definition
    they are filtering by.
    """
    taxonomy = load_taxonomy()
    return {
        "version": taxonomy.version,
        "owner": taxonomy.owner,
        "categories": [
            {
                "id": category.id,
                "label": category.label,
                "definition": category.definition.strip(),
            }
            for category in taxonomy.categories
        ],
    }


async def list_clusters_by_concern(
    conn: DBConnection,
    topic_id: str,
    *,
    org_id: str,
    categories: list[str],
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Clusters carrying any of the chosen categories, in propagation order.

    The SQL orders. The filter only removes. Swapping those two would make
    this a concern ranking, which ADR 0001 forbids.
    """
    rows = await conn.fetch(SQL_CLUSTERS_WITH_CONCERN, topic_id, org_id, limit)

    clusters: list[dict[str, Any]] = []
    for row in rows:
        cluster = dict(row)
        # asyncpg returns JSONB as text unless a codec is registered on the
        # pool, and the filter reads it as a mapping.
        cluster["concern"] = _as_mapping(cluster.get("concern"))
        clusters.append(cluster)

    return apply_filter(clusters, categories=categories)


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes)):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}
