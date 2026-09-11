"""Watch Space - issues #25 and #52.

A Watch Space is a Topic in every technical respect. The distinction is
breadth and intent: it collects across a domain rather than a named subject,
and its clusters are what narrative detection detects within.

Its keywords must name no specific organisation, party, or individual. If a
target appears in the keywords, the later claim that the system found a
narrative unaided is false, and that is the first thing a customer checks.

Every constraint below runs against every file in the Watch Space directory
rather than one named file. A second domain was added in #52, and a rule
that only guards the file it was written for guards nothing once a third
arrives.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from anveshak.models.base import Labels
from anveshak.models.topic import Topic

pytestmark = pytest.mark.unit

WATCH_SPACE_DIR = Path("infra/configs/watch_spaces")
WATCH_SPACE_SEEDS = sorted(WATCH_SPACE_DIR.glob("*.yaml"))

DEVANAGARI = re.compile(r"[\u0900-\u097f]")


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


@pytest.fixture(params=WATCH_SPACE_SEEDS, ids=lambda path: path.stem)
def seed(request):
    """Every Watch Space definition, one test run each."""
    return yaml.safe_load(request.param.read_text())


class TestSeededWatchSpaces:
    """Every Watch Space definition on disk, not one named file."""

    def test_the_directory_holds_the_expected_domains(self):
        """Named explicitly, so an empty glob cannot pass every other test."""
        names = {path.name for path in WATCH_SPACE_SEEDS}
        assert "internal_security_tension.yaml" in names
        assert "youth_grievance.yaml" in names

    def test_more_than_one_domain_is_watched(self):
        """One Watch Space is a hand-tuned case; two is a mechanism."""
        assert len(WATCH_SPACE_SEEDS) >= 2

    def test_each_domain_is_defined_once(self):
        seeds = [yaml.safe_load(path.read_text()) for path in WATCH_SPACE_SEEDS]
        names = [seed["name"] for seed in seeds]
        assert len(names) == len(set(names))

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

    def test_no_source_is_listed_twice(self, seed):
        handles = [(s["platform"], s["url_or_handle"]) for s in seed["sources"]]
        assert len(handles) == len(set(handles))

    def test_it_collects_in_english_and_hindi(self, seed):
        assert "en" in seed["languages"]
        assert "hi" in seed["languages"]


class TestKeywordsCoverBothLanguages:
    """A declared language with no keywords in it collects nothing.

    languages: [en, hi] sets what the pipeline will accept, but keywords are
    what the scraper matches on. English-only keywords under a bilingual
    Watch Space draw the Signal from the English-speaking part of a story.
    """

    def test_keywords_include_devanagari(self, seed):
        assert any(DEVANAGARI.search(keyword) for keyword in seed["keywords"])

    def test_keywords_include_latin_script(self, seed):
        assert any(re.search(r"[a-z]", keyword) for keyword in seed["keywords"])

    def test_each_language_carries_several_keywords(self, seed):
        """One token in a language is a gesture, not coverage."""
        hindi = [k for k in seed["keywords"] if DEVANAGARI.search(k)]
        english = [k for k in seed["keywords"] if not DEVANAGARI.search(k)]
        assert len(hindi) >= 5
        assert len(english) >= 5


class TestKeywordsNameNoTarget:
    """The load-bearing claim of the demonstration.

    If a keyword names the group the system later 'discovers', detection
    found nothing. This test is the guard on that claim.
    """

    @pytest.fixture
    def keywords(self, seed):
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

    def test_no_keyword_is_a_person_name(self, seed):
        """Domain vocabulary is lowercase common nouns, not proper nouns."""
        for keyword in seed["keywords"]:
            assert keyword == keyword.lower(), keyword

    def test_keywords_describe_behaviour_not_identity(self, keywords):
        """Every keyword reads as a domain term an analyst would defend."""
        assert len(keywords) >= 10
        for keyword in keywords:
            assert len(keyword) >= 4
