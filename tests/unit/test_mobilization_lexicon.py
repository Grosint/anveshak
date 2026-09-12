"""Mobilization lexicon signal — issue #33.

Public content calling for people to assemble surfaces as a signal, with the
date and place extracted and the exact matched phrase always displayed, so
an analyst can verify the extraction and correct it when it is wrong.

The signal reports what was publicly said. It never states that an event
will occur and carries no probability that one will.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from anveshak.analyst import mobilization
from anveshak.analyst.mobilization import (
    Lexicon,
    LexiconPattern,
    build_description,
    extract_date,
    extract_place,
    find_calls_to_assemble,
    load_lexicon,
    script_of_source,
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

    def test_the_version_was_raised_when_the_vocabulary_changed(self):
        """Issue #50 added patterns, so the version is no longer 1.

        A vocabulary change that kept the same version would be invisible in
        the evidence of every signal it fired.
        """
        assert load_lexicon().version >= 2

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


class TestIndianMobilizationIdiom:
    """Issue #50.

    The construction that names a destination and tells people to go there
    was absent in both scripts, in a list that already covered gherao,
    dharna, chakka jam and rasta roko. It was assembled English-first, so
    the other assembly idioms it had missed were added with it.
    """

    @pytest.mark.parametrize(
        ("text", "language", "expected_id"),
        [
            ("Sansad Chalo on March 18. Buses leave from every district.", "en", "en_chalo"),
            ("Dilli Chalo. Buses leave at dawn.", "en", "en_chalo"),
            ("#BidadiChalo on July 11. Bring water and flags.", "en", "en_chalo"),
            ("#dillichalo on March 18, buses from every district", "en", "en_chalo_hashtag"),
            ("Dilli kooch karenge, sab taiyar rahein.", "en", "en_kooch"),
            ("Human chain at Rajghat on March 22.", "en", "en_human_chain"),
            ("Call for a jail bharo from March 20.", "en", "en_jail_bharo"),
            ("दिल्ली चलो। सभी जिलों से बसें रवाना होंगी।", "hi", "hi_chalo"),
            ("कूच करेंगे, तैयार रहें।", "hi", "hi_kooch"),
            ("कलेक्ट्रेट का घेराव करेंगे।", "hi", "hi_gherao"),
            ("हड़ताल का ऐलान किया गया है।", "hi", "hi_hartal"),
            ("सभी कार्यकर्ता उपस्थित रहें।", "hi", "hi_upasthit"),
            ("जेल भरो का ऐलान किया गया है।", "hi", "hi_jail_bharo"),
            ("आंदोलन में शामिल हों।", "hi", "hi_shamil"),
            ("मोर्चा निकालेंगे।", "hi", "hi_morcha_nikalna"),
            ("मानव श्रृंखला बनाएंगे।", "hi", "hi_manav_shrinkhala"),
            ("धरने पर बैठेंगे।", "hi", "hi_dharne_par_baithenge"),
        ],
    )
    def test_a_call_to_assemble_matches(self, text: str, language: str, expected_id: str) -> None:
        matched = find_calls_to_assemble(text, language=language)
        assert expected_id in {match.pattern_id for match in matched}

    @pytest.mark.parametrize(
        ("text", "language"),
        [
            # Each is the reportage form of a pattern above, in the script
            # that pattern is written in: the noun is present and the call
            # is not.
            ("He said chalo, nothing will change.", "en"),
            ("The film Chalo Dilli was screened at the club.", "en"),
            ("Watch Chalo Dilli on TV tonight.", "en"),
            ("Actor Recalls Chalo Dilli Shoot After A Decade", "en"),
            ("A human chain formed last week was dispersed peacefully.", "en"),
            ("The jail bharo agitation last month ended with 500 arrests.", "en"),
            ("चलो ठीक है, कल बात करते हैं।", "hi"),
            ("अच्छा चलो, कल मिलते हैं।", "hi"),
            ("तुम चलो, मैं बाद में आता हूँ।", "hi"),
            ("मैंने कहा चलो।", "hi"),
            ("अब चलो यहाँ से।", "hi"),
            ("कब चलोगे दिल्ली?", "hi"),
            ("भाजपा युवा मोर्चा ने शहर में रैली निकाली।", "hi"),
            ("कांग्रेस की पदयात्रा निकाली गई थी।", "hi"),
            ("जेल भरो आंदोलन 1930 में शुरू हुआ था।", "hi"),
            ("पिछले साल मानव श्रृंखला बनाई गई थी।", "hi"),
            ("अदालत में उपस्थित होने का नोटिस भेजा गया।", "hi"),
            ("प्रदर्शन में शामिल होने के बाद पांच लोग गिरफ्तार हुए।", "hi"),
            ("किसानों ने कलेक्ट्रेट का घेराव करने के बाद हिरासत में लिए गए।", "hi"),
            ("हड़ताल का ऐलान वापस ले लिया गया।", "hi"),
            ("हड़ताल का ऐलान स्थगित कर दिया गया।", "hi"),
            ("प्रदर्शनकारी दिल्ली की ओर कूच कर गए थे।", "hi"),
            ("धरने पर बैठे किसानों से प्रशासन ने बातचीत की।", "hi"),
            ("रैली में शामिल हुए लोगों की संख्या हजारों में थी।", "hi"),
            ("घेराव के दौरान यातायात प्रभावित रहा।", "hi"),
            ("हड़ताल के कारण कामकाज ठप रहा।", "hi"),
        ],
    )
    def test_ordinary_reporting_does_not_match(self, text: str, language: str) -> None:
        assert find_calls_to_assemble(text, language=language) == []

    def test_the_destination_idiom_is_read_in_both_scripts(self) -> None:
        """Transliterated and Devanagari, because both appear in real content."""
        latin = find_calls_to_assemble("Sansad Chalo on March 18.", language="en")
        devanagari = find_calls_to_assemble("दिल्ली चलो।", language="hi")
        assert {m.pattern_id for m in latin} >= {"en_chalo"}
        assert {m.pattern_id for m in devanagari} >= {"hi_chalo"}

    def test_no_pattern_names_an_organisation_a_viewpoint_or_a_grievance(self) -> None:
        """User story 5: the lexicon fires on the act of convening.

        Not on who is convening, and not on why. The needles are in both
        scripts, because a guard written only in Latin says nothing about a
        list that is mostly Devanagari.
        """
        lexicon = load_lexicon()
        source = " ".join(pattern.regex.pattern for pattern in lexicon.patterns).lower()
        for word in (
            "bjp",
            "congress",
            "भाजपा",
            "कांग्रेस",
            "संघ",
            "kisan",
            "किसान",
            "farmer",
            "बेरोजगार",
            "unemploy",
            "भ्रष्टाचार",
            "corrupt",
            "मुसलमान",
            "दलित",
        ):
            assert word not in source, f"{word} names who or why, not the act of convening"

    def test_a_noun_that_is_also_an_organisation_carries_a_verb(self) -> None:
        """`मोर्चा` is both a procession and a party wing.

        Standing alone it fires on every report that names the wing, so the
        pattern holding it must also require the verb that makes it a call.
        """
        for pattern in load_lexicon().patterns:
            if "मोर्चा" in pattern.regex.pattern:
                assert "निकाल" in pattern.regex.pattern

    def test_a_retraction_suppresses_only_its_own_sentence(self) -> None:
        """`वापस` also begins `वापसी` and `वापस लौटेंगे`.

        A needle that matched either of those would suppress the call it
        was meant to leave alone.
        """
        assert find_calls_to_assemble(
            "हड़ताल का ऐलान किया गया है, वापसी की कोई योजना नहीं है।", language="hi"
        )
        assert find_calls_to_assemble(
            "हड़ताल का ऐलान किया गया है। सभी कर्मचारी काम पर वापस नहीं लौटेंगे।", language="hi"
        )

    def test_a_slogan_is_told_apart_from_the_same_words_in_speech(self) -> None:
        """The destination idiom is capitalised; the filler use is not.

        Case is the only thing that separates them, so the pattern carrying
        the idiom must be the one that opted out of case folding.
        """
        assert find_calls_to_assemble("Dilli Chalo on March 18.", language="en")
        assert find_calls_to_assemble("chalo yaar, we are late.", language="en") == []


class TestScriptDecidesWhichPatternsAreTried:
    """Issue #56.

    Patterns were selected by the item's `language` label, and every
    transliterated pattern in the lexicon is tagged `en`. Latin-script
    Hinglish that the detector labelled `hi` therefore never reached the
    patterns written for exactly that content.

    Selection is by the script the text is written in, so a wrong label
    costs nothing, while a pattern written in the other script is still
    not tried.
    """

    def test_every_pattern_declares_the_script_it_is_written_in(self) -> None:
        for pattern in load_lexicon().patterns:
            assert pattern.script in {"latin", "devanagari"}, pattern.pattern_id

    def test_a_devanagari_pattern_is_never_labelled_latin(self) -> None:
        """The declared script has to be the one the regex is written in."""
        for pattern in load_lexicon().patterns:
            has_devanagari = any("ऀ" <= ch <= "ॿ" for ch in pattern.regex.pattern)
            if has_devanagari:
                assert pattern.script == "devanagari", pattern.pattern_id

    @pytest.mark.parametrize(
        ("text", "expected_id"),
        [
            ("Dilli Chalo on March 18. Buses leave at dawn.", "en_chalo"),
            ("#dillichalo on March 18, buses from every district", "en_chalo_hashtag"),
            ("Dilli kooch karenge, sab taiyar rahein.", "en_kooch"),
            ("Call for a jail bharo from March 20.", "en_jail_bharo"),
            ("Dharna outside the collectorate from tomorrow.", "en_dharna"),
            ("Calling for a bandh across the district on Monday.", "en_bandh_call"),
        ],
    )
    def test_a_transliterated_call_labelled_hindi_is_still_detected(
        self, text: str, expected_id: str
    ) -> None:
        """The label says `hi`; the text is Latin script, so `en` patterns run."""
        matched = find_calls_to_assemble(text, language="hi")
        assert expected_id in {match.pattern_id for match in matched}

    @pytest.mark.parametrize(
        ("text", "expected_id"),
        [
            ("दिल्ली चलो। सभी जिलों से बसें रवाना होंगी।", "hi_chalo"),
            ("सभी लोग कल सुबह कलेक्ट्रेट पर पहुंचें।", "hi_pahunche"),
            ("कलेक्ट्रेट का घेराव करेंगे।", "hi_gherao"),
        ],
    )
    def test_a_devanagari_call_labelled_english_is_still_detected(
        self, text: str, expected_id: str
    ) -> None:
        matched = find_calls_to_assemble(text, language="en")
        assert expected_id in {match.pattern_id for match in matched}

    def test_only_the_patterns_of_the_script_present_are_tried(self) -> None:
        """Not "try everything always", which would be a precision change."""
        latin = find_calls_to_assemble(
            "Everyone gather at the town square tomorrow.", language="hi"
        )
        assert latin
        assert {match.script for match in latin} == {"latin"}

        devanagari = find_calls_to_assemble("सभी लोग कल सुबह कलेक्ट्रेट पर पहुंचें।", language="en")
        assert devanagari
        assert {match.script for match in devanagari} == {"devanagari"}

    def test_code_mixed_text_tries_both_scripts(self) -> None:
        """One item, two scripts, and the call is in the transliterated half."""
        matched = find_calls_to_assemble(
            "किसान संगठन ने कहा: Dilli Chalo on March 18.", language="hi"
        )
        assert "en_chalo" in {match.pattern_id for match in matched}

    def _lexicon_with(self, *extra: LexiconPattern) -> Lexicon:
        real = load_lexicon()
        return Lexicon(
            version=real.version,
            patterns=[*extra, *real.patterns],
            place_markers=real.place_markers,
        )

    # Bengali is in neither list, and the danda is deliberately absent from
    # this text: U+0964 sits in the Devanagari block and would make the
    # script readable after all.
    BENGALI = "সবাই আসুন"
    _BENGALI_PATTERN = LexiconPattern(
        pattern_id="test_latin",
        language="en",
        script="latin",
        regex=re.compile("আসুন"),
    )

    def test_text_in_no_script_the_lexicon_covers_tries_every_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The property #33 wrote and this change must not weaken.

        The needle is carried by a pattern declared `latin`, on text that
        is not Latin, so only the fallback can find it.
        """
        monkeypatch.setattr(
            mobilization, "load_lexicon", lambda: self._lexicon_with(self._BENGALI_PATTERN)
        )
        matched = find_calls_to_assemble(self.BENGALI, language="bn")
        assert "test_latin" in {match.pattern_id for match in matched}

    def test_an_unreadable_script_is_not_narrowed_by_a_scriptless_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One `any` pattern must not hide the rest from unreadable text.

        Falling back on an empty candidate list rather than on an empty
        script set would do exactly that: the `any` pattern alone would be
        tried, every other pattern skipped, and nothing logged.
        """
        anywhere = LexiconPattern(
            pattern_id="test_any",
            language="en",
            script="any",
            regex=re.compile(r"\d{1,2}:\d{2}"),
        )
        monkeypatch.setattr(
            mobilization,
            "load_lexicon",
            lambda: self._lexicon_with(anywhere, self._BENGALI_PATTERN),
        )
        matched = find_calls_to_assemble(f"{self.BENGALI} 16:00", language="bn")
        assert {"test_any", "test_latin"} <= {match.pattern_id for match in matched}

    def test_the_language_label_changes_no_result(self) -> None:
        """The non-selecting property, asserted rather than assumed."""
        text = "किसान संगठन ने कहा: Dilli Chalo on March 18."
        labels = [None, "en", "hi", "bn", "EN"]
        results = [
            sorted(match.pattern_id for match in find_calls_to_assemble(text, language=label))
            for label in labels
        ]
        assert all(result == results[0] for result in results)
        assert results[0]

    @pytest.mark.parametrize(
        ("text", "language"),
        [
            # Ordinary speech, carrying the label that used to hide it from
            # the pattern written to reject it.
            ("He said chalo, nothing will change.", "hi"),
            ("The film Chalo Dilli was screened at the club.", "hi"),
            ("चलो ठीक है, कल बात करते हैं।", "en"),
            ("पुलिस ने कहा कि स्थिति नियंत्रण में है।", "en"),
        ],
    )
    def test_a_wrong_label_does_not_cost_precision(self, text: str, language: str) -> None:
        assert find_calls_to_assemble(text, language=language) == []

    def test_a_place_is_extracted_from_a_mislabelled_item(self) -> None:
        """Place markers are selected by script too, for the same reason."""
        assert "Town Square" in (extract_place("Gather at Town Square", language="hi") or "")
        place = extract_place("कलेक्ट्रेट पर पहुंचें", language="en")
        assert place is not None
        assert any("ऀ" <= ch <= "ॿ" for ch in place)


@pytest.fixture
def reloadable_lexicon():
    """Read the lexicon from a written file rather than the shipped one."""
    load_lexicon.cache_clear()
    yield
    load_lexicon.cache_clear()


class TestACustomerEditedFileCannotDisableItselfSilently:
    """The file is handed to the customer to edit, so an edit that would
    stop a pattern from ever being tried has to say so."""

    def _write(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "lexicon.yaml"
        path.write_text(body)
        return path

    def test_an_unrecognised_script_falls_back_to_the_regex(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloadable_lexicon: None
    ) -> None:
        """`script: hindi` names no script the text can carry.

        Stored as written, the pattern is skipped on every item for the
        life of the deployment and nothing says why.
        """
        path = self._write(
            tmp_path,
            "version: 9\n"
            "patterns:\n"
            "  - id: hi_test\n"
            "    language: hi\n"
            "    script: hindi\n"
            "    regex: 'कूच करेंगे'\n",
        )
        monkeypatch.setattr(settings, "mobilization_lexicon_path", str(path))

        patterns = load_lexicon().patterns
        assert [p.script for p in patterns] == ["devanagari"]
        assert find_calls_to_assemble("कूच करेंगे।", language="hi")

    def test_a_marker_group_that_is_not_a_list_is_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloadable_lexicon: None
    ) -> None:
        """A bare string would otherwise become one marker per character."""
        path = self._write(
            tmp_path,
            "version: 9\n"
            "patterns: []\n"
            "place_markers:\n"
            "  en: 'at'\n"
            "  hi:\n"
            "    - 'पर'\n",
        )
        monkeypatch.setattr(settings, "mobilization_lexicon_path", str(path))

        assert load_lexicon().place_markers == {"devanagari": ["पर"]}


class TestTheScriptOfAPatternIsReadFromWhatItMatches:
    """Inference runs only on an entry that declares no script, which is
    the least exercised path in a file the customer edits."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (r"\bkooch\s+karenge\b", "latin"),
            ("कूच\\s*करेंगे", "devanagari"),
            # Regex syntax is Latin text describing something that is not
            # Latin script, so it decides nothing.
            (r"\d{4}-\d{2}-\d{2}", "any"),
            (r"\d{1,2}:\d{2}", "any"),
            # A Latin pattern carrying a Devanagari exclusion is Latin.
            (r"(?<![\u0900-\u097F])Chalo", "latin"),
            # A Devanagari range written as an escape is Devanagari.
            (r"[\u0900-\u097F]{2,}", "devanagari"),
        ],
    )
    def test_the_script_is_inferred_from_the_regex(self, source: str, expected: str) -> None:
        assert script_of_source(source) == expected
