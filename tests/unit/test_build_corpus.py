"""Corpus build selection, refusals and hand placement - issue #54.

A build decides what a demonstration is made of, so every rule here is about a
wrong item reaching the corpus quietly. An impostor domain's article attributed
to the movement, an outlet with no historic route reported as an outlet with no
history, and a hand-placed item with no citation are the three that would each
survive review as a plausible row.

The network half is covered by the collection run itself. These are the pure
parts, so they run without Docker and without a fetch.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from anveshak.scraper.archive_backfill import OutletBackfill

from scripts.build_corpus import (
    BuildError,
    CollectedItem,
    collect_news,
    corpus_record,
    is_impostor,
    matches_keywords,
    read_hand_placed,
    summarise,
    verify_outlets_configured,
    verify_pinned,
)
from scripts.corpus_plan import DEFAULT_PLAN_PATH, NewsOutlet, load_plan

pytestmark = pytest.mark.unit

PLAN = load_plan(DEFAULT_PLAN_PATH)

OUTLET = NewsOutlet(
    host="outlet.example",
    name="Outlet",
    handle="https://outlet.example/feed",
)


def _pinned(**changes: object) -> object:
    """The committed plan with its collection targets filled in."""
    from dataclasses import replace

    from scripts.corpus_plan import YouTubeTarget

    base = dict(
        canonical_domain="movement.example",
        impostor_domains=("movement-official.example",),
        keywords=("cockroach janta party", "कॉकरोच जनता पार्टी"),
        news_outlets=(OUTLET,),
        youtube=YouTubeTarget(channel_id="UC000", backfill_count=200),
        telegram_channel="@movement",
        x_handle="@movement",
        counter_narrative_handles=("@satire",),
    )
    base.update(changes)
    return replace(PLAN, **base)  # type: ignore[arg-type]


def _item(
    url: str = "https://outlet.example/2026/05/16/founded",
    text: str = "The Cockroach Janta Party was founded today.",
    published_at: datetime | None = datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
) -> CollectedItem:
    return CollectedItem(
        url=url,
        text=text,
        source_handle=OUTLET.handle,
        source_name=OUTLET.name,
        source_platform=OUTLET.platform,
        published_at=published_at,
        published_at_signal="jsonld_date_published" if published_at else None,
        discovery="archive_sitemap",
        body_source="publisher",
    )


# ---------------------------------------------------------------------------
# Refusals before anything is fetched
# ---------------------------------------------------------------------------


class TestRefusalsBeforeCollection:
    def test_an_unpinned_target_stops_the_build(self) -> None:
        # A guessed handle collects somebody else's content and attributes it
        # to the movement, which is a corpus that manufactures its own
        # evidence rather than a build that failed.
        with pytest.raises(BuildError) as exc:
            verify_pinned(PLAN)
        assert "collection.keywords" in str(exc.value)
        assert "collection.news.outlets" in str(exc.value)

    def test_a_social_target_alone_does_not_stop_a_news_build(self) -> None:
        # The social layers are collected by the adapters with their own
        # credentials, and the hand-placed layer is transcribed, so a news
        # build blocked on a channel identifier it never reads would be a
        # refusal nobody can act on from here. It is reported instead.
        from dataclasses import replace

        from scripts.corpus_plan import YouTubeTarget

        plan = replace(
            _pinned(),
            youtube=YouTubeTarget(channel_id=None, backfill_count=200),
            telegram_channel=None,
        )
        verify_pinned(plan)
        assert "collection.social.youtube.channel_id" in plan.unpinned_for_social()

    def test_an_empty_impostor_list_stops_the_build(self) -> None:
        # An empty list is a list nobody filled in, not a finding that no
        # squatter exists, and it runs a filter that matches nothing.
        from dataclasses import replace

        with pytest.raises(BuildError) as exc:
            verify_pinned(replace(_pinned(), impostor_domains=()))
        assert "collection.impostor_domains" in str(exc.value)

    def test_a_pinned_plan_passes(self) -> None:
        verify_pinned(_pinned())

    def test_an_outlet_with_no_historic_route_stops_the_build(self) -> None:
        # OUTLET_BACKFILL is deny-by-default, so an unconfigured outlet
        # discovers nothing and reports as an outlet that published nothing in
        # the window. That is indistinguishable from a quiet outlet.
        with pytest.raises(BuildError) as exc:
            verify_outlets_configured(_pinned(), registry={})
        assert "outlet.example" in str(exc.value)

    def test_a_configured_outlet_passes(self) -> None:
        verify_outlets_configured(_pinned(), registry={"outlet.example": object()})


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_keyword_match_is_case_insensitive_and_matches_hindi(self) -> None:
        assert matches_keywords("The COCKROACH Janta Party met", PLAN_KEYWORDS)
        assert matches_keywords("कॉकरोच जनता पार्टी की बैठक", PLAN_KEYWORDS)

    def test_an_item_naming_nothing_in_the_corpus_is_not_selected(self) -> None:
        assert not matches_keywords("A monsoon update from the capital", PLAN_KEYWORDS)

    def test_an_impostor_domain_is_rejected(self) -> None:
        plan = _pinned()
        assert is_impostor("https://movement-official.example/post/1", plan)
        assert is_impostor("https://www.movement-official.example/post/1", plan)

    def test_a_subdomain_of_an_impostor_domain_is_rejected(self) -> None:
        # A squatter serving from a subdomain is the same squatter.
        assert is_impostor("https://news.movement-official.example/p/1", _pinned())

    def test_the_canonical_domain_is_not_an_impostor(self) -> None:
        assert not is_impostor("https://movement.example/statement", _pinned())


PLAN_KEYWORDS = ("cockroach janta party", "कॉकरोच जनता पार्टी")

# The entry the scraper keys its historic route by. Discovery and fetch are
# injected, but the host on it is real: the build checks a discovered URL
# against it before attributing the article to the outlet's Source.
BACKFILL = OutletBackfill(
    host="outlet.example",
    path_date_format="slash_ymd",
    reason="test fixture",
)
REGISTRY = {"outlet.example": BACKFILL}


# ---------------------------------------------------------------------------
# The record written to the corpus
# ---------------------------------------------------------------------------


class TestCorpusRecord:
    def test_a_dated_item_carries_its_date_and_the_signal_that_produced_it(self) -> None:
        record = corpus_record(_item())
        assert record["published_at"] == "2026-05-16T09:30:00+00:00"
        assert record["published_at_signal"] == "jsonld_date_published"

    def test_an_undated_item_omits_both_date_keys(self) -> None:
        # The corpus format refuses a date without its signal, and a null
        # written for either would be an assertion the item does not support.
        record = corpus_record(_item(published_at=None))
        assert "published_at" not in record
        assert "published_at_signal" not in record

    def test_the_record_parses_as_a_corpus_line(self) -> None:
        import json

        from scripts.import_corpus import parse_corpus_line

        item = parse_corpus_line(json.dumps(corpus_record(_item())), 1)
        assert item.url == "https://outlet.example/2026/05/16/founded"
        assert item.source.handle == OUTLET.handle


# ---------------------------------------------------------------------------
# Hand-placed items
# ---------------------------------------------------------------------------


class TestHandPlaced:
    def _write(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "hand_placed.jsonl"
        path.write_text(body, encoding="utf-8")
        return path

    ITEM = (
        '{"url": "https://social.example/p/1", "text": "A post the coverage quotes.", '
        '"published_at": "2026-06-04T11:00:00+05:30", "published_at_signal": "cited_reporting", '
        '"source": {"handle": "@movement", "name": "Movement", "platform": "instagram"}}'
    )

    def test_a_cited_item_is_read_with_its_citation(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path, f"# Cited: Outlet, 4 June 2026, movement statement\n{self.ITEM}\n"
        )
        placed = read_hand_placed(path)
        assert len(placed) == 1
        assert "Outlet, 4 June 2026" in placed[0].citation

    def test_an_item_with_no_citation_is_refused(self, tmp_path: Path) -> None:
        # A hand-placed item without the reporting it came from is a
        # fabricated timestamp inside a corpus whose whole claim is that it
        # fabricates none.
        path = self._write(tmp_path, f"{self.ITEM}\n")
        with pytest.raises(BuildError) as exc:
            read_hand_placed(path)
        assert "line 1" in str(exc.value)

    def test_the_citation_does_not_carry_to_the_next_item(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, f"# Cited: Outlet\n{self.ITEM}\n{self.ITEM}\n")
        with pytest.raises(BuildError) as exc:
            read_hand_placed(path)
        assert "line 3" in str(exc.value)

    def test_a_hand_placed_item_from_an_impostor_domain_is_refused(self, tmp_path: Path) -> None:
        # The hand-placed layer is where a squatter URL is most plausible,
        # because it is transcribed from coverage rather than discovered from
        # an outlet the plan named.
        item = self.ITEM.replace(
            "https://social.example/p/1", "https://movement-official.example/p/1"
        )
        path = self._write(tmp_path, f"# Cited: Outlet\n{item}\n")
        with pytest.raises(BuildError) as exc:
            read_hand_placed(path, _pinned())
        assert "movement-official.example" in str(exc.value)

    def test_a_malformed_item_is_refused_by_the_corpus_format(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '# Cited: Outlet\n{"url": "https://social.example/p/1"}\n')
        with pytest.raises(BuildError):
            read_hand_placed(path)


# ---------------------------------------------------------------------------
# The file that gets written
# ---------------------------------------------------------------------------


class TestWriteCorpus:
    def _hand_placed(self, published_at: datetime) -> object:
        from scripts.build_corpus import HandPlaced
        from scripts.import_corpus import parse_corpus_line

        line = (
            '{"url": "https://social.example/p/1", "text": "A post.", '
            f'"published_at": "{published_at.isoformat()}", '
            '"published_at_signal": "cited_reporting", '
            '"source": {"handle": "@movement", "name": "Movement", "platform": "instagram"}}'
        )
        return HandPlaced(
            item=parse_corpus_line(line, 1), citation="Outlet, 4 June 2026", line_number=1
        )

    def test_both_layers_are_written_in_publication_order(self, tmp_path: Path) -> None:
        # The hand-placed layer covers the period the movement's account was
        # blocked. A file that appends it at the end reads as though that
        # happened after the split.
        from scripts.build_corpus import write_corpus

        path = tmp_path / "corpus.jsonl"
        written = write_corpus(
            path,
            [
                _item(
                    url="https://outlet.example/a", published_at=datetime(2026, 5, 16, tzinfo=UTC)
                ),
                _item(
                    url="https://outlet.example/b", published_at=datetime(2026, 7, 20, tzinfo=UTC)
                ),
            ],
            [self._hand_placed(datetime(2026, 6, 4, 11, tzinfo=UTC))],  # type: ignore[list-item]
            PLAN,
        )
        assert written == 3
        items = [line for line in path.read_text().splitlines() if not line.startswith("#")]
        dates = [json.loads(line)["published_at"][:10] for line in items]
        assert dates == ["2026-05-16", "2026-06-04", "2026-07-20"]

    def test_a_hand_placed_item_keeps_its_citation_on_the_line_above(self, tmp_path: Path) -> None:
        # The citation is the fabrication guard's last mile: an item in the
        # committed corpus without it cannot be checked by a reviewer.
        from scripts.build_corpus import write_corpus

        path = tmp_path / "corpus.jsonl"
        write_corpus(path, [], [self._hand_placed(datetime(2026, 6, 4, 11, tzinfo=UTC))], PLAN)  # type: ignore[list-item]
        lines = path.read_text().splitlines()
        placed = next(index for index, line in enumerate(lines) if "social.example" in line)
        assert lines[placed - 1].startswith("# Cited: Outlet, 4 June 2026")

    def test_the_written_file_parses_as_a_corpus(self, tmp_path: Path) -> None:
        from scripts.build_corpus import write_corpus
        from scripts.import_corpus import load_corpus

        path = tmp_path / "corpus.jsonl"
        write_corpus(
            path, [_item()], [self._hand_placed(datetime(2026, 6, 4, 11, tzinfo=UTC))], PLAN
        )  # type: ignore[list-item]
        assert len(load_corpus(path)) == 2


# ---------------------------------------------------------------------------
# The build summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_items_are_counted_into_their_phase(self) -> None:
        summary = summarise(
            [_item(), _item(published_at=datetime(2026, 7, 20, 12, tzinfo=UTC))], PLAN
        )
        assert summary.per_phase[1] == 1
        assert summary.per_phase[4] == 1

    def test_a_phase_with_no_items_is_named(self) -> None:
        # A phase the corpus does not cover is a stage of the Replay that
        # imports nothing, and the arc then shows a quiet week the story did
        # not have.
        summary = summarise([_item()], PLAN)
        assert summary.empty_phases == [2, 3, 4, 5, 6, 7]

    def test_undated_items_are_counted_rather_than_dropped(self) -> None:
        summary = summarise([_item(published_at=None)], PLAN)
        assert summary.undated == 1

    def test_a_hand_placed_item_counts_towards_its_phase(self) -> None:
        # A phase the news route missed and the hand-placed layer covers is a
        # covered phase, and reporting it empty would stop the build.
        from scripts.build_corpus import collected_of
        from scripts.import_corpus import parse_corpus_line

        line = (
            '{"url": "https://social.example/p/1", "text": "A post.", '
            '"published_at": "2026-06-04T11:00:00+00:00", '
            '"published_at_signal": "cited_reporting", '
            '"source": {"handle": "@movement", "name": "Movement", "platform": "instagram"}}'
        )
        summary = summarise([collected_of(parse_corpus_line(line, 1))], PLAN)
        assert summary.per_phase[2] == 1

    def test_an_item_published_outside_the_arc_is_counted(self) -> None:
        summary = summarise([_item(published_at=datetime(2026, 4, 1, tzinfo=UTC))], PLAN)
        assert summary.outside_arc == 1


# ---------------------------------------------------------------------------
# News collection
# ---------------------------------------------------------------------------


class TestCollectNews:
    async def test_only_matching_items_inside_the_arc_are_collected(self) -> None:
        from types import SimpleNamespace

        discovered = [
            SimpleNamespace(url="https://outlet.example/2026/05/16/a"),
            SimpleNamespace(url="https://outlet.example/2026/05/17/b"),
            SimpleNamespace(url="https://movement-official.example/2026/05/17/c"),
        ]
        bodies = {
            "https://outlet.example/2026/05/16/a": (
                "The Cockroach Janta Party was founded today.",
                datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
            ),
            "https://outlet.example/2026/05/17/b": (
                "A monsoon update from the capital.",
                datetime(2026, 5, 17, 9, 30, tzinfo=UTC),
            ),
            "https://movement-official.example/2026/05/17/c": (
                "The Cockroach Janta Party, says the squatter site.",
                datetime(2026, 5, 17, 9, 30, tzinfo=UTC),
            ),
        }

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            assert window.start == PLAN.start_date
            assert window.end == PLAN.freeze_date
            return discovered

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            text, published_at = bodies[item.url]
            return SimpleNamespace(
                url=item.url,
                title="",
                raw_text=text,
                discovery="archive_sitemap",
                body_source="publisher",
                published_at=published_at,
                published_at_signal="jsonld_date_published",
            )

        collected = await collect_news(
            _pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY
        )
        assert [item.url for item in collected] == ["https://outlet.example/2026/05/16/a"]

    async def test_an_off_host_discovered_url_is_not_attributed_to_the_outlet(self) -> None:
        # A sitemap lists whatever its publisher put in it, and everything
        # collected is attributed to the outlet's Source. A third-party URL
        # under a trusted outlet inflates the independent source count.
        from types import SimpleNamespace

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            return [SimpleNamespace(url="https://syndicated.example/2026/05/16/a")]

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("an off-host URL must not be fetched as the outlet's own")

        collected = await collect_news(
            _pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY
        )
        assert collected == []

    async def test_an_item_the_corpus_format_would_refuse_is_dropped_not_fatal(self) -> None:
        # Scraped text is untrusted. An unhandled refusal at write time would
        # discard a run that had already fetched the whole arc.
        from types import SimpleNamespace

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            return [
                SimpleNamespace(url="https://outlet.example/2026/05/16/a"),
                SimpleNamespace(url="https://outlet.example/2026/05/17/b"),
            ]

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            body = "The Cockroach Janta Party was founded today."
            if item.url.endswith("/a"):
                body += "\x07"  # a control character the format refuses
            return SimpleNamespace(
                url=item.url,
                title="",
                raw_text=body,
                discovery="archive_sitemap",
                body_source="publisher",
                published_at=datetime(2026, 5, 16, tzinfo=UTC),
                published_at_signal="jsonld_date_published",
            )

        collected = await collect_news(
            _pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY
        )
        assert [item.url for item in collected] == ["https://outlet.example/2026/05/17/b"]

    async def test_one_rate_limiter_is_shared_across_the_run(self) -> None:
        # A limiter per call is no limiter: the run fetches an outlet's whole
        # history at full speed from the collector's address.
        from types import SimpleNamespace

        limiters = []

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            limiters.append(kwargs["limiter"])
            return [SimpleNamespace(url="https://outlet.example/2026/05/16/a")]

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            limiters.append(kwargs["limiter"])
            return None

        await collect_news(_pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY)
        assert len(limiters) == 2
        assert limiters[0] is limiters[1]

    async def test_an_article_with_no_body_is_skipped(self) -> None:
        from types import SimpleNamespace

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            return [SimpleNamespace(url="https://outlet.example/2026/05/16/a")]

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            return None

        assert (
            await collect_news(
                _pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY
            )
            == []
        )

    async def test_the_same_url_discovered_twice_is_collected_once(self) -> None:
        from types import SimpleNamespace

        async def fake_discover(outlet, window, **kwargs):  # type: ignore[no-untyped-def]
            return [
                SimpleNamespace(url="https://outlet.example/2026/05/16/a"),
                SimpleNamespace(url="https://outlet.example/2026/05/16/a"),
            ]

        async def fake_fetch(item, outlet, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                url=item.url,
                title="",
                raw_text="The Cockroach Janta Party was founded today.",
                discovery="archive_sitemap",
                body_source="publisher",
                published_at=datetime(2026, 5, 16, tzinfo=UTC),
                published_at_signal="jsonld_date_published",
            )

        collected = await collect_news(
            _pinned(), discover=fake_discover, fetch=fake_fetch, registry=REGISTRY
        )
        assert len(collected) == 1


def test_the_arc_window_is_both_ends_inclusive() -> None:
    assert PLAN.phase_on(date(2026, 9, 10)) is not None
