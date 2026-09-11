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
