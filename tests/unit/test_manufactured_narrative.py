"""Manufactured Narrative signal — issue #32.

The inverse of the existing convergence rule. That one fires when
independent sourcing rises; this one fires when item count and contributing
account count climb while independent source count stays flat.

That is the behavioural fingerprint of amplification rather than reporting,
and it is detectable entirely from how content spreads, without anyone
judging whether the claims are true. The signal says the spread lacks
independent sourcing. It never says the narrative is false.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from anveshak.analyst.manufactured import (
    SQL_AMPLIFIED_CLUSTERS,
    build_description,
    build_evidence,
    qualifies,
)
from anveshak.analyst.settings import settings

pytestmark = pytest.mark.unit


def _cluster(**overrides):
    base = {
        "item_count": settings.manufactured_min_item_count,
        "contributing_account_count": settings.manufactured_min_account_count,
        "independent_source_count": settings.manufactured_max_independent_sources,
    }
    base.update(overrides)
    return base


class TestFiringCondition:
    def test_high_volume_from_many_accounts_on_flat_sourcing_qualifies(self):
        assert qualifies(**_cluster()) is True

    def test_too_few_items_does_not_qualify(self):
        assert qualifies(**_cluster(item_count=settings.manufactured_min_item_count - 1)) is False

    def test_too_few_accounts_does_not_qualify(self):
        """Many items from one account is one loud account, not amplification."""
        assert (
            qualifies(
                **_cluster(contributing_account_count=settings.manufactured_min_account_count - 1)
            )
            is False
        )

    def test_wide_independent_sourcing_does_not_qualify(self):
        """That is reporting, and the existing convergence signal covers it."""
        assert (
            qualifies(
                **_cluster(
                    independent_source_count=settings.manufactured_max_independent_sources + 1
                )
            )
            is False
        )

    def test_it_is_the_inverse_of_convergence(self):
        """The two rules must not both fire on one cluster."""
        both = _cluster(
            independent_source_count=settings.promotion_min_independent_sources,
            item_count=settings.manufactured_min_item_count + 50,
            contributing_account_count=100,
        )
        assert qualifies(**both) is False


class TestThresholdsAreSettings:
    def test_no_threshold_is_hardcoded(self):
        source = Path("services/analyst/anveshak/analyst/manufactured.py").read_text()
        for name in (
            "manufactured_min_item_count",
            "manufactured_min_account_count",
            "manufactured_max_independent_sources",
        ):
            assert f"settings.{name}" in source

    def test_the_ceiling_sits_below_the_promotion_floor(self):
        """Or one cluster qualifies as both a candidate and a manufactured
        narrative at the same time."""
        assert (
            settings.manufactured_max_independent_sources
            < settings.promotion_min_independent_sources
        )


class TestTheCardShowsArithmeticNotAVerdict:
    def test_the_description_states_what_was_measured(self):
        description = build_description(
            item_count=40, contributing_account_count=12, independent_source_count=1
        )
        assert "40" in description
        assert "12" in description
        assert "1" in description

    def test_the_description_never_asserts_falsehood(self):
        description = build_description(
            item_count=40, contributing_account_count=12, independent_source_count=1
        ).lower()
        for word in (
            "false",
            "fake",
            "disinformation",
            "misinformation",
            "propaganda",
            "misleading",
            "untrue",
            "hoax",
        ):
            assert word not in description

    def test_the_description_says_the_spread_lacks_independent_sourcing(self):
        description = build_description(
            item_count=40, contributing_account_count=12, independent_source_count=1
        ).lower()
        assert "independent" in description

    def test_the_evidence_carries_every_threshold_and_its_margin(self):
        evidence = build_evidence(
            cluster_id="cl-1",
            item_count=40,
            contributing_account_count=12,
            independent_source_count=1,
            repeated_claim="the same sentence, many accounts",
            content_item_ids=["ci-1", "ci-2"],
        )
        thresholds = evidence["thresholds"]
        assert thresholds["min_item_count"] == settings.manufactured_min_item_count
        assert thresholds["min_account_count"] == settings.manufactured_min_account_count
        assert (
            thresholds["max_independent_sources"] == settings.manufactured_max_independent_sources
        )
        margins = evidence["margins"]
        assert margins["item_count"] == 40 - settings.manufactured_min_item_count
        assert margins["account_count"] == 12 - settings.manufactured_min_account_count

    def test_the_evidence_carries_the_repeated_claim(self):
        evidence = build_evidence(
            cluster_id="cl-1",
            item_count=40,
            contributing_account_count=12,
            independent_source_count=1,
            repeated_claim="the same sentence, many accounts",
            content_item_ids=["ci-1", "ci-2"],
        )
        assert evidence["repeated_claim"] == "the same sentence, many accounts"

    def test_the_evidence_carries_the_items_that_fired_it(self):
        """So the analyst reads the claim across accounts themselves."""
        evidence = build_evidence(
            cluster_id="cl-1",
            item_count=40,
            contributing_account_count=12,
            independent_source_count=1,
            repeated_claim="claim",
            content_item_ids=["ci-1", "ci-2"],
        )
        assert evidence["content_item_ids"] == ["ci-1", "ci-2"]


class TestQuery:
    def test_the_query_counts_accounts_not_sources(self):
        assert "author_handle" in SQL_AMPLIFIED_CLUSTERS

    def test_the_query_applies_the_quality_gate(self):
        assert "content_quality" in SQL_AMPLIFIED_CLUSTERS

    def test_the_query_skips_archived_clusters(self):
        assert "archived_at IS NULL" in SQL_AMPLIFIED_CLUSTERS


class TestDedupMatchesExistingBehaviour:
    async def test_it_reuses_the_existing_24h_cluster_dedup(self):
        from anveshak.analyst.manufactured import check_manufactured_narratives

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_ctx(conn))

        assert await check_manufactured_narratives(pool, AsyncMock()) == 0

    def test_it_uses_the_shared_dedup_helper(self):
        source = Path("services/analyst/anveshak/analyst/manufactured.py").read_text()
        assert "is_duplicate_signal" in source


class TestWiring:
    def test_the_signal_loop_calls_it(self):
        source = Path("services/analyst/anveshak/analyst/signal_engine.py").read_text()
        assert "check_manufactured_narratives" in source


def _ctx(conn):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx
