"""Engine C — Identifier Clustering (Step 3).

Group extracted identifiers across content items by normalized value.
Detect identifier networks: shared identifiers across different content
from different sources → same actor/operation.

Pure functions — no DB, no I/O. Safe to unit-test without infrastructure.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentIdentifier:
    """An identifier extracted from a specific content item."""

    identifier_type: str  # PHONE_IN, UPI, CRYPTO_BTC, etc.
    normalized_value: str  # canonical form
    content_item_id: str  # which content item
    source_id: str  # which source
    seen_at: datetime  # when content was captured


@dataclass(frozen=True)
class IdentifierCluster:
    """A group of content items sharing the same identifier."""

    identifier_type: str
    identifier_value: str
    content_item_ids: frozenset[str]
    source_ids: frozenset[str]
    source_count: int
    content_item_count: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class NetworkEdge:
    """Co-occurrence edge: two identifiers appearing in the same content items."""

    identifier_a_type: str
    identifier_a_value: str
    identifier_b_type: str
    identifier_b_value: str
    shared_content_item_ids: frozenset[str]
    shared_count: int


# ---------------------------------------------------------------------------
# Cluster building
# ---------------------------------------------------------------------------


def build_clusters(
    identifiers: list[ContentIdentifier],
    *,
    min_sources: int = 2,
    min_items: int = 2,
) -> list[IdentifierCluster]:
    """Group identifiers by (type, value) and return clusters meeting thresholds.

    Args:
        identifiers: All extracted identifiers across content items.
        min_sources: Minimum distinct source_ids to form a cluster (default 2).
        min_items: Minimum distinct content_item_ids to form a cluster (default 2).

    Returns:
        List of IdentifierCluster sorted by source_count descending.
    """
    if not identifiers:
        return []

    # Group by (type, normalized_value)
    groups: dict[tuple[str, str], list[ContentIdentifier]] = defaultdict(list)
    for ident in identifiers:
        groups[(ident.identifier_type, ident.normalized_value)].append(ident)

    clusters: list[IdentifierCluster] = []
    for (id_type, id_value), items in groups.items():
        # Deduplicate by content_item_id
        seen_items: dict[str, ContentIdentifier] = {}
        for item in items:
            if item.content_item_id not in seen_items:
                seen_items[item.content_item_id] = item

        content_item_ids = frozenset(seen_items.keys())
        source_ids = frozenset(item.source_id for item in seen_items.values())
        timestamps = [item.seen_at for item in seen_items.values()]

        if len(content_item_ids) < min_items:
            continue
        if len(source_ids) < min_sources:
            continue

        clusters.append(
            IdentifierCluster(
                identifier_type=id_type,
                identifier_value=id_value,
                content_item_ids=content_item_ids,
                source_ids=source_ids,
                source_count=len(source_ids),
                content_item_count=len(content_item_ids),
                first_seen_at=min(timestamps),
                last_seen_at=max(timestamps),
            )
        )

    clusters.sort(key=lambda c: c.source_count, reverse=True)
    return clusters


# ---------------------------------------------------------------------------
# Incremental merge
# ---------------------------------------------------------------------------


def merge_into_cluster(
    cluster: IdentifierCluster,
    new_item: ContentIdentifier,
) -> IdentifierCluster:
    """Add a new content item to an existing cluster. Returns new instance.

    Args:
        cluster: Existing cluster.
        new_item: New identifier occurrence to merge.

    Returns:
        New IdentifierCluster with updated stats.

    Raises:
        ValueError: If new_item type or value doesn't match cluster.
    """
    if new_item.identifier_type != cluster.identifier_type:
        raise ValueError(
            f"type mismatch: cluster={cluster.identifier_type}, item={new_item.identifier_type}"
        )
    if new_item.normalized_value != cluster.identifier_value:
        raise ValueError(
            f"value mismatch: cluster={cluster.identifier_value}, item={new_item.normalized_value}"
        )

    new_content_ids = cluster.content_item_ids | {new_item.content_item_id}
    new_source_ids = cluster.source_ids | {new_item.source_id}

    return IdentifierCluster(
        identifier_type=cluster.identifier_type,
        identifier_value=cluster.identifier_value,
        content_item_ids=new_content_ids,
        source_ids=new_source_ids,
        source_count=len(new_source_ids),
        content_item_count=len(new_content_ids),
        first_seen_at=min(cluster.first_seen_at, new_item.seen_at),
        last_seen_at=max(cluster.last_seen_at, new_item.seen_at),
    )


# ---------------------------------------------------------------------------
# Co-occurrence detection
# ---------------------------------------------------------------------------


def find_co_occurrences(
    identifiers: list[ContentIdentifier],
) -> list[NetworkEdge]:
    """Find pairs of distinct identifiers that appear in the same content items.

    Args:
        identifiers: All extracted identifiers across content items.

    Returns:
        List of NetworkEdge sorted by shared_count descending.
    """
    if not identifiers:
        return []

    # Map: content_item_id → set of (type, value) tuples
    content_to_ids: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for ident in identifiers:
        content_to_ids[ident.content_item_id].add((ident.identifier_type, ident.normalized_value))

    # Count shared content items per identifier pair
    pair_contents: dict[tuple[tuple[str, str], tuple[str, str]], set[str]] = defaultdict(set)
    for content_id, id_set in content_to_ids.items():
        # All pairs of distinct identifiers in this content item
        for a, b in combinations(sorted(id_set), 2):
            pair_contents[(a, b)].add(content_id)

    edges: list[NetworkEdge] = []
    for (a, b), content_ids in pair_contents.items():
        edges.append(
            NetworkEdge(
                identifier_a_type=a[0],
                identifier_a_value=a[1],
                identifier_b_type=b[0],
                identifier_b_value=b[1],
                shared_content_item_ids=frozenset(content_ids),
                shared_count=len(content_ids),
            )
        )

    edges.sort(key=lambda e: e.shared_count, reverse=True)
    return edges


# ---------------------------------------------------------------------------
# Full network builder
# ---------------------------------------------------------------------------


def build_identifier_network(
    identifiers: list[ContentIdentifier],
    *,
    min_sources: int = 2,
    min_items: int = 2,
) -> tuple[list[IdentifierCluster], list[NetworkEdge]]:
    """Build full identifier network: clusters + co-occurrence edges.

    Args:
        identifiers: All extracted identifiers across content items.
        min_sources: Minimum distinct sources for cluster formation.
        min_items: Minimum distinct content items for cluster formation.

    Returns:
        Tuple of (clusters, edges).
    """
    clusters = build_clusters(
        identifiers,
        min_sources=min_sources,
        min_items=min_items,
    )
    edges = find_co_occurrences(identifiers)
    return clusters, edges
