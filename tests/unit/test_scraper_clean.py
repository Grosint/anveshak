"""Unit tests for post-extraction text cleaner.

pytest.mark.unit — no external dependencies, no DB, no network.
"""
import pytest
from anveshak.scraper.clean import clean_extracted_text, is_paywall_page, score_content_quality


class TestMarkdownLinkRemoval:
    """Markdown [text](url) syntax should be converted to plain text."""

    def test_simple_link(self):
        assert clean_extracted_text("[Click here](https://example.com)") == "Click here"

    def test_link_in_context(self):
        result = clean_extracted_text(
            "Read the [full report](https://example.com/report) for details."
        )
        assert result == "Read the full report for details."

    def test_multiple_links(self):
        text = "[China](https://scmp.com/china) [Military](https://scmp.com/military)"
        result = clean_extracted_text(text)
        assert "China" in result
        assert "Military" in result
        assert "https://" not in result

    def test_empty_link_text(self):
        result = clean_extracted_text("[](https://example.com)")
        assert "https://" not in result


class TestMarkdownImageRemoval:
    """Markdown ![alt](url) should be stripped entirely."""

    def test_simple_image(self):
        result = clean_extracted_text('![GlobalSecurity.org](https://example.com/img.png)')
        assert "https://" not in result

    def test_image_with_title(self):
        result = clean_extracted_text(
            '![GlobalSecurity.org](https://www.globalsecurity.org/index.html "GlobalSecurity.org")'
        )
        assert "https://" not in result
        assert "index.html" not in result

    def test_image_in_context(self):
        text = 'See ![photo](https://example.com/photo.jpg) for reference. Real content here.'
        result = clean_extracted_text(text)
        assert "Real content here." in result
        assert "https://" not in result


class TestBoilerplateRemoval:
    """Common boilerplate phrases on their own lines should be removed."""

    def test_advertisement_lines(self):
        text = "Real content here.\nAdvertisement\nMore real content."
        result = clean_extracted_text(text)
        assert "Advertisement" not in result
        assert "Real content here." in result
        assert "More real content." in result

    def test_sign_in(self):
        text = "Article text.\nSIGN IN\nMore article text."
        result = clean_extracted_text(text)
        assert "SIGN IN" not in result

    def test_cookie_policy(self):
        text = "Content.\nCookie Policy\nMore content."
        result = clean_extracted_text(text)
        assert "Cookie Policy" not in result

    def test_boilerplate_mid_sentence_preserved(self):
        """Boilerplate phrase within a real sentence should NOT be removed."""
        text = "The advertisement campaign reached millions."
        result = clean_extracted_text(text)
        assert "advertisement campaign" in result

    def test_log_in_register(self):
        text = "Article.\nLog in Register\nContent."
        result = clean_extracted_text(text)
        assert "Log in Register" not in result


class TestAsteriskNavRemoval:
    """Asterisk-separated navigation should be removed."""

    def test_asterisk_nav(self):
        text = "* My Account * Sign In * Subscribe * Sign Out * More"
        result = clean_extracted_text(text)
        assert "My Account" not in result

    def test_globalsecurity_nav(self):
        nav = "* Military Menu * Introduction * Systems * Facilities * Agencies * Industry"
        text = f"Real article content.\n{nav}\nMore content."
        result = clean_extracted_text(text)
        assert "Military Menu" not in result
        assert "Real article content." in result


class TestBreadcrumbRemoval:
    """Breadcrumb separators like 'Home :: Military :: Systems' should be removed."""

    def test_double_colon_breadcrumb(self):
        text = "Home :: Military :: * Military Menu"
        result = clean_extracted_text(text)
        assert "Home :: Military" not in result


class TestCamelCaseNavRemoval:
    """CamelCase-concatenated navigation like 'ChinaEconomyAsiaWorldSport'."""

    def test_long_camel_nav(self):
        text = "Real content. ChinaEconomyAsiaWorldSportLifestyle More real content."
        result = clean_extracted_text(text)
        assert "ChinaEconomyAsiaWorldSportLifestyle" not in result
        assert "Real content." in result
        assert "More real content." in result

    def test_short_camel_preserved(self):
        """Short CamelCase like 'SouthChina' should be preserved."""
        text = "The SouthChina Morning Post reported."
        result = clean_extracted_text(text)
        assert "SouthChina" in result


class TestInlineJunkRemoval:
    """Inline junk phrases should be stripped from within lines."""

    def test_inline_log_in_register(self):
        text = "Thursday, April 23, 2026 Log in Register What's new By: Content here."
        result = clean_extracted_text(text)
        assert "Log in Register" not in result.title()

    def test_app_install_instructions(self):
        text = "How to install the app on iOS Follow along with the video below to see how to install our site as a web app on your home screen. Real content."
        result = clean_extracted_text(text)
        assert "install the app" not in result
        assert "Real content." in result

    def test_pages_left(self):
        text = "2 pages left * My Account * Sign In"
        result = clean_extracted_text(text)
        assert "pages left" not in result

    def test_edition_international(self):
        text = "Edition: International HIGHLIGHTS some content here."
        result = clean_extracted_text(text)
        assert "Edition: International" not in result


class TestNavigationLineRemoval:
    """Lines that look like navigation menus should be removed."""

    def test_scmp_style_nav(self):
        nav = "Latest China Economy Hong Kong Asia Business Tech Lifestyle People Culture"
        text = f"Real headline here.\n{nav}\nReal article content."
        result = clean_extracted_text(text)
        assert nav not in result
        assert "Real headline here." in result
        assert "Real article content." in result

    def test_short_lines_preserved(self):
        text = "This is a normal sentence.\nAnother normal sentence."
        result = clean_extracted_text(text)
        assert "This is a normal sentence." in result


class TestBareUrlRemoval:
    """Lines that are just URLs should be removed."""

    def test_bare_url_line(self):
        text = "Article text.\nhttps://example.com/page\nMore text."
        result = clean_extracted_text(text)
        assert "https://example.com" not in result

    def test_url_in_sentence_preserved(self):
        text = "Visit https://example.com for more."
        result = clean_extracted_text(text)
        assert "https://example.com" in result


class TestRepeatedBlockRemoval:
    """Blocks appearing 2+ times (headers/footers) should be removed."""

    def test_repeated_header(self):
        header = "SCMP PLUS Latest China Economy Hong Kong Asia"
        text = f"{header}\nArticle one text.\n{header}\nArticle two text."
        result = clean_extracted_text(text)
        assert "Article one text." in result
        assert "Article two text." in result


class TestWhitespaceCollapse:
    def test_multiple_blank_lines(self):
        text = "Paragraph one.\n\n\n\n\nParagraph two."
        result = clean_extracted_text(text)
        assert "\n\n\n" not in result
        assert "Paragraph one." in result
        assert "Paragraph two." in result


class TestMarkdownBold:
    def test_bold_to_plain(self):
        text = "**Note:** This is important content."
        result = clean_extracted_text(text)
        assert "**" not in result
        assert "Note:" in result


class TestEdgeCases:
    def test_empty_string(self):
        assert clean_extracted_text("") == ""

    def test_none_like_empty(self):
        assert clean_extracted_text("") == ""

    def test_real_article_preserved(self):
        article = (
            "China conducted military exercises near Taiwan on Wednesday, "
            "involving naval and air assets in a display that analysts said "
            "was intended to signal displeasure with recent diplomatic moves."
        )
        result = clean_extracted_text(article)
        assert result == article

    def test_scmp_garbage_input(self):
        """Realistic SCMP-style garbage from Crawl4AI."""
        garbage = (
            "Edition: International [](https://www.scmp.com/mynews) "
            "HIGHLIGHTS [Donald Trump's China policyNEW]"
            "(https://www.scmp.com/topics/donald-trumps-china-policy?"
            "module=hamburger_menu&pgtype=section)[US-China relations]...\n"
            "Advertisement Advertisement SCMP PLUS Latest China Economy "
            "Hong Kong Asia Business Tech Lifestyle People Culture World "
            "Opinion Video Sport\n"
            "Advertisement\n"
            "SIGN IN\n"
            "# China\n"
            "+ FOLLOW\n"
            "The actual article content about military exercises near Taiwan."
        )
        result = clean_extracted_text(garbage)
        assert "The actual article content about military exercises near Taiwan." in result
        assert "Advertisement" not in result
        assert "SIGN IN" not in result
        assert "https://www.scmp.com" not in result

    def test_globalsecurity_garbage(self):
        """Realistic GlobalSecurity.org garbage from screenshot."""
        garbage = (
            "* * 2 pages left * My Account * Sign In * Subscribe * Sign Out "
            "![GlobalSecurity.org](https://www.globalsecurity.org/index.html "
            '"GlobalSecurity.org") Home :: Military :: * Military Menu '
            "* Introduction * Systems * Facilities * Agencies * Industry "
            "* Operations * Countries * Hot Topics"
        )
        result = clean_extracted_text(garbage)
        assert "My Account" not in result
        assert "Sign In" not in result
        assert "globalsecurity.org" not in result.lower()
        assert "Military Menu" not in result

    def test_defence_pk_garbage(self):
        """Realistic defence.pk forum garbage from screenshot."""
        garbage = (
            "Thursday, April 23, 2026 Log in Register What's new By: "
            "How to install the app on iOS Follow along with the video "
            "below to see how to install our site as a web app on your "
            "home screen. **Note:** This feature may not be available "
            "in some browsers. * Home * Forums New threads New posts "
            "Real forum post content about military developments."
        )
        result = clean_extracted_text(garbage)
        assert "Real forum post content about military developments." in result
        assert "Log in Register" not in result
        assert "install the app" not in result
        assert "New threads" not in result


class TestPaywallDetection:
    """is_paywall_page should detect login/subscription wall pages."""

    THEHINDU_PAYWALL = (
        "You are logged in\n"
        "Loading...\n"
        "LOGOUT\n"
        "You don't have any Active Subscription.\n"
        "\n"
        "Subscribed with another email? Logout and Login with that one.\n"
        "Your active subscription(s) Account subscription benefits alongside Premium..."
    )

    def test_thehindu_paywall_detected(self):
        assert is_paywall_page(self.THEHINDU_PAYWALL) is True

    def test_real_article_not_flagged(self):
        article = (
            "China conducted military exercises near Taiwan on Wednesday, "
            "involving naval and air assets in a display that analysts said "
            "was intended to signal displeasure with recent diplomatic moves. "
            "The PLA Eastern Theatre Command confirmed the drills."
        )
        assert is_paywall_page(article) is False

    def test_empty_text(self):
        assert is_paywall_page("") is False

    def test_generic_paywall(self):
        text = (
            "Subscribe to read the full article.\n"
            "Premium content is available to subscribers only.\n"
            "Sign in to read this premium member exclusive."
        )
        assert is_paywall_page(text) is True

    def test_article_mentioning_subscription_not_flagged(self):
        """An article about subscriptions should not be flagged."""
        text = (
            "Netflix announced new subscription tiers today, with premium content "
            "being made available to a wider audience. The company said subscribers "
            "would benefit from lower prices across all regions."
        )
        assert is_paywall_page(text) is False

    def test_score_content_quality_paywall(self):
        """Paywall pages should be marked low_quality by score_content_quality."""
        quality, gate = score_content_quality(self.THEHINDU_PAYWALL, self.THEHINDU_PAYWALL)
        assert quality == "low_quality"
        assert gate == "paywall"

    def test_score_content_quality_real_article(self):
        article = (
            "The Indian Air Force conducted a major exercise in the western sector "
            "involving Rafale and Sukhoi-30MKI fighter jets. The exercise tested "
            "integrated air defence operations across multiple airbases."
        )
        quality, _gate = score_content_quality(article, article)
        assert quality == "good"


# ---------------------------------------------------------------------------
# Additional clean.py tests — quality scoring, title extraction, clean hash
# ---------------------------------------------------------------------------

from anveshak.scraper.clean import compute_clean_hash, extract_title


class TestScoreContentQualityExtended:
    """Extended tests for score_content_quality business logic.

    score_content_quality returns (quality, gate) tuples where:
    - quality: 'good' or 'low_quality'
    - gate: 'too_short', 'paywall', 'nav_icon', 'ratio', 'bypass', 'passed'
    """

    @pytest.mark.unit
    def test_returns_tuple(self):
        """Return type must be a 2-tuple of strings."""
        article = (
            "The Indian Navy commissioned its second indigenous aircraft carrier today "
            "at a ceremony in Kochi. The 45,000-tonne vessel represents a significant "
            "milestone in India's naval shipbuilding capabilities."
        )
        result = score_content_quality(article, article)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.unit
    def test_high_quality_article(self):
        """Normal article text → ('good', 'passed')."""
        article = (
            "The Indian Navy commissioned its second indigenous aircraft carrier today "
            "at a ceremony in Kochi. The 45,000-tonne vessel represents a significant "
            "milestone in India's naval shipbuilding capabilities. Defence Minister "
            "praised the achievement as a step toward self-reliance in defence. "
            "The carrier can operate 30 aircraft including MiG-29K fighters."
        )
        quality, gate = score_content_quality(article, article)
        assert quality == "good"
        assert gate == "passed"

    @pytest.mark.unit
    def test_boilerplate_only_is_low_quality(self):
        """Navigation-only text → 'low_quality' after cleaning strips most content."""
        raw = (
            "Home About Contact Us Privacy Policy Terms of Service "
            "Subscribe Now Log In Register My Account Sign In Sign Out "
            "Cookie Settings Accept Cookies Newsletter Download the App"
        )
        cleaned = clean_extracted_text(raw)
        quality, gate = score_content_quality(raw, cleaned)
        assert quality == "low_quality"

    @pytest.mark.unit
    def test_short_clean_text_is_low_quality(self):
        """Clean text under 100 chars → ('low_quality', 'too_short')."""
        quality, gate = score_content_quality("short", "short")
        assert quality == "low_quality"
        assert gate == "too_short"

    @pytest.mark.unit
    def test_gate_too_short_empty(self):
        """Empty clean text triggers too_short gate."""
        quality, gate = score_content_quality("raw content", "")
        assert (quality, gate) == ("low_quality", "too_short")

    @pytest.mark.unit
    def test_gate_too_short_none(self):
        """None clean text triggers too_short gate."""
        quality, gate = score_content_quality("raw", None)
        assert (quality, gate) == ("low_quality", "too_short")

    @pytest.mark.unit
    def test_gate_paywall(self):
        """Paywall content triggers paywall gate."""
        paywall = (
            "You don't have any active subscription. "
            "Subscribed with another email? Logout and login with that one. "
            "Your active subscription benefits include full access to all "
            "articles and premium content. Please sign in to continue reading."
        )
        quality, gate = score_content_quality(paywall, paywall)
        assert quality == "low_quality"
        assert gate == "paywall"

    @pytest.mark.unit
    def test_gate_nav_icon(self):
        """Nav icon garbage triggers nav_icon gate."""
        nav = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow menu close hamburger share facebook twitter whatsapp "
        ) * 3  # enough chars to pass length check, 40%+ nav icon words
        quality, gate = score_content_quality(nav, nav)
        assert quality == "low_quality"
        assert gate == "nav_icon"

    @pytest.mark.unit
    def test_gate_no_raw_text(self):
        """Empty raw_text with valid clean_text → ('good', 'passed')."""
        clean = "A substantial article about defence acquisitions and naval exercises. " * 3
        quality, gate = score_content_quality("", clean)
        assert quality == "good"
        assert gate == "passed"


class TestScoreContentQualityThresholds:
    """Boundary tests for ratio gate and length bypass."""

    @pytest.mark.unit
    def test_ratio_bypass_long_clean_text(self):
        """clean_text >= 500 chars bypasses ratio check → ('good', 'bypass')."""
        raw = "x" * 10_000
        clean = (
            "India conducted a major joint military exercise involving all three "
            "services in the Rajasthan desert. The exercise tested integrated "
            "operations doctrine adopted after the 2020 Galwan standoff. "
            "All branches operated under a unified theatre command structure "
            "for the first time. The Navy contributed maritime patrol assets "
            "coordinating with ground forces via encrypted satellite links. "
            "Exercise duration was 14 days with over 30,000 troops participating. "
            "The exercise validated new communication protocols and joint logistics "
            "chains across service boundaries under simulated combat conditions."
        )
        assert len(clean) >= 500
        assert len(clean) / len(raw) < 0.08
        quality, gate = score_content_quality(raw, clean)
        assert quality == "good"
        assert gate == "bypass"

    @pytest.mark.unit
    def test_low_ratio_short_text_still_rejected(self):
        """clean_text < 500 chars with ratio < 0.08 → ('low_quality', 'ratio')."""
        raw = "a" * 5_000
        clean = "India deploys new radar systems along the northern border region. " * 3
        assert len(clean) < 500
        assert len(clean) / len(raw) < 0.08
        quality, gate = score_content_quality(raw, clean)
        assert quality == "low_quality"
        assert gate == "ratio"

    @pytest.mark.unit
    def test_ratio_band_0_08_to_0_15_now_accepted(self):
        """Items with ratio in [0.08, 0.15) are now good with 'passed' gate."""
        raw = "n" * 2_000
        clean = (
            "The defence ministry approved acquisition of six additional P-8I "
            "maritime patrol aircraft to bolster anti-submarine warfare capabilities "
            "in the Indian Ocean Region. The contract is worth approximately twelve "
            "thousand crore rupees and includes weapons systems integration."
        )
        assert len(clean) < 500
        ratio = len(clean) / len(raw)
        assert 0.08 <= ratio < 0.15
        quality, gate = score_content_quality(raw, clean)
        assert quality == "good"
        assert gate == "passed"

    @pytest.mark.unit
    def test_pure_boilerplate_ratio_still_rejected(self):
        """Items with ratio < 0.08 and clean_text < 500 chars → ('low_quality', 'ratio')."""
        raw = "b" * 5_000
        clean = "Home About Contact Privacy Terms Subscribe " * 3  # ~130 chars, ratio ~0.026
        assert 100 <= len(clean) < 500
        assert len(clean) / len(raw) < 0.08
        quality, gate = score_content_quality(raw, clean)
        assert quality == "low_quality"
        assert gate == "ratio"

    @pytest.mark.unit
    def test_paywall_with_long_text_still_rejected(self):
        """A paywall page with 500+ clean chars is still rejected via paywall gate."""
        paywall_text = (
            "You don't have any active subscription. "
            "Subscribed with another email? Logout and login with that one. "
            "Your active subscription benefits include full access to all "
            "articles, premium content, and subscriber only features. "
            "Account subscription benefits are managed from your profile. "
            "Please sign in to continue reading this article. " * 3
        )
        assert len(paywall_text) >= 500
        quality, gate = score_content_quality(paywall_text, paywall_text)
        assert quality == "low_quality"
        assert gate == "paywall"


class TestExtractTitle:
    """Tests for extract_title logic."""

    @pytest.mark.unit
    def test_first_sentence_extracted(self):
        """First sentence becomes the title."""
        text = (
            "China launches new satellite for maritime surveillance. "
            "The satellite will enhance monitoring of sea lanes in the South China Sea."
        )
        title = extract_title(text)
        assert title is not None
        assert "China launches new satellite" in title

    @pytest.mark.unit
    def test_markdown_heading_preferred(self):
        """Markdown heading is used over first sentence when present."""
        text = "## Defence Budget Analysis 2026\n\nThe government increased spending by 12%."
        title = extract_title(text)
        assert title == "Defence Budget Analysis 2026"

    @pytest.mark.unit
    def test_empty_returns_none(self):
        assert extract_title("") is None
        assert extract_title(None) is None

    @pytest.mark.unit
    def test_very_short_text_returns_none(self):
        """Text too short for a title → None."""
        assert extract_title("Hi") is None


class TestComputeCleanHash:
    """Tests for compute_clean_hash determinism."""

    @pytest.mark.unit
    def test_deterministic(self):
        """Same text → same hash."""
        text = "India deploys additional troops along the northern border."
        h1 = compute_clean_hash(text)
        h2 = compute_clean_hash(text)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    @pytest.mark.unit
    def test_different_text_different_hash(self):
        """Different text → different hash."""
        h1 = compute_clean_hash("Alpha article about naval exercises.")
        h2 = compute_clean_hash("Beta article about air force procurement.")
        assert h1 != h2

    @pytest.mark.unit
    def test_whitespace_normalisation(self):
        """Whitespace differences produce the same hash."""
        h1 = compute_clean_hash("India   deploys   troops")
        h2 = compute_clean_hash("India deploys troops")
        assert h1 == h2


# ---------------------------------------------------------------------------
# Nav-icon garbage detection — RSS/web pages with scraped UI element names
# ---------------------------------------------------------------------------

from anveshak.scraper.clean import is_nav_icon_garbage


class TestNavIconGarbageDetection:
    """Detect text dominated by UI element names (icon labels, nav items).

    From real NDTV RSS scrapes: "arrow-down comments printer search bell
    top-nav right-arrow left-arrow arrow-down" — these are icon alt-text
    and aria-labels scraped as content.
    """

    @pytest.mark.unit
    def test_ndtv_arrow_nav_detected(self):
        """Real NDTV garbage from screenshot — icon alt-text."""
        text = "arrow-down comments printer search bell top-nav right-arrow left-arrow arrow-down"
        assert is_nav_icon_garbage(text) is True

    @pytest.mark.unit
    def test_ndtv_mixed_garbage(self):
        """Nav icons mixed with partial real content."""
        text = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down , Why Reservation For Their Children?: "
            "Supreme Court"
        )
        assert is_nav_icon_garbage(text) is True

    @pytest.mark.unit
    def test_ndtv_full_garbage_line(self):
        """Full garbage line from NDTV RSS page scrape."""
        text = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down \u092b\u093f\u0930\u094d :Board Exam Results "
            "2026 Get it on Google Play Download on the App Store facebook :) "
            "twitter :) WhatsApp :) Settings * Change Fo..."
        )
        assert is_nav_icon_garbage(text) is True

    @pytest.mark.unit
    def test_real_article_not_flagged(self):
        """Normal article text should NOT be detected as nav garbage."""
        text = (
            "India's Supreme Court ruled on reservation policies affecting "
            "children of government employees. The landmark judgment sets "
            "new precedent for affirmative action in education."
        )
        assert is_nav_icon_garbage(text) is False

    @pytest.mark.unit
    def test_military_article_not_flagged(self):
        """Military article with directional words should not be flagged."""
        text = (
            "The fighter jet turned left and executed a right banking maneuver "
            "before descending to search for the target below."
        )
        assert is_nav_icon_garbage(text) is False

    @pytest.mark.unit
    def test_short_text_not_flagged(self):
        """Short text shouldn't be flagged as nav garbage."""
        assert is_nav_icon_garbage("hello") is False
        assert is_nav_icon_garbage("") is False

    @pytest.mark.unit
    def test_menu_hamburger_icons(self):
        """Menu/hamburger icon labels."""
        text = "menu close hamburger search user account cart chevron-down chevron-up"
        assert is_nav_icon_garbage(text) is True

    @pytest.mark.unit
    def test_social_share_icons(self):
        """Social sharing icon labels."""
        text = "share facebook twitter whatsapp telegram copy-link email print bookmark"
        assert is_nav_icon_garbage(text) is True


class TestCleanExtractedTextNavIcons:
    """clean_extracted_text should strip nav-icon garbage lines."""

    @pytest.mark.unit
    def test_ndtv_garbage_stripped(self):
        """NDTV nav icons should be stripped, real content preserved."""
        text = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down\n"
            "India's Oil Reserves: How Long Can They Last As Iran War..."
        )
        result = clean_extracted_text(text)
        assert "arrow-down" not in result
        assert "Oil Reserves" in result

    @pytest.mark.unit
    def test_multiple_garbage_lines_stripped(self):
        """Multiple nav-icon lines in sequence should all be stripped."""
        text = (
            "arrow-down comments printer search bell\n"
            "menu close hamburger search user\n"
            "Real article content about defence policy changes in India."
        )
        result = clean_extracted_text(text)
        assert "arrow-down" not in result
        assert "hamburger" not in result
        assert "defence policy" in result


class TestExtractTitleNavGarbage:
    """extract_title should reject nav-icon garbage as titles."""

    @pytest.mark.unit
    def test_nav_garbage_title_rejected(self):
        """Nav-icon text should not become a title."""
        text = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down\n"
            "India's Oil Reserves: How Long Can They Last As Iran War Looms."
        )
        title = extract_title(text)
        assert title is None or "arrow-down" not in title

    @pytest.mark.unit
    def test_skip_links_title_rejected(self):
        """'Skip linksSkip to Content' should not be a title."""
        text = (
            "Skip linksSkip to Content play Live Close navigation menu Navigation "
            "menu here to search\n"
            "British climber sets record with 20th Everest summit."
        )
        title = extract_title(text)
        assert title is None or "Skip links" not in title


class TestScoreContentQualityNavGarbage:
    """score_content_quality should flag nav-icon-dominated content."""

    @pytest.mark.unit
    def test_nav_only_garbage_is_low_quality(self):
        """Content that is purely nav icons → low_quality."""
        raw = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down\n"
            "menu close hamburger search user account cart\n"
            "share facebook twitter whatsapp telegram\n"
        )
        cleaned = clean_extracted_text(raw)
        quality, _gate = score_content_quality(raw, cleaned)
        assert quality == "low_quality"

    @pytest.mark.unit
    def test_nav_prefix_stripped_from_content(self):
        """Nav icon prefix on a line should be stripped, leaving real content."""
        raw = (
            "arrow-down comments printer search bell top-nav right-arrow "
            "left-arrow arrow-down , Why Reservation For Their Children?: "
            "Supreme Court"
        )
        cleaned = clean_extracted_text(raw)
        assert "arrow-down" not in cleaned
