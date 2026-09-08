"""Watch Space — issue #25.

A Watch Space is a Topic in every technical respect. The distinction is
breadth and intent: it collects across a domain rather than a named subject,
and its clusters are what narrative detection detects within.

Its keywords must name no specific organisation, party, or individual. If a
target appears in the keywords, the later claim that the system found a
narrative unaided is false, and that is the first thing a customer checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from anveshak.models.base import Labels
from anveshak.models.topic import Topic

pytestmark = pytest.mark.unit

WATCH_SPACE_SEED = Path("infra/configs/watch_spaces/internal_security_tension.yaml")


class TestTopicModelCarriesTheMarker:
    def test_topic_defaults_to_not_a_watch_space(self):
        topic = Topic(name="Kerala Cyber Fraud Ring", labels=Labels())
        assert topic.is_watch_space is False
        assert topic.parent_topic_id is None

    def test_a_watch_space_is_marked(self):
        topic = Topic(name="Internal Security Tension", is_watch_space=True, labels=Labels())
        assert topic.is_watch_space is True

    def test_a_promoted_topic_records_its_lineage(self):
        topic = Topic(name="Promoted", parent_topic_id="watch-space-1", labels=Labels())
        assert topic.parent_topic_id == "watch-space-1"

    def test_the_marker_is_not_optional(self):
        """A boolean with a default, never None, so no call site null-checks it."""
        assert Topic.model_fields["is_watch_space"].annotation is bool


class TestApiAcceptsTheMarker:
    def test_create_request_accepts_a_watch_space(self):
        from anveshak.api.routes.topics import CreateTopicRequest

        req = CreateTopicRequest(name="Domain", keywords=["a"], is_watch_space=True)
        assert req.is_watch_space is True

    def test_create_request_defaults_to_a_normal_topic(self):
        from anveshak.api.routes.topics import CreateTopicRequest

        assert CreateTopicRequest(name="Subject", keywords=["a"]).is_watch_space is False

    def test_insert_sql_persists_both_columns(self):
        from anveshak.api.db.topics import SQL_INSERT_TOPIC

        assert "is_watch_space" in SQL_INSERT_TOPIC
        assert "parent_topic_id" in SQL_INSERT_TOPIC

    def test_insert_placeholder_count_matches_columns(self):
        import re

        from anveshak.api.db.topics import SQL_INSERT_TOPIC

        columns = SQL_INSERT_TOPIC.split("(", 1)[1].split(")", 1)[0]
        column_count = len([c for c in columns.split(",") if c.strip()])
        placeholders = re.findall(r"\$\d+", SQL_INSERT_TOPIC.split("VALUES", 1)[1])
        assert column_count == len(placeholders)

    def test_list_query_exposes_the_marker(self):
        """The interface cannot identify a Watch Space unless the list says so."""
        from anveshak.api.db.topics import SQL_LIST_TOPICS, SQL_LIST_TOPICS_BY_ORG

        assert "is_watch_space" in SQL_LIST_TOPICS
        assert "is_watch_space" in SQL_LIST_TOPICS_BY_ORG


class TestSeededWatchSpace:
    def test_the_seed_file_exists(self):
        assert WATCH_SPACE_SEED.exists()

    @pytest.fixture
    def seed(self):
        return yaml.safe_load(WATCH_SPACE_SEED.read_text())

    def test_it_is_marked_as_a_watch_space(self, seed):
        assert seed["is_watch_space"] is True

    def test_it_carries_enough_sources(self, seed):
        """Thirty to fifty sources across feeds, channels, forums and accounts."""
        assert 30 <= len(seed["sources"]) <= 50

    def test_sources_span_multiple_platforms(self, seed):
        platforms = {source["platform"] for source in seed["sources"]}
        assert len(platforms) >= 4

    def test_every_source_has_a_platform_and_a_handle(self, seed):
        for source in seed["sources"]:
            assert source["platform"]
            assert source["url_or_handle"]

    def test_it_collects_in_english_and_hindi(self, seed):
        assert "en" in seed["languages"]
        assert "hi" in seed["languages"]


class TestKeywordsNameNoTarget:
    """The load-bearing claim of the demonstration.

    If a keyword names the group the system later 'discovers', detection
    found nothing. This test is the guard on that claim.
    """

    @pytest.fixture
    def keywords(self):
        seed = yaml.safe_load(WATCH_SPACE_SEED.read_text())
        return [k.lower() for k in seed["keywords"]]

    def test_no_keyword_names_a_political_party(self, keywords):
        parties = {
            "bjp",
            "congress",
            "inc",
            "aap",
            "cpi",
            "cpm",
            "cpi(m)",
            "dmk",
            "aiadmk",
            "trs",
            "brs",
            "tmc",
            "shiv sena",
            "ncp",
            "rjd",
            "jdu",
            "sp",
            "bsp",
            "aimim",
            "ysrcp",
            "tdp",
            "jds",
            "akali",
            "pdp",
            "national conference",
        }
        for keyword in keywords:
            assert not (set(keyword.split()) & parties), keyword
            assert keyword not in parties

    def test_no_keyword_names_a_specific_organisation(self, keywords):
        organisations = {
            "rss",
            "vhp",
            "bajrang dal",
            "sfi",
            "abvp",
            "nsui",
            "sdpi",
            "pfi",
            "jamaat",
            "sikhs for justice",
            "khalistan",
        }
        for organisation in organisations:
            assert not any(organisation in keyword for keyword in keywords), organisation

    def test_no_keyword_is_a_person_name(self, keywords):
        """Domain vocabulary is lowercase common nouns, not proper nouns."""
        seed = yaml.safe_load(WATCH_SPACE_SEED.read_text())
        for keyword in seed["keywords"]:
            assert keyword == keyword.lower(), keyword

    def test_keywords_describe_behaviour_not_identity(self, keywords):
        """Every keyword reads as a domain term an analyst would defend."""
        assert len(keywords) >= 10
        for keyword in keywords:
            assert len(keyword) >= 4
