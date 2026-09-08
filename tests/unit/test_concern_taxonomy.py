"""Concern taxonomy facet — issue #36, ADR 0001.

Categories are filters the analyst chooses to apply. They order nothing, and
the system never surfaces one unprompted.

A future reader will notice that concern scores sort no list anywhere in this
codebase. That is deliberate, and these tests are the reason it stays true.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from anveshak.concern import (
    apply_filter,
    load_taxonomy,
    score_against_taxonomy,
)

pytestmark = pytest.mark.unit


class TestTheTaxonomyIsAVersionedFile:
    def test_it_loads(self):
        taxonomy = load_taxonomy()
        assert taxonomy.version >= 1
        assert taxonomy.categories

    def test_no_category_is_embedded_in_code(self):
        source = Path("sdk/anveshak/concern.py").read_text()
        assert "incitement" not in source.lower()

    def test_the_path_is_a_setting(self):
        from anveshak.concern_settings import ConcernSettings

        assert ConcernSettings().concern_taxonomy_path

    def test_the_customer_owns_it(self):
        taxonomy = load_taxonomy()
        assert taxonomy.owner == "customer"


class TestCategoriesAreBehavioural:
    @pytest.fixture
    def taxonomy(self):
        return load_taxonomy()

    def test_every_category_has_a_definition(self, taxonomy):
        for category in taxonomy.categories:
            assert category.definition.strip()

    def test_no_category_names_a_political_position(self, taxonomy):
        """A viewpoint-based category turns this into a dissent detector."""
        viewpoint_words = {
            "left",
            "right",
            "liberal",
            "conservative",
            "nationalist",
            "secular",
            "anti-national",
            "pro-government",
            "opposition",
            "dissent",
            "criticism",
        }
        for category in taxonomy.categories:
            text = f"{category.label} {category.definition}".lower()
            for word in viewpoint_words:
                assert word not in text.split(), f"{category.id}: {word}"

    def test_no_category_names_an_organisation_or_a_party(self, taxonomy):
        organisations = {"bjp", "congress", "rss", "pfi", "sdpi", "aap", "tmc"}
        for category in taxonomy.categories:
            tokens = set(f"{category.id} {category.label}".lower().split())
            assert not (tokens & organisations), category.id


class TestScoring:
    def test_matching_content_scores_the_category(self):
        scores = score_against_taxonomy("Send UPI to claim your lottery winner prize")
        assert scores.get("financial_fraud", 0) > 0

    def test_unmatched_content_scores_nothing(self):
        scores = score_against_taxonomy("The district council met to discuss drainage.")
        assert scores == {}

    def test_hindi_content_is_scored(self):
        scores = score_against_taxonomy("सभी ग्रुप में भेजें, कॉपी पेस्ट करें")
        assert scores.get("coordinated_inauthenticity", 0) > 0

    def test_a_score_is_a_count_of_matched_patterns(self):
        """A count an analyst can verify, not an opaque model output."""
        scores = score_against_taxonomy("send upi now, kyc expired, processing fee")
        assert scores["financial_fraud"] >= 2


class TestFilteringChangesMembershipNotOrdering:
    """The single most important test in this file. ADR 0001."""

    ITEMS = [
        {"id": "a", "independent_source_count": 6, "concern": {"financial_fraud": 3}},
        {"id": "b", "independent_source_count": 4, "concern": {}},
        {"id": "c", "independent_source_count": 2, "concern": {"financial_fraud": 9}},
        {"id": "d", "independent_source_count": 1, "concern": {"incitement_to_violence": 5}},
    ]

    def test_applying_a_filter_removes_non_matching_items(self):
        filtered = apply_filter(self.ITEMS, categories=["financial_fraud"])
        assert {item["id"] for item in filtered} == {"a", "c"}

    def test_applying_a_filter_does_not_reorder_what_remains(self):
        filtered = apply_filter(self.ITEMS, categories=["financial_fraud"])
        assert [item["id"] for item in filtered] == ["a", "c"]

    def test_the_highest_concern_score_does_not_move_to_the_top(self):
        """c scores 9 and a scores 3. a stays first, because a spreads wider."""
        filtered = apply_filter(self.ITEMS, categories=["financial_fraud"])
        assert filtered[0]["id"] == "a"

    def test_no_filter_returns_everything_in_the_original_order(self):
        assert [item["id"] for item in apply_filter(self.ITEMS, categories=[])] == [
            "a",
            "b",
            "c",
            "d",
        ]

    def test_several_categories_are_a_union(self):
        filtered = apply_filter(
            self.ITEMS, categories=["financial_fraud", "incitement_to_violence"]
        )
        assert [item["id"] for item in filtered] == ["a", "c", "d"]


class TestNothingSortsByConcern:
    def test_the_module_never_reorders(self):
        """No sorted() and no .sort(). Prose about sorting is fine; a call is not."""
        source = Path("sdk/anveshak/concern.py").read_text()
        assert "sorted(" not in source
        assert ".sort(" not in source

    def test_no_sql_orders_by_a_concern_score(self):
        for directory in (
            Path("services/analyst/anveshak/analyst"),
            Path("services/api/anveshak/api"),
            Path("sdk/anveshak"),
        ):
            for path in directory.rglob("*.py"):
                source = path.read_text().lower()
                assert "order by concern" not in source, path

    def test_the_frontend_never_sorts_on_a_concern_value(self):
        """Prose about not sorting is fine. A sort call reading concern is not."""
        import re

        sort_call = re.compile(r"\.sort\([^)]*concern[^)]*\)", re.IGNORECASE)
        sorted_by_concern = re.compile(r"sortBy\s*[=:]\s*['\"]concern", re.IGNORECASE)
        for path in Path("frontend/src").rglob("*.ts*"):
            source = path.read_text()
            assert not sort_call.search(source), path
            assert not sorted_by_concern.search(source), path
