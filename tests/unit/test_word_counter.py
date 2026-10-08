"""The shared word counter must cover every language the platform claims.

The gate at services/analyst/anveshak/analyst/content_quality.py measures
content volume in words. A script missing from sdk/anveshak/text.py therefore
counts zero words and every item in that language is dropped with no error.
This repository has shipped that bug once already, with Devanagari missing from
the analyst's pattern, and the scraper's copy of the gate reintroduced it for
eight more scripts before this file existed: a missing script there is worse,
because the scraper's verdict is persisted as content_quality and the
clustering SQL honours it forever.

So the contract is pinned here rather than left to a comment: one real sentence
per language in AnalystSettings.stance_supported_languages, each of which must
count at least content_min_words words.
"""

from __future__ import annotations

import pytest
from anveshak.text import count_words, extract_words

pytestmark = pytest.mark.unit


# One realistic news sentence per language, saying roughly the same thing: the
# police refused permission for a march and the organisation said it would
# march anyway. Length is deliberately near the short end of what a real item
# carries, so the floor is tested where it bites rather than where it is safe.
SENTENCE_PER_LANGUAGE: dict[str, str] = {
    "en": "Ranchi police refused permission for the march. The organisation said it would march anyway.",
    "hi": "रांची पुलिस ने मार्च की अनुमति देने से इनकार कर दिया। संगठन ने कहा कि वह मार्च करेगा।",
    "bn": "পুলিশ মিছিলের অনুমতি দিতে অস্বীকার করেছে। সংগঠনটি বলেছে তারা যেভাবেই হোক মিছিল করবে।",
    "ta": "அணிவகுப்புக்கு அனுமதி அளிக்க காவல்துறை மறுத்தது. எப்படியும் அணிவகுப்பு நடக்கும் என்று அந்த அமைப்பு கூறியது.",
    "te": "ర్యాలీకి అనుమతి ఇవ్వడానికి పోలీసులు నిరాకరించారు. ఏమైనప్పటికీ ర్యాలీ నిర్వహిస్తామని ఆ సంస్థ ప్రకటించింది.",
    "mr": "पोलिसांनी मोर्चाला परवानगी देण्यास नकार दिला. संघटनेने सांगितले की ते कोणत्याही परिस्थितीत मोर्चा काढतील.",
    "gu": "પોલીસે રેલીની પરવાનગી આપવાનો ઇનકાર કર્યો. સંસ્થાએ કહ્યું કે તે કોઈપણ રીતે રેલી કાઢશે.",
    "kn": "ಮೆರವಣಿಗೆಗೆ ಅನುಮತಿ ನೀಡಲು ಪೊಲೀಸರು ನಿರಾಕರಿಸಿದರು. ಹೇಗಾದರೂ ಮೆರವಣಿಗೆ ನಡೆಸುವುದಾಗಿ ಸಂಸ್ಥೆ ಹೇಳಿದೆ.",
    "ml": "റാലിക്ക് അനുമതി നൽകാൻ പോലീസ് വിസമ്മതിച്ചു. എന്തായാലും റാലി നടത്തുമെന്ന് സംഘടന അറിയിച്ചു.",
    "pa": "ਪੁਲਿਸ ਨੇ ਮਾਰਚ ਦੀ ਮਨਜ਼ੂਰੀ ਦੇਣ ਤੋਂ ਇਨਕਾਰ ਕਰ ਦਿੱਤਾ। ਸੰਸਥਾ ਨੇ ਕਿਹਾ ਕਿ ਉਹ ਫਿਰ ਵੀ ਮਾਰਚ ਕਰੇਗੀ।",
    "ur": "پولیس نے مارچ کی اجازت دینے سے انکار کر دیا۔ تنظیم نے کہا کہ وہ پھر بھی مارچ کرے گی۔",
    "ne": "प्रहरीले जुलुसको अनुमति दिन अस्वीकार गर्यो। संस्थाले भन्यो कि उनीहरू जे भए पनि जुलुस निकाल्नेछन्।",
    "si": "පෙළපාලියට අවසර දීම පොලීසිය ප්‍රතික්ෂේප කළේය. කෙසේ වෙතත් පෙළපාලිය පවත්වන බව එම සංවිධානය කියා සිටියේය.",
    "ar": "رفضت الشرطة منح الترخيص للمسيرة. وقالت المنظمة إنها ستمضي في المسيرة على أي حال.",
    "fr": "La police a refusé l'autorisation de la marche. L'organisation a déclaré qu'elle défilerait quand même.",
    "de": "Die Polizei hat die Genehmigung für den Marsch verweigert. Die Organisation erklärte, sie werde trotzdem marschieren.",
    "es": "La policía denegó el permiso para la marcha. La organización declaró que marcharía de todos modos.",
    "ru": "Полиция отказалась выдать разрешение на марш. Организация заявила, что всё равно проведёт его.",
    "zh": "警方拒绝批准游行申请。该组织表示无论如何都会举行游行。",
    "tr": "Polis yürüyüş iznini vermeyi reddetti. Örgüt yine de yürüyüş yapacağını açıkladı.",
}


def _supported_languages() -> list[str]:
    from anveshak.analyst.settings import settings

    return list(settings.stance_supported_languages)


class TestEverySupportedLanguageIsCounted:
    def test_no_supported_language_lacks_a_sample(self):
        """A language added to settings without a sample here is a gap, not a pass."""
        missing = sorted(set(_supported_languages()) - set(SENTENCE_PER_LANGUAGE))
        assert not missing, (
            f"stance_supported_languages lists {missing} with no sentence in this test. "
            "Add one, and add the script to sdk/anveshak/text.py if it counts zero words."
        )

    @pytest.mark.parametrize("code", sorted(SENTENCE_PER_LANGUAGE))
    def test_sentence_counts_above_the_gate_floor(self, code: str):
        from anveshak.analyst.settings import settings

        counted = count_words(SENTENCE_PER_LANGUAGE[code])
        assert counted >= settings.content_min_words, (
            f"{code} counts {counted} words against a floor of {settings.content_min_words}. "
            "Either its script is missing from sdk/anveshak/text.py, in which case every "
            f"{code} item is silently dropped, or the floor is too high for this script."
        )

    @pytest.mark.parametrize("code", sorted(SENTENCE_PER_LANGUAGE))
    def test_no_language_counts_zero(self, code: str):
        """Zero is the signature of a missing script, and it is always a bug."""
        assert count_words(SENTENCE_PER_LANGUAGE[code]) > 0


class TestCombiningMarksStayInsideTheirWord:
    """Why the ranges are whole blocks and not a generic Unicode letter class.

    A vowel sign is a combining mark, not a letter, so `[^\\W\\d_]` splits every
    Indic word at its matras. Measured, that takes the Hindi sentence above from
    19 words to 9 and scores the standalone word 'की' as zero. These cases fail
    if anyone swaps the ranges for a letter-only class.
    """

    @pytest.mark.parametrize(
        "word",
        [
            "की",  # Devanagari, mark-initial second character
            "मार्च",  # Devanagari with virama
            "ਦਿੱਤਾ",  # Gurmukhi with addak
            "நடத்தும்",  # Tamil with virama
            "ప్రకటించింది",  # Telugu with conjunct
        ],
    )
    def test_single_word_counts_as_one(self, word: str):
        assert count_words(word) == 1
        assert extract_words(word) == [word.lower()]


class TestCounterContract:
    def test_count_agrees_with_extract(self):
        """count_words streams and extract_words materialises; they must agree."""
        mixed = "Police refused मार्च की अनुमति 中国 பேரணி permission today"
        assert count_words(mixed) == len(extract_words(mixed))

    @pytest.mark.parametrize("text", ["", "   ", "\n\t ", "12345 67890", ">>> --- ||| === ***"])
    def test_wordless_input_counts_zero(self, text: str):
        assert count_words(text) == 0

    def test_a_single_long_run_of_letters_is_one_word(self):
        """Not 200 words. The gate relies on this to reject wordless padding."""
        assert count_words("A" * 200) == 1

    def test_extract_lowercases_for_dedup(self):
        """The unique-word ratio depends on case folding, so extract must fold."""
        assert extract_words("Police POLICE police") == ["police", "police", "police"]

    def test_count_does_not_pay_for_the_token_list(self):
        """A 2 MB page must not build a multi-megabyte list just to be counted.

        Pinned because count_words previously called extract_words and threw the
        list away, which on a 16 MB page measured several hundred megabytes of
        transient strings inside a container with a hard memory limit.
        """
        import tracemalloc

        page = "lorem ipsum dolor sit amet " * 80_000  # ~2 MB, ~400k words
        tracemalloc.start()
        count_words(page)
        _, counted_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        extract_words(page)
        _, extracted_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert counted_peak * 10 < extracted_peak, (
            f"count_words peaked at {counted_peak} bytes against extract_words' "
            f"{extracted_peak}; it is materialising the token list again"
        )


class TestScraperAndAnalystFloorsAgree:
    """One env var, two settings classes, two different consequences.

    The analyst's floor skips embedding and a re-run undoes it. The scraper's
    writes content_quality='low_quality', which the clustering SQL honours
    permanently. They are bound to the same CONTENT_MIN_WORDS, so the defaults
    must match or an operator setting the env var moves one and not the other.
    """

    def test_defaults_are_equal(self):
        from anveshak.analyst.settings import AnalystSettings
        from anveshak.scraper.settings import ScraperSettings

        assert AnalystSettings().content_min_words == ScraperSettings().content_min_words

    def test_floor_is_at_least_one(self):
        """At 0 the ratio gates divide by zero, so the floor must stay positive."""
        from anveshak.analyst.settings import settings

        assert settings.content_min_words >= 1
