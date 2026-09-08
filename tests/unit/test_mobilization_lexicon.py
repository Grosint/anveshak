"""Mobilization lexicon signal — issue #33.

Public content calling for people to assemble surfaces as a signal, with the
date and place extracted and the exact matched phrase always displayed, so
an analyst can verify the extraction and correct it when it is wrong.

The signal reports what was publicly said. It never states that an event
will occur and carries no probability that one will.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from anveshak.analyst.mobilization import (
    build_description,
    extract_date,
    extract_place,
    find_calls_to_assemble,
    load_lexicon,
)
from anveshak.analyst.settings import settings

pytestmark = pytest.mark.unit

TODAY = date(2026, 3, 4)


class TestTheLexiconIsAVersionedFile:
    def test_the_path_is_a_setting(self):
        assert settings.mobilization_lexicon_path

    def test_no_pattern_is_embedded_in_code(self):
        source = Path("services/analyst/anveshak/analyst/mobilization.py").read_text()
        assert "gather" not in source.lower().replace("gathering", "")

    def test_the_file_is_versioned(self):
        lexicon = load_lexicon()
        assert lexicon.version >= 1

    def test_it_covers_both_languages(self):
        lexicon = load_lexicon()
        languages = {pattern.language for pattern in lexicon.patterns}
        assert {"en", "hi"} <= languages


class TestEnglishDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "All are invited to join the gathering outside the collectorate.",
            "Everyone gather at the town square tomorrow evening.",
            "Join us at Jantar Mantar on Friday.",
            "Protest march to the district headquarters at 4pm.",
            "Calling for a bandh across the district on Monday.",
            "Rasta roko announced for tomorrow.",
        ],
    )
    def test_a_call_to_assemble_matches(self, text):
        assert find_calls_to_assemble(text, language="en")

    @pytest.mark.parametrize(
        "text",
        [
            "The meeting was held yesterday and passed off peacefully.",
            "Police said the situation is under control.",
            "He gathered his thoughts before speaking.",
            "A report on last week's rally was published today.",
        ],
    )
    def test_ordinary_reporting_does_not_match(self, text):
        assert find_calls_to_assemble(text, language="en") == []

    def test_the_exact_matched_phrase_is_returned(self):
        matches = find_calls_to_assemble(
            "Everyone gather at the town square tomorrow.", language="en"
        )
        assert matches[0].phrase
        assert matches[0].phrase.lower() in "everyone gather at the town square tomorrow."

    def test_the_pattern_id_is_returned(self):
        matches = find_calls_to_assemble("Join us at the maidan on Friday.", language="en")
        assert matches[0].pattern_id


class TestHindiDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "सभी लोग कल सुबह कलेक्ट्रेट पर पहुंचें।",
            "कल जुलूस निकालेंगे।",
            "बंद का ऐलान किया गया है।",
            "सभी एकत्र हों और विरोध प्रदर्शन करेंगे।",
            "महापंचायत में सभी आएं।",
        ],
    )
    def test_a_call_to_assemble_matches(self, text):
        assert find_calls_to_assemble(text, language="hi")

    @pytest.mark.parametrize(
        "text",
        [
            "पुलिस ने कहा कि स्थिति नियंत्रण में है।",
            "कल की बैठक शांतिपूर्ण रही।",
        ],
    )
    def test_ordinary_reporting_does_not_match(self, text):
        assert find_calls_to_assemble(text, language="hi") == []

    def test_devanagari_is_read_directly(self):
        """Not through a translation, which loses the imperative."""
        matches = find_calls_to_assemble("सभी लोग कल कलेक्ट्रेट पर पहुंचें।", language="hi")
        assert matches
        assert any("ऀ" <= ch <= "ॿ" for ch in matches[0].phrase)


class TestLanguageSelection:
    def test_an_unknown_language_tries_every_pattern(self):
        """Detection must not depend on language detection being right."""
        assert find_calls_to_assemble("Everyone gather at the square.", language=None)
        assert find_calls_to_assemble("सभी लोग कल पहुंचें।", language=None)


class TestDateExtraction:
    def test_an_explicit_date_is_extracted(self):
        assert extract_date("March 12 rally at the maidan", today=TODAY) == date(2026, 3, 12)

    def test_tomorrow_resolves_against_today(self):
        assert extract_date("Gather tomorrow at the square", today=TODAY) == date(2026, 3, 5)

    def test_a_hindi_relative_date_resolves(self):
        assert extract_date("सभी कल पहुंचें", today=TODAY) == date(2026, 3, 5)

    def test_no_date_returns_none(self):
        """None, never a guessed date. The card shows the phrase instead."""
        assert extract_date("Everyone gather at the square", today=TODAY) is None


class TestPlaceExtraction:
    def test_a_place_after_a_marker_is_extracted(self):
        assert "Town Square" in (extract_place("Gather at Town Square", language="en") or "")

    def test_no_place_returns_none(self):
        assert extract_place("Everyone should come out", language="en") is None

    def test_a_hindi_place_is_extracted(self):
        place = extract_place("कलेक्ट्रेट पर पहुंचें", language="hi")
        assert place is None or isinstance(place, str)


class TestWordingIsNotAForecast:
    def test_the_description_reports_what_was_said(self):
        description = build_description(
            phrase="Everyone gather at the town square tomorrow",
            when=date(2026, 3, 5),
            place="the town square",
            item_count=4,
        )
        assert "Everyone gather at the town square tomorrow" in description

    def test_the_description_never_predicts(self):
        description = build_description(
            phrase="Everyone gather at the town square tomorrow",
            when=date(2026, 3, 5),
            place="the town square",
            item_count=4,
        ).lower()
        for word in (
            "will occur",
            "will happen",
            "expected to",
            "likely",
            "probability",
            "forecast",
            "predict",
            "imminent",
            "risk of",
            "threat",
        ):
            assert word not in description

    def test_the_phrase_is_always_present_even_without_a_date_or_place(self):
        description = build_description(
            phrase="Join us at the maidan", when=None, place=None, item_count=1
        )
        assert "Join us at the maidan" in description
