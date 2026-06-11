"""Unit tests for Engine C Step 3 — Identifier Clustering (pure functions).

Tests cover:
  1. Data model integrity (ContentIdentifier, IdentifierCluster, NetworkEdge)
  2. build_clusters() — grouping, threshold filtering, stats computation
  3. merge_into_cluster() — incremental update with dedup
  4. find_co_occurrences() — identifiers sharing content items
  5. build_identifier_network() — full network from co-occurrences
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from anveshak.analyst.identifier_clustering import (
    ContentIdentifier,
    IdentifierCluster,
    NetworkEdge,
    build_clusters,
    build_identifier_network,
    find_co_occurrences,
    merge_into_cluster,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(hour: int = 12, day: int = 1) -> datetime:
    """Quick timestamp factory."""
    return datetime(2026, 6, day, hour, 0, 0, tzinfo=timezone.utc)


def _ci(
    id_type: str = "PHONE_IN",
    value: str = "9876543210",
    content_id: str = "c1",
    source_id: str = "s1",
    seen_at: datetime | None = None,
) -> ContentIdentifier:
    """Quick ContentIdentifier factory."""
    return ContentIdentifier(
        identifier_type=id_type,
        normalized_value=value,
        content_item_id=content_id,
        source_id=source_id,
        seen_at=seen_at or _ts(),
    )


# ===================================================================
# 1. Data model tests
# ===================================================================

class TestContentIdentifierModel:
    """ContentIdentifier dataclass integrity."""

    def test_fields_exist(self) -> None:
        ci = _ci()
        assert ci.identifier_type == "PHONE_IN"
        assert ci.normalized_value == "9876543210"
        assert ci.content_item_id == "c1"
        assert ci.source_id == "s1"
        assert ci.seen_at == _ts()

    def test_frozen(self) -> None:
        ci = _ci()
        with pytest.raises(AttributeError):
            ci.identifier_type = "UPI"  # type: ignore[misc]


class TestIdentifierClusterModel:
    """IdentifierCluster dataclass integrity."""

    def test_fields_exist(self) -> None:
        cluster = IdentifierCluster(
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            content_item_ids=frozenset({"c1", "c2"}),
            source_ids=frozenset({"s1", "s2"}),
            source_count=2,
            content_item_count=2,
            first_seen_at=_ts(hour=10),
            last_seen_at=_ts(hour=14),
        )
        assert cluster.identifier_type == "PHONE_IN"
        assert cluster.identifier_value == "9876543210"
        assert cluster.source_count == 2
        assert cluster.content_item_count == 2
        assert cluster.first_seen_at == _ts(hour=10)
        assert cluster.last_seen_at == _ts(hour=14)

    def test_frozen(self) -> None:
        cluster = IdentifierCluster(
            identifier_type="UPI",
            identifier_value="test@ybl",
            content_item_ids=frozenset({"c1"}),
            source_ids=frozenset({"s1"}),
            source_count=1,
            content_item_count=1,
            first_seen_at=_ts(),
            last_seen_at=_ts(),
        )
        with pytest.raises(AttributeError):
            cluster.source_count = 5  # type: ignore[misc]


class TestNetworkEdgeModel:
    """NetworkEdge dataclass integrity."""

    def test_fields_exist(self) -> None:
        edge = NetworkEdge(
            identifier_a_type="PHONE_IN",
            identifier_a_value="9876543210",
            identifier_b_type="UPI",
            identifier_b_value="test@ybl",
            shared_content_item_ids=frozenset({"c1"}),
            shared_count=1,
        )
        assert edge.identifier_a_type == "PHONE_IN"
        assert edge.identifier_b_value == "test@ybl"
        assert edge.shared_count == 1

    def test_frozen(self) -> None:
        edge = NetworkEdge(
            identifier_a_type="PHONE_IN",
            identifier_a_value="9876543210",
            identifier_b_type="UPI",
            identifier_b_value="test@ybl",
            shared_content_item_ids=frozenset({"c1"}),
            shared_count=1,
        )
        with pytest.raises(AttributeError):
            edge.shared_count = 5  # type: ignore[misc]


# ===================================================================
# 2. build_clusters() tests
# ===================================================================

class TestBuildClusters:
    """build_clusters() groups identifiers and applies threshold."""

    def test_empty_input_returns_empty(self) -> None:
        assert build_clusters([]) == []

    def test_single_item_below_threshold(self) -> None:
        """One content item with one identifier — no cluster (needs 2+ items, 2+ sources)."""
        items = [_ci(content_id="c1", source_id="s1")]
        assert build_clusters(items) == []

    def test_two_items_same_source_below_threshold(self) -> None:
        """Two content items same identifier, same source — no cluster (needs 2+ sources)."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s1"),
        ]
        assert build_clusters(items) == []

    def test_two_items_two_sources_creates_cluster(self) -> None:
        """Two content items, two sources, same identifier → cluster."""
        items = [
            _ci(content_id="c1", source_id="s1", seen_at=_ts(hour=10)),
            _ci(content_id="c2", source_id="s2", seen_at=_ts(hour=14)),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 1
        c = clusters[0]
        assert c.identifier_type == "PHONE_IN"
        assert c.identifier_value == "9876543210"
        assert c.source_count == 2
        assert c.content_item_count == 2
        assert c.first_seen_at == _ts(hour=10)
        assert c.last_seen_at == _ts(hour=14)

    def test_three_items_three_sources(self) -> None:
        """Three items from three sources → source_count=3."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
            _ci(content_id="c3", source_id="s3"),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 1
        assert clusters[0].source_count == 3
        assert clusters[0].content_item_count == 3

    def test_duplicate_content_item_deduplicated(self) -> None:
        """Same content_item_id appears twice — counted once."""
        items = [
            _ci(content_id="c1", source_id="s1", seen_at=_ts(hour=10)),
            _ci(content_id="c1", source_id="s1", seen_at=_ts(hour=10)),  # dup
            _ci(content_id="c2", source_id="s2", seen_at=_ts(hour=14)),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 1
        assert clusters[0].content_item_count == 2  # not 3

    def test_source_count_is_distinct_source_ids(self) -> None:
        """4th item from existing source → source_count stays 3."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
            _ci(content_id="c3", source_id="s3"),
            _ci(content_id="c4", source_id="s1"),  # same source as c1
        ]
        clusters = build_clusters(items)
        assert clusters[0].source_count == 3
        assert clusters[0].content_item_count == 4

    def test_multiple_identifier_types_separate_clusters(self) -> None:
        """PHONE_IN and UPI create separate clusters."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c2", source_id="s2"),
            _ci(id_type="UPI", value="test@ybl", content_id="c3", source_id="s3"),
            _ci(id_type="UPI", value="test@ybl", content_id="c4", source_id="s4"),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 2
        types = {c.identifier_type for c in clusters}
        assert types == {"PHONE_IN", "UPI"}

    def test_same_type_different_values_separate_clusters(self) -> None:
        """Two different phone numbers → two clusters."""
        items = [
            _ci(value="9876543210", content_id="c1", source_id="s1"),
            _ci(value="9876543210", content_id="c2", source_id="s2"),
            _ci(value="8765432109", content_id="c3", source_id="s3"),
            _ci(value="8765432109", content_id="c4", source_id="s4"),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 2
        values = {c.identifier_value for c in clusters}
        assert values == {"9876543210", "8765432109"}

    def test_mixed_qualifying_and_non_qualifying(self) -> None:
        """Some identifiers qualify, some don't."""
        items = [
            # Qualifies: 2 items, 2 sources
            _ci(value="9876543210", content_id="c1", source_id="s1"),
            _ci(value="9876543210", content_id="c2", source_id="s2"),
            # Does NOT qualify: 1 item only
            _ci(value="1111111111", content_id="c3", source_id="s3"),
        ]
        clusters = build_clusters(items)
        assert len(clusters) == 1
        assert clusters[0].identifier_value == "9876543210"

    def test_content_item_ids_tracked(self) -> None:
        """Cluster contains correct content_item_ids."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
            _ci(content_id="c3", source_id="s3"),
        ]
        clusters = build_clusters(items)
        assert clusters[0].content_item_ids == frozenset({"c1", "c2", "c3"})

    def test_source_ids_tracked(self) -> None:
        """Cluster contains correct source_ids."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
        ]
        clusters = build_clusters(items)
        assert clusters[0].source_ids == frozenset({"s1", "s2"})

    def test_first_seen_is_earliest(self) -> None:
        """first_seen_at = min of all seen_at in cluster."""
        items = [
            _ci(content_id="c1", source_id="s1", seen_at=_ts(hour=14)),
            _ci(content_id="c2", source_id="s2", seen_at=_ts(hour=8)),
            _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=20)),
        ]
        clusters = build_clusters(items)
        assert clusters[0].first_seen_at == _ts(hour=8)
        assert clusters[0].last_seen_at == _ts(hour=20)

    def test_custom_min_sources_threshold(self) -> None:
        """Raise threshold to 3 sources — 2-source group filtered out."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
        ]
        assert build_clusters(items, min_sources=3) == []

    def test_custom_min_items_threshold(self) -> None:
        """Raise min_items to 3 — 2-item group filtered out."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
        ]
        assert build_clusters(items, min_items=3) == []

    def test_sorted_by_source_count_desc(self) -> None:
        """Clusters returned sorted by source_count descending."""
        items = [
            # 2 sources
            _ci(id_type="UPI", value="a@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="a@ybl", content_id="c2", source_id="s2"),
            # 4 sources
            _ci(value="9876543210", content_id="c3", source_id="s1"),
            _ci(value="9876543210", content_id="c4", source_id="s2"),
            _ci(value="9876543210", content_id="c5", source_id="s3"),
            _ci(value="9876543210", content_id="c6", source_id="s4"),
        ]
        clusters = build_clusters(items)
        assert clusters[0].source_count == 4
        assert clusters[1].source_count == 2


# ===================================================================
# 3. merge_into_cluster() tests
# ===================================================================

class TestMergeIntoCluster:
    """merge_into_cluster() adds new item to existing cluster."""

    def _base_cluster(self) -> IdentifierCluster:
        return IdentifierCluster(
            identifier_type="PHONE_IN",
            identifier_value="9876543210",
            content_item_ids=frozenset({"c1", "c2"}),
            source_ids=frozenset({"s1", "s2"}),
            source_count=2,
            content_item_count=2,
            first_seen_at=_ts(hour=10),
            last_seen_at=_ts(hour=14),
        )

    def test_new_item_new_source(self) -> None:
        """New content item from new source increments both counts."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=16))
        updated = merge_into_cluster(cluster, new_item)
        assert updated.content_item_count == 3
        assert updated.source_count == 3
        assert "c3" in updated.content_item_ids
        assert "s3" in updated.source_ids

    def test_new_item_existing_source(self) -> None:
        """New content item from existing source — source_count stays same."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s1", seen_at=_ts(hour=16))
        updated = merge_into_cluster(cluster, new_item)
        assert updated.content_item_count == 3
        assert updated.source_count == 2  # s1 already existed

    def test_duplicate_item_no_change(self) -> None:
        """Same content_item_id already in cluster — no change."""
        cluster = self._base_cluster()
        dup_item = _ci(content_id="c1", source_id="s1", seen_at=_ts(hour=10))
        updated = merge_into_cluster(cluster, dup_item)
        assert updated.content_item_count == 2
        assert updated.source_count == 2

    def test_updates_last_seen(self) -> None:
        """last_seen_at updated when new item is later."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=20))
        updated = merge_into_cluster(cluster, new_item)
        assert updated.last_seen_at == _ts(hour=20)

    def test_preserves_first_seen(self) -> None:
        """first_seen_at unchanged when new item is later."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=20))
        updated = merge_into_cluster(cluster, new_item)
        assert updated.first_seen_at == _ts(hour=10)

    def test_earlier_item_updates_first_seen(self) -> None:
        """first_seen_at updated when new item is earlier."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=6))
        updated = merge_into_cluster(cluster, new_item)
        assert updated.first_seen_at == _ts(hour=6)
        assert updated.last_seen_at == _ts(hour=14)  # unchanged

    def test_returns_new_instance(self) -> None:
        """merge_into_cluster returns new object, doesn't mutate original."""
        cluster = self._base_cluster()
        new_item = _ci(content_id="c3", source_id="s3", seen_at=_ts(hour=16))
        updated = merge_into_cluster(cluster, new_item)
        assert updated is not cluster
        assert cluster.content_item_count == 2  # original unchanged

    def test_type_mismatch_raises(self) -> None:
        """Merging identifier with different type raises ValueError."""
        cluster = self._base_cluster()  # PHONE_IN
        wrong_type = _ci(id_type="UPI", value="test@ybl", content_id="c3", source_id="s3")
        with pytest.raises(ValueError, match="type mismatch"):
            merge_into_cluster(cluster, wrong_type)

    def test_value_mismatch_raises(self) -> None:
        """Merging identifier with different value raises ValueError."""
        cluster = self._base_cluster()  # value=9876543210
        wrong_val = _ci(value="1111111111", content_id="c3", source_id="s3")
        with pytest.raises(ValueError, match="value mismatch"):
            merge_into_cluster(cluster, wrong_val)


# ===================================================================
# 4. find_co_occurrences() tests
# ===================================================================

class TestFindCoOccurrences:
    """find_co_occurrences() finds identifiers sharing content items."""

    def test_empty_input(self) -> None:
        assert find_co_occurrences([]) == []

    def test_no_shared_content(self) -> None:
        """Two identifiers in different content items — no co-occurrence."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c2", source_id="s2"),
        ]
        assert find_co_occurrences(items) == []

    def test_two_identifiers_same_content(self) -> None:
        """Phone and UPI in same content item → one co-occurrence edge."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
        ]
        edges = find_co_occurrences(items)
        assert len(edges) == 1
        edge = edges[0]
        assert "c1" in edge.shared_content_item_ids
        assert edge.shared_count == 1

    def test_three_identifiers_same_content(self) -> None:
        """Phone, UPI, and Telegram in same content → 3 edges (all pairs)."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="TELEGRAM_HANDLE", value="scammer", content_id="c1", source_id="s1"),
        ]
        edges = find_co_occurrences(items)
        assert len(edges) == 3  # phone-upi, phone-telegram, upi-telegram

    def test_shared_across_multiple_content_items(self) -> None:
        """Same pair appears in 2 content items → shared_count=2."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c2", source_id="s2"),
            _ci(id_type="UPI", value="test@ybl", content_id="c2", source_id="s2"),
        ]
        edges = find_co_occurrences(items)
        assert len(edges) == 1
        assert edges[0].shared_count == 2
        assert edges[0].shared_content_item_ids == frozenset({"c1", "c2"})

    def test_same_type_same_value_not_self_edge(self) -> None:
        """Same identifier in multiple content items — no self-edge."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c2", source_id="s2"),
        ]
        assert find_co_occurrences(items) == []

    def test_edge_identifiers_are_sorted(self) -> None:
        """Edge (a, b) is canonical — identifier_a < identifier_b lexicographically."""
        items = [
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
        ]
        edges = find_co_occurrences(items)
        assert len(edges) == 1
        # PHONE_IN < UPI lexicographically
        assert edges[0].identifier_a_type == "PHONE_IN"
        assert edges[0].identifier_b_type == "UPI"

    def test_no_duplicate_edges(self) -> None:
        """Multiple content items don't create duplicate edges."""
        items = [
            _ci(id_type="PHONE_IN", value="111", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="a@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="111", content_id="c2", source_id="s2"),
            _ci(id_type="UPI", value="a@ybl", content_id="c2", source_id="s2"),
            _ci(id_type="PHONE_IN", value="111", content_id="c3", source_id="s3"),
            _ci(id_type="UPI", value="a@ybl", content_id="c3", source_id="s3"),
        ]
        edges = find_co_occurrences(items)
        assert len(edges) == 1
        assert edges[0].shared_count == 3


# ===================================================================
# 5. build_identifier_network() tests
# ===================================================================

class TestBuildIdentifierNetwork:
    """build_identifier_network() combines clusters + co-occurrences."""

    def test_empty_input(self) -> None:
        clusters, edges = build_identifier_network([])
        assert clusters == []
        assert edges == []

    def test_clusters_and_edges_together(self) -> None:
        """Phone+UPI in same content, from different sources → cluster + edge."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c2", source_id="s2"),
            _ci(id_type="UPI", value="test@ybl", content_id="c2", source_id="s2"),
        ]
        clusters, edges = build_identifier_network(items)
        assert len(clusters) == 2  # phone cluster + UPI cluster
        assert len(edges) == 1    # phone-UPI co-occurrence

    def test_clusters_without_edges(self) -> None:
        """Same phone in different content (no other identifiers) → cluster, no edges."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
        ]
        clusters, edges = build_identifier_network(items)
        assert len(clusters) == 1
        assert edges == []

    def test_edges_without_clusters(self) -> None:
        """Two identifiers in same content, each from 1 source → edge but no clusters."""
        items = [
            _ci(id_type="PHONE_IN", value="9876543210", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="test@ybl", content_id="c1", source_id="s1"),
        ]
        clusters, edges = build_identifier_network(items)
        assert clusters == []     # neither meets 2+ sources threshold
        assert len(edges) == 1   # but they co-occur

    def test_complex_network(self) -> None:
        """Multiple identifiers, multiple content items → realistic network."""
        items = [
            # c1: phone + UPI from s1
            _ci(id_type="PHONE_IN", value="111", content_id="c1", source_id="s1"),
            _ci(id_type="UPI", value="a@ybl", content_id="c1", source_id="s1"),
            # c2: phone + telegram from s2
            _ci(id_type="PHONE_IN", value="111", content_id="c2", source_id="s2"),
            _ci(id_type="TELEGRAM_HANDLE", value="scam_bot", content_id="c2", source_id="s2"),
            # c3: UPI + telegram from s3
            _ci(id_type="UPI", value="a@ybl", content_id="c3", source_id="s3"),
            _ci(id_type="TELEGRAM_HANDLE", value="scam_bot", content_id="c3", source_id="s3"),
        ]
        clusters, edges = build_identifier_network(items)
        # All 3 identifiers appear in 2+ sources → 3 clusters
        assert len(clusters) == 3
        # Co-occurrences: phone-UPI (c1), phone-telegram (c2), UPI-telegram (c3)
        assert len(edges) == 3

    def test_network_respects_thresholds(self) -> None:
        """Custom thresholds passed through to build_clusters."""
        items = [
            _ci(content_id="c1", source_id="s1"),
            _ci(content_id="c2", source_id="s2"),
        ]
        # Default threshold → 1 cluster
        clusters1, _ = build_identifier_network(items)
        assert len(clusters1) == 1
        # Raise threshold → 0 clusters
        clusters2, _ = build_identifier_network(items, min_sources=3)
        assert len(clusters2) == 0
