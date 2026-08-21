---
name: fallback-null-fk-query
description: When a foreign key (e.g. cluster_id) is nullable, graph/connection queries silently return empty — add a fallback query path
type: pitfall
---

# Fallback Query for Nullable Foreign Keys

## Problem
Signal graph query joins content items via `ci.narrative_cluster_id = s.cluster_id`.
When `cluster_id IS NULL` (pre-seeded signals, sentiment shifts), the LEFT JOIN
returns zero content rows → graph shows a single lonely node.

This is silent — no error, just an empty graph. Hard to debug.

## Solution
Two SQL queries + conditional routing:

```python
SQL_SIGNAL_CONNECTIONS = """..JOIN ON ci.narrative_cluster_id = s.cluster_id..."""
SQL_SIGNAL_CONNECTIONS_BY_TOPIC = """..JOIN ON ci.topic_id = s.topic_id..."""

async def get_signal_connections(conn, signal_id):
    rows = await conn.fetch(SQL_SIGNAL_CONNECTIONS, signal_id)
    first = rows[0]
    if not first["cluster_id"]:
        rows = await conn.fetch(SQL_SIGNAL_CONNECTIONS_BY_TOPIC, signal_id)
        return _build_topic_graph(rows)
    return _build_cluster_graph(rows)
```

## Why not one query with COALESCE?
`WHERE ci.narrative_cluster_id = COALESCE(s.cluster_id, ci.topic_id)` doesn't work —
the semantics differ. Cluster-linked content shows a focused subset; topic-linked
content shows everything. Different graph builders render different node types.

## Rule
When designing queries that depend on an optional FK:
1. Check if the FK is NULL before running the main query
2. Have a fallback query using the parent relationship (topic_id)
3. Build different response shapes if the graph semantics differ
4. Test BOTH paths — with and without the FK set
