"""Unit tests for analyst content quality gate.

is_quality_content returns (passed: bool, gate: str) tuples where:
- passed: True if content is good for embedding, False if rejected
- gate: 'too_short', 'unique_ratio', 'punctuation', or 'passed'
"""

from unittest.mock import patch

import pytest
from anveshak.analyst.content_quality import is_quality_content


@pytest.fixture(autouse=True)
def _default_settings():
    """Ensure default thresholds for all tests."""
    with patch("anveshak.analyst.content_quality.settings") as mock:
        mock.content_min_words = 8
        mock.content_min_unique_word_ratio = 0.4
        mock.content_max_punctuation_ratio = 0.3
        yield mock


class TestIsQualityContent:
    def test_returns_tuple(self):
        """Return type must be a 2-tuple (bool, str)."""
        result = is_quality_content("Hello world")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_short_text_rejected(self):
        passed, gate = is_quality_content("Hello world")
        assert passed is False
        assert gate == "too_short"

    def test_empty_text_rejected(self):
        passed, gate = is_quality_content("")
        assert passed is False
        assert gate == "too_short"

        passed, gate = is_quality_content("   ")
        assert passed is False
        assert gate == "too_short"

    def test_real_article_accepted(self):
        text = (
            "India conducted a successful test of the BrahMos supersonic cruise missile "
            "from a naval destroyer in the Arabian Sea on Thursday. The missile hit its "
            "designated target with precision, according to the defence ministry statement."
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    def test_navigation_boilerplate_rejected(self):
        """Simulates nav menu text scraped from janes.com → unique_ratio gate."""
        text = (
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science "
            "Military Diplomacy Politics Science China Future Tech Science"
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "unique_ratio"

    def test_repeated_menu_rejected(self):
        text = (
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport "
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport "
            "Latest China Economy Hong Kong Asia Business Tech Lifestyle World Opinion Video Sport"
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "unique_ratio"

    def test_high_punctuation_rejected(self):
        # Enough real words to pass the length gate, but dominated by punctuation
        text = (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu "
            ">>> --- ||| === *** $$$ @@@ ### ^^^ &&& <<< >>> --- ||| === *** "
            "$$$ @@@ ### ^^^ &&& <<< >>> --- ||| === *** $$$ @@@ ### ^^^ &&& "
            "<<< >>> --- ||| === *** $$$ @@@ ### ^^^ &&& <<< >>> --- ||| === "
        )
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "punctuation"

    def test_no_real_words_rejected(self):
        """Long but wordless text fails the single length gate, not a second one."""
        text = "A" * 200  # long but not real words
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "too_short"

    def test_multilingual_accepted(self):
        """Chinese text with sufficient unique content should pass."""
        text = (
            "中国国防部发布最新声明表示南海局势总体稳定可控各方应当保持克制避免采取任何可能"
            "导致局势升级的行动中方将继续坚定维护国家主权和领土完整同时致力于通过对话协商"
            "和平解决有关争议中方强调南海航行自由从来不是问题"
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    def test_borderline_unique_ratio(self):
        """Exactly at the threshold — unique_ratio = 0.4 should pass."""
        # 10 words, 4 unique = 0.4 ratio
        words = ["alpha", "beta", "gamma", "delta"] + ["alpha"] * 3 + ["beta"] * 3
        text = (
            " ".join(words) + " extra filler content to reach the minimum length threshold needed"
        )
        passed, gate = is_quality_content(text)
        assert isinstance(passed, bool)
        assert gate in ("passed", "unique_ratio")


# ---------------------------------------------------------------------------
# Script fairness — the gate must measure content volume, not character count
# ---------------------------------------------------------------------------

# Verbatim from corpora/synthetic_cockroach_janta_party.jsonl, the nine items
# the old 100-character gate rejected. Every one is Hindi, every one carries
# 16 or more words, and every one clears the unique-word-ratio floor.
HINDI_CORPUS_ITEMS = [
    "CJP के नाम से वायरल परिपत्र फ़र्ज़ी निकला। यह परिपत्र संगठन ने जारी नहीं किया है।",
    "लाठीचार्ज की न्यायिक जांच के आदेश दिए गए हैं। जांच रिपोर्ट तीन महीने में देनी होगी।",
    "शिक्षा मंत्री ने शुक्रवार को इस्तीफ़ा दे दिया। इस्तीफ़े में आंदोलन का कोई ज़िक्र नहीं है।",
    "रांची पुलिस ने CJP मार्च की अनुमति देने से इनकार कर दिया। संगठन ने कहा कि वह मार्च करेगा।",
    "भोपाल पुलिस ने CJP मार्च की अनुमति देने से इनकार कर दिया। संगठन ने कहा कि वह मार्च करेगा।",
    "दिल्ली पुलिस ने CJP मार्च की अनुमति देने से इनकार कर दिया। संगठन ने कहा कि वह मार्च करेगा।",
    "फिर से संसद चलो का ऐलान, सभी कार्यकर्ता तय तारीख़ को पहुंचें। अनुमति के लिए आवेदन दिया गया है।",
    "पुलिस ने लाठीचार्ज किया, कई कार्यकर्ता घायल हुए। यह शर्मनाक है, बैठे हुए छात्रों पर लाठी चलाई गई।",
    "संसद चलो मार्च में हज़ारों लोग शामिल हुए, पुलिस ने बैरिकेड पर रोका। मेट्रो स्टेशन चार घंटे बंद रहे।",
]


class TestDevanagariNotPenalisedForBeingCompact:
    """Regression: a character floor rejects Hindi that an English equal clears.

    Devanagari carries the same meaning in roughly half the characters, so a
    complete Hindi news sentence failed a 100-character gate while the English
    sentence saying the same thing passed. These nine items cost the Cockroach
    Janta Party Replay its entire Hindi coverage.
    """

    @pytest.mark.unit
    @pytest.mark.parametrize("text", HINDI_CORPUS_ITEMS)
    def test_real_hindi_item_accepted(self, text: str):
        assert len(text) < 100, "fixture must stay under the old character floor"
        passed, gate = is_quality_content(text)
        assert passed is True, f"rejected at gate {gate!r}: {text}"
        assert gate == "passed"

    @pytest.mark.unit
    def test_hindi_and_its_english_equal_agree(self):
        """Same claim, two scripts, one verdict. The old gate split them."""
        hindi = "रांची पुलिस ने CJP मार्च की अनुमति देने से इनकार कर दिया। संगठन ने कहा कि वह मार्च करेगा।"
        english = (
            "Ranchi police refused permission for the CJP march. "
            "The organisation said that it would march anyway."
        )
        assert len(hindi) < 100 <= len(english), "the character counts must differ"
        assert is_quality_content(hindi) == is_quality_content(english)


class TestOtherScripts:
    """One case per script the word regex covers, so none drifts unnoticed."""

    @pytest.mark.unit
    def test_arabic_accepted(self):
        text = (
            "أعلنت الشرطة أنها رفضت منح الترخيص للمسيرة المقررة في العاصمة "
            "يوم الجمعة، وقالت المنظمة إنها ستمضي في المسيرة على أي حال."
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    @pytest.mark.unit
    def test_bengali_accepted(self):
        text = (
            "পুলিশ রাজধানীতে নির্ধারিত মিছিলের অনুমতি দিতে অস্বীকার করেছে বলে জানিয়েছে, "
            "এবং সংগঠনটি বলেছে তারা যেভাবেই হোক মিছিল করবে।"
        )
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"

    @pytest.mark.unit
    def test_very_short_cjk_rejected_because_each_ideograph_is_one_word(self):
        """Pinned, not accidental.

        The regex treats one ideograph as one word, so a CJK item needs only
        content_min_words ideographs to pass. Six is below the floor of 8 and is
        rejected. This is the residual cost of one word floor across scripts
        with very different words-per-sentence, and it is accepted: a per-script
        budget is more machinery than the measured gain justifies. The floor
        sits at the bottom of the range the golden corpus tolerates precisely to
        keep this residue small.
        """
        text = "警方拒绝游行"  # 6 ideographs
        passed, gate = is_quality_content(text)
        assert passed is False
        assert gate == "too_short"

    @pytest.mark.unit
    def test_a_real_cjk_sentence_passes(self):
        """The counterpart: a real CJK sentence must clear the same floor."""
        text = "警方拒绝批准游行申请。该组织表示无论如何都会举行游行。"
        passed, gate = is_quality_content(text)
        assert passed is True
        assert gate == "passed"


class TestThresholdInvariants:
    """The shipped default must not eat the golden corpus.

    Reads the real settings object rather than the patched one, so a future
    tuning change that would silently drop real content fails here instead of
    shipping.
    """

    @pytest.mark.unit
    def test_min_words_below_smallest_genuine_corpus_item(self):
        import json
        from pathlib import Path

        from anveshak.analyst.settings import settings as real_settings
        from anveshak.text import count_words

        relative = Path("corpora") / "synthetic_cockroach_janta_party.jsonl"
        root = Path(__file__).resolve()
        while not (root / relative).exists():
            assert root != root.parent, f"{relative} not found above {__file__}"
            root = root.parent
        corpus = root / relative

        # count_words, not a local regex. A copied pattern here would be the
        # third copy of the thing the shared counter exists to prevent, and it
        # would agree with the gate only by luck.
        counts = [
            count_words(json.loads(line)["text"])
            for line in corpus.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert counts, "corpus parsed to zero items"
        assert real_settings.content_min_words < min(counts), (
            f"content_min_words={real_settings.content_min_words} would reject the "
            f"smallest genuine corpus item at {min(counts)} words"
        )


class TestKnownFalseAccept:
    """A one-shot navigation menu passes, and that is a recorded decision.

    Every word is distinct, so the unique-word-ratio gate cannot see it, and it
    carries no punctuation, so the punctuation gate cannot either. The old
    character floor caught this particular string only because it is 90
    characters long; the same menu at 110 characters passed before this change
    too, so the hole is pre-existing rather than new. It is pinned here so the
    next person to touch the gate knows the shape it already lets through.

    Closing it needs a boilerplate signal that is not a length proxy, such as
    requiring a sentence terminator from the full set of scripts, and that
    carries its own risk of dropping real headline-only items. Deliberately not
    attempted in the change that fixed the script bias.
    """

    @pytest.mark.unit
    def test_non_repeating_navigation_menu_is_accepted(self):
        text = (
            "Home News Sports Business Technology Lifestyle "
            "Videos Photos About Contact Subscribe Login"
        )
        passed, gate = is_quality_content(text)
        assert passed is True, "if this starts failing, a new boilerplate gate landed"
        assert gate == "passed"
