"""Corpus format parsing and validation - issue #45.

The corpus file is the committed source of truth for a dataset, so a line that
is wrong has to say so at parse time rather than land in the database as a
plausible row. Every rule here exists because the silent version of it loses
either a date or an item.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.import_corpus import (
    CorpusFormatError,
    load_corpus,
    parse_corpus_line,
)

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).resolve().parents[1] / "fixtures" / "corpus" / "sample_corpus.jsonl"

DATED_LINE = (
    '{"url": "https://outlet-a.example/2026/05/16/a", '
    '"text": "Body text of the article.", '
    '"language": "en", '
    '"published_at": "2026-05-16T09:30:00+00:00", '
    '"published_at_signal": "jsonld_date_published", '
    '"source": {"handle": "https://outlet-a.example/feed", '
    '"name": "Outlet A", "platform": "web"}}'
)

UNDATED_LINE = (
    '{"url": "https://outlet-a.example/opinion/b", '
    '"text": "Body text of the column.", '
    '"source": {"handle": "https://outlet-a.example/feed", '
    '"name": "Outlet A", "platform": "web"}}'
)


def _line(**overrides: object) -> str:
    """A dated line with the given top-level keys replaced or added."""
    import json

    item = json.loads(DATED_LINE)
    for key, value in overrides.items():
        if value is None:
            item.pop(key, None)
        else:
            item[key] = value
    return json.dumps(item)


class TestParsingAWellFormedItem:
    def test_it_reads_every_field(self):
        item = parse_corpus_line(DATED_LINE, 1)

        assert item.url == "https://outlet-a.example/2026/05/16/a"
        assert item.text == "Body text of the article."
        assert item.language == "en"
        assert item.published_at == datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
        assert item.published_at_signal == "jsonld_date_published"
        assert item.source.handle == "https://outlet-a.example/feed"
        assert item.source.name == "Outlet A"
        assert item.source.platform == "web"

    def test_publication_time_is_normalised_to_utc(self):
        item = parse_corpus_line(_line(published_at="2026-05-16T15:00:00+05:30"), 1)

        assert item.published_at == datetime(2026, 5, 16, 9, 30, tzinfo=UTC)

    def test_optional_fields_default_to_none(self):
        item = parse_corpus_line(UNDATED_LINE, 1)

        assert item.published_at is None
        assert item.published_at_signal is None
        assert item.language is None
        assert item.discovery is None
        assert item.body_source is None

    def test_source_credibility_is_optional(self):
        item = parse_corpus_line(DATED_LINE, 1)
        assert item.source.credibility_score is None

        scored = parse_corpus_line(
            _line(
                source={
                    "handle": "https://outlet-a.example/feed",
                    "name": "Outlet A",
                    "platform": "web",
                    "credibility_score": 70.0,
                }
            ),
            1,
        )
        assert scored.source.credibility_score == 70.0


class TestRejectedLines:
    def test_a_naive_publication_time_is_refused(self):
        """The extraction library refuses naive values, and so does the corpus.

        A guessed zone moves roughly a quarter of items into the wrong day.
        """
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(published_at="2026-05-16T09:30:00"), 7)

        assert "line 7" in str(exc.value)
        assert "offset" in str(exc.value).lower()

    def test_a_date_with_no_signal_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(published_at_signal=None), 3)

        assert "published_at_signal" in str(exc.value)

    def test_a_signal_with_no_date_is_refused(self):
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(_line(published_at=None), 3)

    def test_an_unknown_key_is_refused(self):
        """Deny by default: a typo'd key is a dropped field, not a spare one."""
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(publication_time="2026-05-16T09:30:00+00:00"), 4)

        assert "publication_time" in str(exc.value)

    def test_an_unknown_source_key_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(
                _line(
                    source={
                        "handle": "https://outlet-a.example/feed",
                        "name": "Outlet A",
                        "platform": "web",
                        "credibility": 70.0,
                    }
                ),
                5,
            )

        assert "credibility" in str(exc.value)

    def test_a_missing_required_key_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(url=None), 2)

        assert "url" in str(exc.value)

    def test_empty_text_is_refused(self):
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(_line(text="   "), 2)

    def test_a_missing_source_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(source=None), 2)

        assert "source" in str(exc.value)

    def test_malformed_json_names_its_line(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line("{not json", 9)

        assert "line 9" in str(exc.value)


class TestLoadingAFile:
    def test_it_skips_blank_and_comment_lines(self):
        items = load_corpus(SAMPLE)

        assert len(items) == 3
        assert [i.source.name for i in items] == ["Outlet A", "Outlet B", "Outlet B"]

    def test_the_undated_item_survives_the_load(self):
        """An item with no Publication Time is imported, not dropped."""
        items = load_corpus(SAMPLE)

        undated = [i for i in items if i.published_at is None]
        assert len(undated) == 1
        assert undated[0].url.endswith("undated-column")

    def test_a_missing_file_is_an_error(self, tmp_path):
        with pytest.raises(CorpusFormatError):
            load_corpus(tmp_path / "no-such-corpus.jsonl")

    def test_a_bad_line_reports_its_number_in_the_file(self, tmp_path):
        path = tmp_path / "corpus.jsonl"
        path.write_text(f"{DATED_LINE}\n\n{{oops\n", encoding="utf-8")

        with pytest.raises(CorpusFormatError) as exc:
            load_corpus(path)

        assert "line 3" in str(exc.value)


class TestTypeErrorsInALine:
    """Wrong types are named too, because a corpus is edited by hand."""

    def test_a_non_object_line_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line('["not", "an", "object"]', 2)

        assert "line 2" in str(exc.value)

    def test_a_non_object_source_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(source="Outlet A"), 2)

        assert "source" in str(exc.value)

    def test_a_non_string_publication_time_is_refused(self):
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(_line(published_at=1747387800), 2)

    def test_an_unparseable_publication_time_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(published_at="16 May 2026"), 2)

        assert "ISO 8601" in str(exc.value)

    def test_a_trailing_z_is_accepted_as_utc(self):
        item = parse_corpus_line(_line(published_at="2026-05-16T09:30:00Z"), 1)

        assert item.published_at == datetime(2026, 5, 16, 9, 30, tzinfo=UTC)

    def test_a_non_numeric_credibility_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(
                _line(
                    source={
                        "handle": "https://outlet-a.example/feed",
                        "name": "Outlet A",
                        "platform": "web",
                        "credibility_score": "high",
                    }
                ),
                2,
            )

        assert "credibility_score" in str(exc.value)

    def test_an_empty_source_field_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(
                _line(
                    source={
                        "handle": "https://outlet-a.example/feed",
                        "name": "   ",
                        "platform": "web",
                    }
                ),
                2,
            )

        assert "source.name" in str(exc.value)

    def test_a_non_string_language_is_refused(self):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(language=["en", "hi"]), 2)

        assert "language" in str(exc.value)

    def test_a_file_of_only_comments_is_refused(self, tmp_path):
        """An empty import is a corpus that was not written, not a no-op."""
        path = tmp_path / "corpus.jsonl"
        path.write_text("# nothing here yet\n\n", encoding="utf-8")

        with pytest.raises(CorpusFormatError) as exc:
            load_corpus(path)

        assert "no items" in str(exc.value)


class TestHardenedValues:
    """A corpus carries scraped text, so its values are checked, not trusted."""

    def test_a_non_http_url_is_refused(self):
        """The workbench renders the URL as a live link."""
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(url="javascript:alert(1)"), 2)

        assert "scheme" in str(exc.value)

    def test_a_relative_url_is_refused(self):
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(_line(url="/2026/05/16/a"), 2)

    def test_a_nul_byte_in_the_body_is_refused(self):
        """Postgres TEXT refuses NUL, so it would abort a run partway."""
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(text="Body\x00text"), 2)

        assert "control character" in str(exc.value)

    def test_an_escape_sequence_in_the_body_is_refused(self):
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(_line(text="Body\x1b[31mtext"), 2)

    def test_nan_credibility_is_refused(self):
        """NaN passes isinstance and compares false against every threshold."""
        line = DATED_LINE.replace(
            '"platform": "web"}}',
            '"platform": "web", "credibility_score": NaN}}',
        )
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(line, 2)

    def test_infinite_credibility_is_refused(self):
        line = DATED_LINE.replace(
            '"platform": "web"}}',
            '"platform": "web", "credibility_score": Infinity}}',
        )
        with pytest.raises(CorpusFormatError):
            parse_corpus_line(line, 2)

    def test_boolean_credibility_is_refused(self):
        """bool is a subclass of int, so true would otherwise become 1.0."""
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(
                _line(
                    source={
                        "handle": "https://outlet-a.example/feed",
                        "name": "Outlet A",
                        "platform": "web",
                        "credibility_score": True,
                    }
                ),
                2,
            )

        assert "credibility_score" in str(exc.value)

    @pytest.mark.parametrize("score", [-1.0, 100.1, 10000])
    def test_credibility_outside_the_range_is_refused(self, score):
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(
                _line(
                    source={
                        "handle": "https://outlet-a.example/feed",
                        "name": "Outlet A",
                        "platform": "web",
                        "credibility_score": score,
                    }
                ),
                2,
            )

        assert "0.0 to 100.0" in str(exc.value)

    def test_an_unknown_key_name_is_quoted_back(self):
        """A raw key name would carry terminal escapes into the console."""
        with pytest.raises(CorpusFormatError) as exc:
            parse_corpus_line(_line(**{"\x1b[31mevil": "x"}), 2)

        assert "\\x1b" in str(exc.value)


class TestFileBounds:
    """Each bound reports itself, so a refusal is never read as a short corpus."""

    def test_an_oversized_line_is_refused(self, tmp_path, monkeypatch):
        import scripts.import_corpus as importer

        monkeypatch.setattr(importer, "MAX_LINE_BYTES", 64)
        path = tmp_path / "corpus.jsonl"
        path.write_text(DATED_LINE + "\n", encoding="utf-8")

        with pytest.raises(CorpusFormatError) as exc:
            load_corpus(path)

        assert "byte bound" in str(exc.value)

    def test_an_oversized_file_is_refused(self, tmp_path, monkeypatch):
        import scripts.import_corpus as importer

        monkeypatch.setattr(importer, "MAX_CORPUS_BYTES", 16)
        path = tmp_path / "corpus.jsonl"
        path.write_text(DATED_LINE + "\n", encoding="utf-8")

        with pytest.raises(CorpusFormatError) as exc:
            load_corpus(path)

        assert "byte bound" in str(exc.value)

    def test_too_many_items_are_refused(self, tmp_path, monkeypatch):
        import scripts.import_corpus as importer

        monkeypatch.setattr(importer, "MAX_ITEMS", 1)
        path = tmp_path / "corpus.jsonl"
        path.write_text(f"{DATED_LINE}\n{UNDATED_LINE}\n", encoding="utf-8")

        with pytest.raises(CorpusFormatError) as exc:
            load_corpus(path)

        assert "more than 1 items" in str(exc.value)
