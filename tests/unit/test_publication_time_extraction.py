"""Publication Time extraction from an article document - issue #42.

Backfilled content has no Publication Time unless the document asserts one, and
the signals differ by outlet. This is the pure-function seam of the Backfill
epic: a document plus a source configuration in, a timezone-aware UTC instant
and the name of the signal that produced it out, or nothing.

The table below is the contract. Each row is one outlet markup shape, recorded
as a committed fixture under tests/fixtures/publication_time/.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from anveshak.scraper.publication_time import (
    NAIVE_TIMESTAMP_ZONES,
    PUBLICATION_TIME_SIGNAL_LABEL,
    SIGNAL_JSONLD_DATE_PUBLISHED,
    SIGNAL_META_ARTICLE_PUBLISHED_TIME,
    SIGNAL_META_DATE,
    SIGNAL_TIME_ELEMENT_DATETIME,
    SIGNAL_TIME_ELEMENT_EPOCH,
    SIGNAL_URL_PATH_DATE,
    SourceConfig,
    SourceTimezonePolicy,
    extract_publication_time,
    publication_time_labels,
    source_config_for,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent.parent / "fixtures" / "publication_time"

# Every fixture asserts the same instant, so a wrong answer is visible as a
# wrong number rather than as one of twenty plausible ones. The two exceptions
# are stated in the table.
INSTANT = datetime(2026, 7, 20, 9, 34, 5, tzinfo=UTC)

# fixture stem, url, declared naive timezone, expected instant, expected signal
OUTLET_TABLE: list[tuple[str, str, str | None, datetime | None, str | None]] = [
    (
        "01_jsonld_newsarticle",
        "https://outlet01.example.in/india/sansad-chalo-detentions",
        None,
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "02_jsonld_graph_reportage",
        "https://outlet02.example.in/story",
        None,
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "03_jsonld_array_blogposting",
        "https://outlet03.example.in/opinion/why-the-march-mattered",
        None,
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "04_jsonld_conflicting_blocks",
        "https://outlet04.example.in/news/sansad-chalo",
        None,
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "05_meta_article_published_property",
        "https://outlet05.example.in/politics/minister-resigns",
        None,
        INSTANT,
        SIGNAL_META_ARTICLE_PUBLISHED_TIME,
    ),
    (
        "06_meta_article_published_name",
        "https://outlet06.example.in/explainer/march-timeline",
        None,
        INSTANT,
        SIGNAL_META_ARTICLE_PUBLISHED_TIME,
    ),
    (
        "07_meta_nonstandard_name",
        "https://outlet07.example.in/news/breakaway-faction",
        None,
        INSTANT,
        SIGNAL_META_DATE,
    ),
    (
        "08_meta_dc_date_issued",
        "https://outlet08.example.in/statement",
        None,
        INSTANT,
        SIGNAL_META_DATE,
    ),
    (
        "09_meta_parsely_pub_date",
        "https://outlet09.example.in/analysis/what-changed",
        None,
        INSTANT,
        SIGNAL_META_DATE,
    ),
    (
        "10_meta_og_published_time",
        "https://outlet10.example.in/photos/march",
        None,
        INSTANT,
        SIGNAL_META_DATE,
    ),
    (
        "11_time_element_datetime",
        "https://outlet11.example.in/live/sansad-chalo",
        None,
        INSTANT,
        SIGNAL_TIME_ELEMENT_DATETIME,
    ),
    (
        "12_time_element_camelcase",
        "https://outlet12.example.in/wire/pti-copy",
        None,
        INSTANT,
        SIGNAL_TIME_ELEMENT_DATETIME,
    ),
    (
        "13_time_epoch_data_attribute",
        "https://outlet13.example.in/live/rolling",
        None,
        INSTANT,
        SIGNAL_TIME_ELEMENT_EPOCH,
    ),
    (
        "14_time_epoch_milliseconds",
        "https://outlet14.example.in/regional/desk",
        None,
        INSTANT,
        SIGNAL_TIME_ELEMENT_EPOCH,
    ),
    (
        "15_jsonld_single_digit_offset",
        "https://outlet15.example.in/court/reporting",
        None,
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "16_meta_pseudo_zone_ist",
        "https://outlet16.example.in/city/desk",
        None,
        INSTANT,
        SIGNAL_META_DATE,
    ),
    (
        "17_naive_utc_outlet",
        "https://outlet17.example.in/national/desk",
        "UTC",
        INSTANT,
        SIGNAL_JSONLD_DATE_PUBLISHED,
    ),
    (
        "18_naive_ist_outlet",
        "https://outlet18.example.in/state/bureau",
        "Asia/Kolkata",
        INSTANT,
        SIGNAL_META_DATE,
    ),
    # A naive value with nothing declared is a configuration gap, not a guess.
    (
        "19_naive_no_declared_zone",
        "https://outlet19.example.in/news/story",
        None,
        None,
        None,
    ),
    # A URL path carries a date and no time, so it is midnight in the outlet's
    # own zone: 2026-07-20 00:00 IST is 2026-07-19 18:30 UTC.
    (
        "20_url_path_date_only",
        "https://outlet20.example.in/2026/07/20/archive-page",
        "Asia/Kolkata",
        datetime(2026, 7, 19, 18, 30, tzinfo=UTC),
        SIGNAL_URL_PATH_DATE,
    ),
]


def _load(stem: str) -> str:
    return (FIXTURES / f"{stem}.html").read_text(encoding="utf-8")


def _config(url: str, zone: str | None) -> SourceConfig:
    return SourceConfig(url=url, naive_timezone=zone)


# ---------------------------------------------------------------------------
# The outlet table
# ---------------------------------------------------------------------------


class TestOutletTable:
    @pytest.mark.parametrize(
        "stem,url,zone,expected_instant,expected_signal",
        OUTLET_TABLE,
        ids=[row[0] for row in OUTLET_TABLE],
    )
    def test_extracts_the_stated_instant_and_signal(
        self,
        stem: str,
        url: str,
        zone: str | None,
        expected_instant: datetime | None,
        expected_signal: str | None,
    ) -> None:
        result = extract_publication_time(_load(stem), _config(url, zone))

        if expected_instant is None:
            assert result is None
            return

        assert result is not None
        assert result.instant == expected_instant
        assert result.signal == expected_signal

    @pytest.mark.parametrize(
        "stem,url,zone,expected_instant,expected_signal",
        OUTLET_TABLE,
        ids=[row[0] for row in OUTLET_TABLE],
    )
    def test_output_is_timezone_aware_utc(
        self,
        stem: str,
        url: str,
        zone: str | None,
        expected_instant: datetime | None,
        expected_signal: str | None,
    ) -> None:
        """Rule: the output is stored timezone-aware in UTC, never local, never naive."""
        result = extract_publication_time(_load(stem), _config(url, zone))
        if result is None:
            return
        assert result.instant.tzinfo is not None
        assert result.instant.utcoffset() == timedelta(0)

    def test_every_fixture_appears_in_the_table(self) -> None:
        """A fixture that no row exercises is a fixture nobody is reading."""
        on_disk = {p.stem for p in FIXTURES.glob("*.html")}
        in_table = {row[0] for row in OUTLET_TABLE}
        assert on_disk == in_table


# ---------------------------------------------------------------------------
# Naive timestamps: deny by default
# ---------------------------------------------------------------------------


class TestNaiveTimestampsAreDeniedByDefault:
    def test_naive_value_with_no_declared_zone_yields_nothing(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05">'
            "</head><body></body></html>"
        )
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_naive_value_is_not_silently_treated_as_utc(self) -> None:
        """The failure this prevents: a five and a half hour shift into the wrong day."""
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is None or result.instant != datetime(2026, 7, 20, 15, 4, 5, tzinfo=UTC)

    def test_a_naive_high_precedence_signal_defers_to_a_lower_one_that_is_usable(self) -> None:
        """An unusable candidate is no candidate. A lower signal with an offset is real data."""
        document = """<html><head>
          <script type="application/ld+json">
          {"@type": "NewsArticle", "datePublished": "2026-07-20 15:04:05"}
          </script>
        </head><body>
          <time datetime="2026-07-20T15:04:05+05:30">20 July</time>
        </body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT
        assert result.signal == SIGNAL_TIME_ELEMENT_DATETIME


# ---------------------------------------------------------------------------
# Malformed offsets are errors, never silent naive values
# ---------------------------------------------------------------------------


class TestMalformedOffsets:
    def test_single_digit_offset_parses_rather_than_raising(self) -> None:
        document = """<html><head>
          <script type="application/ld+json">
          {"@type": "NewsArticle", "datePublished": "2026-07-20T15:04:05+5:30"}
          </script></head><body></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT

    def test_known_pseudo_zone_resolves(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05 IST">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT

    def test_unknown_pseudo_zone_yields_nothing_rather_than_a_naive_value(self) -> None:
        """Dropping an unrecognised zone token would silently produce a naive result."""
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05 PDT">'
            "</head><body></body></html>"
        )
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_out_of_range_offset_yields_nothing(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20T15:04:05+99:99">'
            "</head><body></body></html>"
        )
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_malformed_json_ld_does_not_raise_and_falls_through(self) -> None:
        document = """<html><head>
          <script type="application/ld+json">{"@type": "NewsArticle", datePublished:}</script>
          <meta property="article:published_time" content="2026-07-20T15:04:05+05:30">
        </head><body></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.signal == SIGNAL_META_ARTICLE_PUBLISHED_TIME


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


class TestPrecedence:
    def _document(self) -> str:
        return """<html><head>
          <script type="application/ld+json">
          {"@type": "NewsArticle", "datePublished": "2026-07-20T15:04:05+05:30"}
          </script>
          <meta property="article:published_time" content="2026-07-19T15:04:05+05:30">
          <meta name="publish-date" content="2026-07-18T15:04:05+05:30">
        </head><body>
          <time datetime="2026-07-17T15:04:05+05:30">17 July</time>
        </body></html>"""

    def test_json_ld_wins_over_every_other_signal(self) -> None:
        result = extract_publication_time(self._document(), _config("https://x.example.in/a", None))
        assert result is not None
        assert result.signal == SIGNAL_JSONLD_DATE_PUBLISHED
        assert result.instant == INSTANT

    def test_article_published_time_wins_over_other_date_meta(self) -> None:
        document = """<html><head>
          <meta property="article:published_time" content="2026-07-20T15:04:05+05:30">
          <meta name="publish-date" content="2026-07-18T15:04:05+05:30">
        </head><body></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.signal == SIGNAL_META_ARTICLE_PUBLISHED_TIME
        assert result.instant == INSTANT

    def test_date_meta_wins_over_a_time_element(self) -> None:
        document = """<html><head>
          <meta name="publish-date" content="2026-07-20T15:04:05+05:30">
        </head><body><time datetime="2026-07-17T15:04:05+05:30">17 July</time></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.signal == SIGNAL_META_DATE

    def test_time_element_wins_over_the_url_path(self) -> None:
        document = '<html><body><time datetime="2026-07-20T15:04:05+05:30">x</time></body></html>'
        result = extract_publication_time(
            document, _config("https://x.example.in/2020/01/01/a", "Asia/Kolkata")
        )
        assert result is not None
        assert result.signal == SIGNAL_TIME_ELEMENT_DATETIME
        assert result.instant == INSTANT

    def test_a_json_ld_block_carrying_an_offset_beats_one_without(self) -> None:
        document = """<html><head>
          <script type="application/ld+json">
          {"@type": "NewsArticle", "datePublished": "2026-07-01 00:00:00"}</script>
          <script type="application/ld+json">
          {"@type": "Article", "datePublished": "2026-07-20T15:04:05+05:30"}</script>
        </head><body></body></html>"""
        result = extract_publication_time(
            document, _config("https://x.example.in/a", "Asia/Kolkata")
        )
        assert result is not None
        assert result.instant == INSTANT


# ---------------------------------------------------------------------------
# Nothing recoverable
# ---------------------------------------------------------------------------


class TestNothingRecoverable:
    def test_document_with_no_date_signal_yields_nothing(self) -> None:
        document = "<html><head><title>t</title></head><body><p>text</p></body></html>"
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_empty_document_yields_nothing(self) -> None:
        assert extract_publication_time("", _config("https://x.example.in/a", None)) is None

    def test_epoch_outside_a_plausible_range_is_rejected(self) -> None:
        document = '<html><body><time data-epoch="12">x</time></body></html>'
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None


# ---------------------------------------------------------------------------
# Wayback capture time is not a date signal
# ---------------------------------------------------------------------------


class TestArchiveCaptureIsOnlyAnImpossibilityCheck:
    _DOCUMENT = """<html><head>
      <script type="application/ld+json">
      {"@type": "NewsArticle", "datePublished": "2026-07-20T15:04:05+05:30"}
      </script></head><body></body></html>"""

    def test_a_claim_later_than_the_first_capture_is_rejected(self) -> None:
        result = extract_publication_time(
            self._DOCUMENT,
            _config("https://x.example.in/a", None),
            first_archive_capture=datetime(2026, 7, 1, tzinfo=UTC),
        )
        assert result is None

    def test_a_claim_before_the_first_capture_is_kept(self) -> None:
        result = extract_publication_time(
            self._DOCUMENT,
            _config("https://x.example.in/a", None),
            first_archive_capture=datetime(2026, 8, 1, tzinfo=UTC),
        )
        assert result is not None
        assert result.instant == INSTANT

    def test_the_capture_time_is_never_used_as_the_date_itself(self) -> None:
        document = "<html><body><p>no date anywhere</p></body></html>"
        result = extract_publication_time(
            document,
            _config("https://x.example.in/a", None),
            first_archive_capture=datetime(2026, 8, 1, tzinfo=UTC),
        )
        assert result is None


# ---------------------------------------------------------------------------
# Per-source timezone policy registry
# ---------------------------------------------------------------------------


class TestTimezonePolicyRegistry:
    def test_registry_is_deny_by_default(self) -> None:
        """An outlet absent from the registry gets no zone, so naive values are refused."""
        config = source_config_for("https://never-registered.example.in/a")
        assert config.naive_timezone is None

    def test_every_declared_policy_carries_a_reason(self) -> None:
        """Same shape as EXEMPT_MODELS: a declaration without a reason is not a declaration."""
        for host, policy in NAIVE_TIMESTAMP_ZONES.items():
            assert policy.reason.strip(), f"{host} declares a zone with no reason"
            assert policy.zone.strip(), f"{host} declares a reason with no zone"

    def test_lookup_is_by_host_and_ignores_www_and_case(self) -> None:
        registry = {
            "outlet.example.in": SourceTimezonePolicy(
                zone="Asia/Kolkata", reason="Emits naive IST beside an IST display string."
            )
        }
        for url in (
            "https://outlet.example.in/a",
            "https://www.outlet.example.in/a",
            "https://WWW.Outlet.Example.IN/a",
        ):
            assert source_config_for(url, registry=registry).naive_timezone == "Asia/Kolkata"

    def test_lookup_keeps_the_url_on_the_config(self) -> None:
        config = source_config_for("https://outlet.example.in/2026/07/20/a")
        assert config.url == "https://outlet.example.in/2026/07/20/a"

    def test_a_declared_zone_makes_a_naive_value_usable(self) -> None:
        registry = {
            "outlet.example.in": SourceTimezonePolicy(
                zone="Asia/Kolkata", reason="Emits naive IST."
            )
        }
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05">'
            "</head><body></body></html>"
        )
        config = source_config_for("https://outlet.example.in/a", registry=registry)
        result = extract_publication_time(document, config)
        assert result is not None
        assert result.instant == INSTANT


# ---------------------------------------------------------------------------
# Signal name recorded alongside the date
# ---------------------------------------------------------------------------


class TestSignalIsRecorded:
    def test_labels_helper_names_the_signal(self) -> None:
        result = extract_publication_time(
            _load("01_jsonld_newsarticle"),
            _config("https://outlet01.example.in/a", None),
        )
        assert result is not None
        assert publication_time_labels(result) == {
            PUBLICATION_TIME_SIGNAL_LABEL: SIGNAL_JSONLD_DATE_PUBLISHED
        }

    def test_labels_helper_is_empty_when_there_is_no_date(self) -> None:
        assert publication_time_labels(None) == {}


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


class TestPurity:
    def test_the_same_document_yields_the_same_answer(self) -> None:
        document = _load("01_jsonld_newsarticle")
        config = _config("https://outlet01.example.in/a", None)
        assert extract_publication_time(document, config) == extract_publication_time(
            document, config
        )


# ---------------------------------------------------------------------------
# Grammars other than ISO 8601
# ---------------------------------------------------------------------------


class TestRfc2822Dates:
    def test_rfc_2822_meta_value_parses(self) -> None:
        """The shape an RSS pubDate carries, which some outlets put in a meta tag."""
        document = (
            '<html><head><meta name="pubdate" content="Mon, 20 Jul 2026 15:04:05 +0530">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT

    def test_rfc_2822_with_a_zone_name_parses(self) -> None:
        document = (
            '<html><head><meta name="pubdate" content="Mon, 20 Jul 2026 09:34:05 GMT">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT


# ---------------------------------------------------------------------------
# Declared zones apply to every signal, not only to the top one
# ---------------------------------------------------------------------------


class TestDeclaredZoneAppliesToEverySignal:
    def test_a_naive_time_element_resolves_under_a_declared_zone(self) -> None:
        document = '<html><body><time datetime="2026-07-20 15:04:05">x</time></body></html>'
        result = extract_publication_time(
            document, _config("https://x.example.in/a", "Asia/Kolkata")
        )
        assert result is not None
        assert result.instant == INSTANT
        assert result.signal == SIGNAL_TIME_ELEMENT_DATETIME

    def test_an_unknown_declared_zone_is_refused_rather_than_guessed(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20 15:04:05">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(
            document, _config("https://x.example.in/a", "Asia/Not_A_Real_Zone")
        )
        assert result is None


# ---------------------------------------------------------------------------
# Adversarial markup: every reader is bounded
# ---------------------------------------------------------------------------


class TestAdversarialMarkup:
    """Scraped markup is untrusted input. A hostile page must cost bounded work."""

    def test_a_long_whitespace_run_before_a_zone_token_is_refused_quickly(self) -> None:
        """A regex anchored on a trailing whitespace run backtracks quadratically."""
        value = "x" + " " * 40000 + "abcde"
        document = f'<html><head><meta name="publish-date" content="{value}"></head></html>'
        started = time.monotonic()
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None
        assert time.monotonic() - started < 1.0

    def test_a_value_longer_than_any_timestamp_is_refused(self) -> None:
        document = f'<html><head><meta name="publish-date" content="{"9" * 5000}"></head></html>'
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_a_unicode_digit_epoch_does_not_raise(self) -> None:
        """str.isdigit() accepts superscripts that float() then rejects."""
        for value in ("²", "¹²"):
            document = f'<html><body><time data-epoch="{value}">x</time></body></html>'
            assert (
                extract_publication_time(document, _config("https://x.example.in/a", None)) is None
            )

    def test_deeply_nested_json_ld_does_not_raise_and_falls_through(self) -> None:
        """json.loads raises RecursionError, which is a RuntimeError, not a ValueError."""
        payload = "[" * 200_000
        document = f"""<html><head>
          <script type="application/ld+json">{payload}</script>
          <meta property="article:published_time" content="2026-07-20T15:04:05+05:30">
        </head><body></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.signal == SIGNAL_META_ARTICLE_PUBLISHED_TIME

    def test_many_article_nodes_still_yield_the_offset_bearing_one(self) -> None:
        nodes = ", ".join(
            f'{{"@type": "NewsArticle", "datePublished": "not a date {i}"}}' for i in range(5000)
        )
        document = f"""<html><head>
          <script type="application/ld+json">[{nodes}]</script>
          <meta property="article:published_time" content="2026-07-20T15:04:05+05:30">
        </head><body></body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT

    def test_a_document_beyond_the_limit_is_refused_rather_than_parsed(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20T15:04:05+05:30">'
            "</head><body>" + "padding " * 200 + "</body></html>"
        )
        assert (
            extract_publication_time(
                document, _config("https://x.example.in/a", None), max_document_chars=64
            )
            is None
        )

    def test_a_document_within_the_limit_is_parsed_normally(self) -> None:
        document = (
            '<html><head><meta name="publish-date" content="2026-07-20T15:04:05+05:30">'
            "</head><body></body></html>"
        )
        result = extract_publication_time(
            document, _config("https://x.example.in/a", None), max_document_chars=10_000
        )
        assert result is not None
        assert result.instant == INSTANT

    def test_a_doctype_entity_is_not_resolved(self) -> None:
        """The lxml HTML treebuilder must not read a declared external entity."""
        document = (
            '<!DOCTYPE html [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            '<html><head><meta name="publish-date" content="&xxe;"></head></html>'
        )
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None


# ---------------------------------------------------------------------------
# Only the article's own date signals count
# ---------------------------------------------------------------------------


class TestOtherThingsOnThePageAreNotTheArticlesDate:
    """A widget's timestamp presented as the article's is invented history."""

    @pytest.mark.parametrize(
        "markup",
        [
            '<div class="comment" data-timestamp="1757462400">A reader comment.</div>',
            '<div id="ad-slot" data-ts="1789999999"></div>',
            '<aside class="related" data-epoch="1600000000">Related stories</aside>',
            '<div class="player" data-time="1700000000"></div>',
        ],
        ids=["comment", "ad-slot", "related", "player"],
    )
    def test_an_epoch_outside_a_time_element_is_not_a_date_signal(self, markup: str) -> None:
        document = f"<html><body><article><p>No date.</p></article>{markup}</body></html>"
        assert extract_publication_time(document, _config("https://x.example.in/a", None)) is None

    def test_the_articles_time_element_wins_over_a_widget_carrying_the_same_attribute(
        self,
    ) -> None:
        document = """<html><body>
          <article><time data-epoch="1784540045">20 July 2026</time></article>
          <div class="comment" data-timestamp="1600000000">A reader comment.</div>
        </body></html>"""
        result = extract_publication_time(document, _config("https://x.example.in/a", None))
        assert result is not None
        assert result.instant == INSTANT
        assert result.signal == SIGNAL_TIME_ELEMENT_EPOCH
