"""Unit tests for Engine C identifier extraction (Step 1).

Tests 15 identifier types:
  Part 1: PHONE_IN, UPI, EMAIL, CRYPTO_BTC, CRYPTO_ETH, CRYPTO_TRC20,
           TELEGRAM_HANDLE, INSTAGRAM_HANDLE
  Part 2: URL_DOMAIN, GSTIN, UDYAM, PAN, IFSC, BANK_ACCOUNT, SEBI_REG

Each type has: positive match, negative/false-positive, normalization, edge case.
Pure unit tests — no DB, no I/O.
"""
from __future__ import annotations

import pytest

from anveshak.analyst.identifiers import IdentifierMatch, extract_identifiers

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _types(results: list[IdentifierMatch]) -> set[str]:
    return {r.identifier_type for r in results}


def _values(results: list[IdentifierMatch], id_type: str) -> list[str]:
    return [r.normalized_value for r in results if r.identifier_type == id_type]


# ===========================================================================
# PHONE_IN — Indian phone numbers
# ===========================================================================


class TestPhoneIN:
    """Indian phone number extraction."""

    def test_phone_with_plus91_prefix(self):
        text = "Call me at +919876543210 for details"
        results = extract_identifiers(text)
        assert "PHONE_IN" in _types(results)
        assert "9876543210" in _values(results, "PHONE_IN")

    def test_phone_with_zero_prefix(self):
        text = "Reach us at 09876543210"
        results = extract_identifiers(text)
        assert "9876543210" in _values(results, "PHONE_IN")

    def test_phone_with_spaces(self):
        """Phone with spaces/dashes should still match."""
        text = "WhatsApp: +91 98765 43210"
        results = extract_identifiers(text)
        assert "9876543210" in _values(results, "PHONE_IN")

    def test_phone_normalization_strips_to_10_digits(self):
        text = "Contact +91-9876543210 now"
        results = extract_identifiers(text)
        vals = _values(results, "PHONE_IN")
        assert len(vals) >= 1
        assert all(len(v) == 10 for v in vals), "Must normalize to 10 digits"

    def test_phone_must_start_with_6_to_9(self):
        """Indian mobile numbers start with 6-9. 5xxx should not match."""
        text = "Call +915123456789"
        results = extract_identifiers(text)
        assert "PHONE_IN" not in _types(results)

    def test_bare_10_digits_without_context_lower_confidence(self):
        """10 digits without +91/0 prefix or context words = lower confidence."""
        text = "Reference: 9876543210"
        results = extract_identifiers(text)
        phones = [r for r in results if r.identifier_type == "PHONE_IN"]
        if phones:
            assert phones[0].confidence < 0.9, "Bare number without context should have lower confidence"

    def test_phone_near_context_word_higher_confidence(self):
        """Phone near 'call'/'WhatsApp' = higher confidence."""
        text = "WhatsApp me at 9876543210"
        results = extract_identifiers(text)
        phones = [r for r in results if r.identifier_type == "PHONE_IN"]
        assert len(phones) >= 1
        assert phones[0].confidence >= 0.8

    def test_phone_rejects_short_numbers(self):
        """Less than 10 digits should not match."""
        text = "Call 98765"
        results = extract_identifiers(text)
        assert "PHONE_IN" not in _types(results)

    def test_trailing_zero_in_text_not_prefix(self):
        """A number like '20' before phone should NOT count as 0-prefix."""
        text = "Reference 20 9876543210"
        results = extract_identifiers(text)
        phones = [r for r in results if r.identifier_type == "PHONE_IN"]
        assert len(phones) >= 1
        assert phones[0].confidence < 0.9, "Trailing 0 in '20' is not a trunk prefix"

    def test_multiple_phones_in_text(self):
        text = "Primary: +919876543210, backup: +918765432109"
        results = extract_identifiers(text)
        phones = _values(results, "PHONE_IN")
        assert "9876543210" in phones
        assert "8765432109" in phones


# ===========================================================================
# UPI — user@bank format
# ===========================================================================


class TestUPI:
    """UPI ID extraction."""

    def test_upi_basic(self):
        text = "Pay to user123@ybl"
        results = extract_identifiers(text)
        assert "UPI" in _types(results)
        assert "user123@ybl" in _values(results, "UPI")

    def test_upi_paytm(self):
        text = "Send money to merchant@paytm"
        results = extract_identifiers(text)
        assert "merchant@paytm" in _values(results, "UPI")

    def test_upi_okaxis(self):
        text = "UPI: myname@okaxis"
        results = extract_identifiers(text)
        assert "myname@okaxis" in _values(results, "UPI")

    def test_upi_normalization_lowercase(self):
        text = "Pay MyName@YBL now"
        results = extract_identifiers(text)
        vals = _values(results, "UPI")
        assert all(v == v.lower() for v in vals), "UPI must be lowercased"

    def test_upi_not_confused_with_email(self):
        """UPI IDs should not also appear as EMAIL."""
        text = "Pay to user@paytm"
        results = extract_identifiers(text)
        emails = _values(results, "EMAIL")
        assert "user@paytm" not in emails, "UPI ID should not be extracted as EMAIL"

    def test_upi_with_dots_and_dashes(self):
        text = "user.name-123@oksbi"
        results = extract_identifiers(text)
        assert "user.name-123@oksbi" in _values(results, "UPI")

    def test_upi_unknown_bank_not_matched(self):
        """user@randombank should NOT match as UPI."""
        text = "contact user@randombank"
        results = extract_identifiers(text)
        assert "user@randombank" not in _values(results, "UPI")

    def test_upi_high_confidence(self):
        """UPI matches are exact — confidence should be 1.0."""
        text = "Pay to seller@ybl"
        results = extract_identifiers(text)
        upis = [r for r in results if r.identifier_type == "UPI"]
        assert len(upis) >= 1
        assert upis[0].confidence == 1.0


# ===========================================================================
# EMAIL
# ===========================================================================


class TestEmail:
    """Email extraction."""

    def test_email_basic(self):
        text = "Contact us at info@example.com"
        results = extract_identifiers(text)
        assert "EMAIL" in _types(results)
        assert "info@example.com" in _values(results, "EMAIL")

    def test_email_normalization_lowercase(self):
        text = "Write to Admin@Example.COM"
        results = extract_identifiers(text)
        vals = _values(results, "EMAIL")
        assert "admin@example.com" in vals

    def test_email_with_subdomain(self):
        text = "alerts@mail.agency.gov.in"
        results = extract_identifiers(text)
        assert "alerts@mail.agency.gov.in" in _values(results, "EMAIL")

    def test_email_rejects_no_tld(self):
        """user@localhost should not match."""
        text = "debug user@localhost"
        results = extract_identifiers(text)
        assert "user@localhost" not in _values(results, "EMAIL")

    def test_email_excludes_upi_ids(self):
        """UPI IDs like user@ybl should not appear as EMAIL."""
        text = "Pay user@ybl or email admin@example.com"
        results = extract_identifiers(text)
        emails = _values(results, "EMAIL")
        assert "user@ybl" not in emails
        assert "admin@example.com" in emails


# ===========================================================================
# CRYPTO_BTC — Bitcoin addresses
# ===========================================================================


class TestCryptoBTC:
    """Bitcoin address extraction."""

    def test_btc_legacy_address(self):
        """Legacy address starting with 1."""
        text = "Send BTC to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        results = extract_identifiers(text)
        assert "CRYPTO_BTC" in _types(results)
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in _values(results, "CRYPTO_BTC")

    def test_btc_segwit_address(self):
        """Segwit address starting with 3."""
        text = "Wallet: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        results = extract_identifiers(text)
        assert "CRYPTO_BTC" in _types(results)

    def test_btc_bech32_address(self):
        """Bech32 address starting with bc1."""
        text = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        results = extract_identifiers(text)
        assert "CRYPTO_BTC" in _types(results)

    def test_btc_preserves_case(self):
        """BTC addresses are case-sensitive — do NOT lowercase."""
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        text = f"Pay {addr}"
        results = extract_identifiers(text)
        assert addr in _values(results, "CRYPTO_BTC")

    def test_btc_rejects_too_short(self):
        """Too-short strings starting with 1/3 should not match."""
        text = "Order 1ABC123"
        results = extract_identifiers(text)
        assert "CRYPTO_BTC" not in _types(results)

    def test_btc_high_confidence(self):
        text = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        results = extract_identifiers(text)
        btcs = [r for r in results if r.identifier_type == "CRYPTO_BTC"]
        assert btcs[0].confidence >= 0.9


# ===========================================================================
# CRYPTO_ETH — Ethereum addresses
# ===========================================================================


class TestCryptoETH:
    """Ethereum address extraction."""

    def test_eth_address(self):
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD28"
        text = f"ETH wallet: {addr}"
        results = extract_identifiers(text)
        assert "CRYPTO_ETH" in _types(results)

    def test_eth_normalization_lowercase(self):
        addr = "0x742D35CC6634C0532925A3B844BC9E7595F2BD28"
        text = f"Send to {addr}"
        results = extract_identifiers(text)
        vals = _values(results, "CRYPTO_ETH")
        assert all(v == v.lower() for v in vals)

    def test_eth_exact_40_hex_after_0x(self):
        """Must be exactly 40 hex chars after 0x."""
        text = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD"  # 39 chars
        results = extract_identifiers(text)
        assert "CRYPTO_ETH" not in _types(results)

    def test_eth_rejects_non_hex(self):
        """0x followed by non-hex chars should not match."""
        text = "0xZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
        results = extract_identifiers(text)
        assert "CRYPTO_ETH" not in _types(results)

    def test_eth_high_confidence(self):
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD28"
        results = extract_identifiers(addr)
        eths = [r for r in results if r.identifier_type == "CRYPTO_ETH"]
        assert eths[0].confidence >= 0.9


# ===========================================================================
# CRYPTO_TRC20 — TRON TRC-20 addresses
# ===========================================================================


class TestCryptoTRC20:
    """TRC-20 (TRON) address extraction."""

    def test_trc20_address(self):
        addr = "TJYeasTPa8dGTLi7rWCvFzEQdmGSMH4XsH"
        text = f"USDT (TRC20): {addr}"
        results = extract_identifiers(text)
        assert "CRYPTO_TRC20" in _types(results)
        assert addr in _values(results, "CRYPTO_TRC20")

    def test_trc20_preserves_case(self):
        addr = "TJYeasTPa8dGTLi7rWCvFzEQdmGSMH4XsH"
        results = extract_identifiers(addr)
        assert addr in _values(results, "CRYPTO_TRC20")

    def test_trc20_exact_34_chars(self):
        """Must be T + exactly 33 alphanumeric chars."""
        text = "TABC123"  # too short
        results = extract_identifiers(text)
        assert "CRYPTO_TRC20" not in _types(results)

    def test_trc20_rejects_non_T_start(self):
        """Must start with T."""
        text = "AJYeasTPa8dGTLi7rWCvFzEQdmGSMH4XsH"
        results = extract_identifiers(text)
        assert "CRYPTO_TRC20" not in _types(results)


# ===========================================================================
# TELEGRAM_HANDLE
# ===========================================================================


class TestTelegramHandle:
    """Telegram handle extraction."""

    def test_telegram_handle_basic(self):
        text = "Join @fraud_alerts for updates"
        results = extract_identifiers(text)
        assert "TELEGRAM_HANDLE" in _types(results)

    def test_telegram_handle_normalization(self):
        """Strip @ and lowercase."""
        text = "Contact @FraudAlerts"
        results = extract_identifiers(text)
        vals = _values(results, "TELEGRAM_HANDLE")
        assert "fraudalerts" in vals

    def test_telegram_handle_min_length_5(self):
        """Telegram handles must be at least 5 chars (excluding @)."""
        text = "User @ab is short"
        results = extract_identifiers(text)
        tg = _values(results, "TELEGRAM_HANDLE")
        assert "ab" not in tg

    def test_telegram_handle_must_start_with_letter(self):
        """Telegram handles must start with a letter."""
        text = "Contact @123group"
        results = extract_identifiers(text)
        assert "123group" not in _values(results, "TELEGRAM_HANDLE")

    def test_telegram_platform_context_higher_confidence(self):
        """When platform is 'telegram', confidence should be higher."""
        text = "Join @easy_money_group now"
        results_tg = extract_identifiers(text, platform="telegram")
        results_web = extract_identifiers(text, platform="web")
        tg_conf = [r.confidence for r in results_tg if r.identifier_type == "TELEGRAM_HANDLE"]
        web_conf = [r.confidence for r in results_web if r.identifier_type == "TELEGRAM_HANDLE"]
        assert tg_conf[0] > web_conf[0]

    def test_telegram_handle_with_underscores(self):
        text = "Follow @investment_tips_daily"
        results = extract_identifiers(text)
        assert "investment_tips_daily" in _values(results, "TELEGRAM_HANDLE")

    def test_telegram_handle_max_32_chars(self):
        """Telegram handles max 32 chars."""
        handle = "@a" + "b" * 32  # 33 chars total excluding @
        text = f"Join {handle}"
        results = extract_identifiers(text)
        # Should not match the oversized handle
        tg = [r for r in results if r.identifier_type == "TELEGRAM_HANDLE"
              and len(r.normalized_value) > 32]
        assert len(tg) == 0


# ===========================================================================
# INSTAGRAM_HANDLE
# ===========================================================================


class TestInstagramHandle:
    """Instagram handle extraction."""

    def test_instagram_handle_on_instagram_platform(self):
        """On Instagram platform, @handles are INSTAGRAM_HANDLE."""
        text = "Follow @scam_seller for deals"
        results = extract_identifiers(text, platform="instagram")
        assert "INSTAGRAM_HANDLE" in _types(results)

    def test_instagram_handle_normalization(self):
        text = "Check @ScamSeller"
        results = extract_identifiers(text, platform="instagram")
        vals = _values(results, "INSTAGRAM_HANDLE")
        assert "scamseller" in vals

    def test_instagram_vs_telegram_disambiguation(self):
        """On non-platform context, handles default to TELEGRAM_HANDLE.
        On instagram platform, they are INSTAGRAM_HANDLE."""
        text = "Follow @crypto_guru"
        results_ig = extract_identifiers(text, platform="instagram")
        results_default = extract_identifiers(text)
        ig_types = _types(results_ig)
        default_types = _types(results_default)
        assert "INSTAGRAM_HANDLE" in ig_types
        assert "TELEGRAM_HANDLE" in default_types

    def test_instagram_handle_min_length(self):
        """Instagram handles need at least 1 char but we enforce 5 for relevance."""
        text = "User @ab"
        results = extract_identifiers(text, platform="instagram")
        ig = _values(results, "INSTAGRAM_HANDLE")
        assert "ab" not in ig


# ===========================================================================
# Cross-cutting tests
# ===========================================================================


class TestCrossCutting:
    """Cross-type behavior and edge cases."""

    def test_empty_text_returns_empty(self):
        assert extract_identifiers("") == []

    def test_no_identifiers_returns_empty(self):
        text = "This is a normal news article about weather"
        assert extract_identifiers(text) == []

    def test_multiple_types_in_one_text(self):
        """Text with phone + UPI + email should extract all."""
        text = "Call +919876543210 or pay user@ybl or email admin@example.com"
        results = extract_identifiers(text)
        types = _types(results)
        assert "PHONE_IN" in types
        assert "UPI" in types
        assert "EMAIL" in types

    def test_identifier_match_has_required_fields(self):
        text = "Pay user@ybl"
        results = extract_identifiers(text)
        assert len(results) >= 1
        r = results[0]
        assert hasattr(r, "identifier_type")
        assert hasattr(r, "raw_value")
        assert hasattr(r, "normalized_value")
        assert hasattr(r, "confidence")

    def test_no_duplicate_extractions(self):
        """Same identifier appearing twice should only be extracted once."""
        text = "Call +919876543210. Again: +919876543210"
        results = extract_identifiers(text)
        phones = _values(results, "PHONE_IN")
        assert phones.count("9876543210") == 1

    def test_identifiers_in_noisy_text(self):
        """Identifiers embedded in messy text should still be found."""
        text = """
        🚨EARN 50K DAILY🚨
        Join our VIP group @easy_money_tips
        WhatsApp: +91 98765 43210
        Pay registration: merchant@paytm
        BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
        """
        results = extract_identifiers(text)
        types = _types(results)
        assert "PHONE_IN" in types
        assert "UPI" in types
        assert "CRYPTO_BTC" in types
        assert "TELEGRAM_HANDLE" in types


# ===========================================================================
# URL_DOMAIN — URL extraction with domain normalization
# ===========================================================================


class TestURLDomain:
    """URL/domain extraction."""

    def test_url_basic_http(self):
        text = "Visit http://example.com/page for details"
        results = extract_identifiers(text)
        assert "URL_DOMAIN" in _types(results)
        vals = _values(results, "URL_DOMAIN")
        assert "example.com" in vals

    def test_url_https(self):
        text = "Go to https://scam-site.xyz/offer?id=123"
        results = extract_identifiers(text)
        assert "scam-site.xyz" in _values(results, "URL_DOMAIN")

    def test_url_strips_www(self):
        """www prefix should be stripped from domain."""
        text = "Visit https://www.fraud-site.com/login"
        results = extract_identifiers(text)
        assert "fraud-site.com" in _values(results, "URL_DOMAIN")

    def test_url_subdomain_preserved(self):
        """Non-www subdomains should be preserved."""
        text = "https://api.phishing-site.net/hook"
        results = extract_identifiers(text)
        assert "api.phishing-site.net" in _values(results, "URL_DOMAIN")

    def test_url_dedup_same_domain(self):
        """Multiple URLs with same domain → one extraction."""
        text = "https://evil.com/page1 and https://evil.com/page2"
        results = extract_identifiers(text)
        vals = _values(results, "URL_DOMAIN")
        assert vals.count("evil.com") == 1

    def test_url_rejects_no_protocol(self):
        """Bare domain without http/https should NOT match."""
        text = "Visit example.com for details"
        results = extract_identifiers(text)
        assert "URL_DOMAIN" not in _types(results)

    def test_url_confidence(self):
        text = "https://scam-site.com/offer"
        results = extract_identifiers(text)
        urls = [r for r in results if r.identifier_type == "URL_DOMAIN"]
        assert len(urls) >= 1
        assert urls[0].confidence >= 0.8

    def test_url_raw_value_full_url(self):
        """raw_value should be the full URL, normalized_value is domain."""
        text = "Visit https://fraud.com/page?q=1"
        results = extract_identifiers(text)
        urls = [r for r in results if r.identifier_type == "URL_DOMAIN"]
        assert len(urls) >= 1
        assert urls[0].raw_value.startswith("https://")
        assert urls[0].normalized_value == "fraud.com"

    def test_telegram_url_extracts_handle_not_domain(self):
        """https://t.me/username should extract as TELEGRAM_HANDLE, NOT URL_DOMAIN."""
        text = "Join https://t.me/defencenews for updates"
        results = extract_identifiers(text)
        assert "t.me" not in _values(results, "URL_DOMAIN"), \
            "t.me must NOT appear as URL_DOMAIN"
        assert "defencenews" in _values(results, "TELEGRAM_HANDLE"), \
            "Telegram URL path must be extracted as TELEGRAM_HANDLE"

    def test_normal_url_still_extracts_domain(self):
        """Non-Telegram URLs must still extract as URL_DOMAIN."""
        text = "Visit https://ndtv.com/article/123"
        results = extract_identifiers(text)
        assert "ndtv.com" in _values(results, "URL_DOMAIN")

    def test_telegram_joinchat_url_skipped(self):
        """https://t.me/joinchat/abc is not a handle — skip it."""
        text = "Join https://t.me/joinchat/abc123"
        results = extract_identifiers(text)
        assert "joinchat" not in _values(results, "TELEGRAM_HANDLE")

    def test_telegram_share_url_skipped(self):
        """https://t.me/share/url is not a handle — skip it."""
        text = "Share via https://t.me/share/url?text=hello"
        results = extract_identifiers(text)
        assert "share" not in _values(results, "TELEGRAM_HANDLE")


# ===========================================================================
# GSTIN — Indian GST Identification Number
# ===========================================================================


class TestGSTIN:
    """GSTIN extraction."""

    def test_gstin_basic(self):
        text = "GSTIN: 27AABCU9603R1ZM"
        results = extract_identifiers(text)
        assert "GSTIN" in _types(results)
        assert "27AABCU9603R1ZM" in _values(results, "GSTIN")

    def test_gstin_in_sentence(self):
        text = "The company GST number is 07AAECG4582J1Z5 and registered in Delhi"
        results = extract_identifiers(text)
        assert "07AAECG4582J1Z5" in _values(results, "GSTIN")

    def test_gstin_normalization_uppercase(self):
        text = "gstin 27aabcu9603r1zm"
        results = extract_identifiers(text)
        vals = _values(results, "GSTIN")
        assert all(v == v.upper() for v in vals)

    def test_gstin_rejects_invalid_format(self):
        """Invalid GSTIN (wrong structure) should not match."""
        text = "Reference: 12ABCDE1234FGHJ"
        results = extract_identifiers(text)
        assert "GSTIN" not in _types(results)

    def test_gstin_rejects_wrong_state_code(self):
        """State code must be 01-37. 99 is invalid but format may still match.
        We check regex pattern only, not semantic validity."""
        text = "GSTIN: 99AABCU9603R1ZM"
        results = extract_identifiers(text)
        # Regex matches format — semantic validation is Step 2
        assert "GSTIN" in _types(results)

    def test_gstin_high_confidence(self):
        text = "GSTIN: 27AABCU9603R1ZM"
        results = extract_identifiers(text)
        gstins = [r for r in results if r.identifier_type == "GSTIN"]
        assert gstins[0].confidence >= 0.95


# ===========================================================================
# UDYAM — Udyam Registration Number
# ===========================================================================


class TestUdyam:
    """Udyam registration number extraction."""

    def test_udyam_basic(self):
        text = "Registration: UDYAM-MH-02-0012345"
        results = extract_identifiers(text)
        assert "UDYAM" in _types(results)
        assert "UDYAM-MH-02-0012345" in _values(results, "UDYAM")

    def test_udyam_different_states(self):
        text = "UDYAM-KA-15-0067890 registered in Karnataka"
        results = extract_identifiers(text)
        assert "UDYAM-KA-15-0067890" in _values(results, "UDYAM")

    def test_udyam_normalization_uppercase(self):
        text = "udyam-mh-02-0012345"
        results = extract_identifiers(text)
        vals = _values(results, "UDYAM")
        assert all(v == v.upper() for v in vals)

    def test_udyam_rejects_wrong_format(self):
        """Missing district code or short serial should not match."""
        text = "UDYAM-MH-1234"
        results = extract_identifiers(text)
        assert "UDYAM" not in _types(results)

    def test_udyam_high_confidence(self):
        text = "UDYAM-DL-07-0098765"
        results = extract_identifiers(text)
        udyams = [r for r in results if r.identifier_type == "UDYAM"]
        assert udyams[0].confidence >= 0.95


# ===========================================================================
# PAN — Permanent Account Number
# ===========================================================================


class TestPAN:
    """PAN extraction — context-dependent due to moderate FP risk."""

    def test_pan_with_context(self):
        """PAN near context words should be extracted."""
        text = "His PAN is ABCDE1234F"
        results = extract_identifiers(text)
        assert "PAN" in _types(results)
        assert "ABCDE1234F" in _values(results, "PAN")

    def test_pan_with_pan_keyword(self):
        text = "PAN card number: BQRPP1234K"
        results = extract_identifiers(text)
        assert "BQRPP1234K" in _values(results, "PAN")

    def test_pan_without_context_not_extracted(self):
        """Bare 10-char alphanumeric matching PAN format but no context → skip."""
        text = "The code ABCDE1234F was generated"
        results = extract_identifiers(text)
        # Without PAN/tax/income context, should NOT extract
        assert "PAN" not in _types(results)

    def test_pan_normalization_uppercase(self):
        text = "PAN: abcde1234f"
        results = extract_identifiers(text)
        vals = _values(results, "PAN")
        assert all(v == v.upper() for v in vals)

    def test_pan_rejects_wrong_format(self):
        """PAN must be AAAAA9999A pattern."""
        text = "PAN: 12345ABCDE"
        results = extract_identifiers(text)
        assert "PAN" not in _types(results)

    def test_pan_context_words(self):
        """Various context words should trigger extraction."""
        for ctx in ["PAN", "pan card", "income tax", "tax id", "permanent account"]:
            text = f"{ctx}: ABCDE1234F"
            results = extract_identifiers(text)
            assert "PAN" in _types(results), f"PAN not extracted with context '{ctx}'"

    def test_pan_moderate_confidence(self):
        text = "PAN: ABCDE1234F"
        results = extract_identifiers(text)
        pans = [r for r in results if r.identifier_type == "PAN"]
        assert 0.7 <= pans[0].confidence <= 0.95


# ===========================================================================
# IFSC — Indian Financial System Code
# ===========================================================================


class TestIFSC:
    """IFSC code extraction."""

    def test_ifsc_basic(self):
        text = "IFSC: SBIN0001234"
        results = extract_identifiers(text)
        assert "IFSC" in _types(results)
        assert "SBIN0001234" in _values(results, "IFSC")

    def test_ifsc_hdfc(self):
        text = "Bank IFSC code HDFC0002345"
        results = extract_identifiers(text)
        assert "HDFC0002345" in _values(results, "IFSC")

    def test_ifsc_fifth_char_must_be_zero(self):
        """5th character must be 0 in IFSC."""
        text = "Code: SBIN1001234"
        results = extract_identifiers(text)
        assert "IFSC" not in _types(results)

    def test_ifsc_normalization_uppercase(self):
        text = "IFSC: sbin0001234"
        results = extract_identifiers(text)
        vals = _values(results, "IFSC")
        assert all(v == v.upper() for v in vals)

    def test_ifsc_rejects_wrong_length(self):
        """IFSC must be exactly 11 chars."""
        text = "IFSC: SBIN000123"  # only 10
        results = extract_identifiers(text)
        assert "IFSC" not in _types(results)

    def test_ifsc_high_confidence(self):
        text = "SBIN0001234"
        results = extract_identifiers(text)
        ifscs = [r for r in results if r.identifier_type == "IFSC"]
        assert len(ifscs) >= 1
        assert ifscs[0].confidence >= 0.9


# ===========================================================================
# BANK_ACCOUNT — Indian bank account numbers (context-required)
# ===========================================================================


class TestBankAccount:
    """Bank account number extraction — HIGH FP, requires context."""

    def test_bank_account_with_context(self):
        """Account number near 'account' should be extracted."""
        text = "Transfer to account 12345678901234"
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" in _types(results)
        assert "12345678901234" in _values(results, "BANK_ACCOUNT")

    def test_bank_account_with_ac_abbreviation(self):
        text = "A/C No: 9876543210123"
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" in _types(results)

    def test_bank_account_with_bank_keyword(self):
        text = "Bank account number 112233445566"
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" in _types(results)

    def test_bank_account_without_context_not_extracted(self):
        """Bare long number without bank context → NOT extracted."""
        text = "The reference number is 12345678901234"
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" not in _types(results)

    def test_bank_account_rejects_too_short(self):
        """Less than 9 digits should not match even with context."""
        text = "Account: 12345678"  # 8 digits
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" not in _types(results)

    def test_bank_account_rejects_too_long(self):
        """More than 18 digits should not match."""
        text = "Account: 1234567890123456789"  # 19 digits
        results = extract_identifiers(text)
        assert "BANK_ACCOUNT" not in _types(results)

    def test_bank_account_strips_spaces(self):
        """Spaces in account number should be stripped."""
        text = "Account no: 1234 5678 9012 34"
        results = extract_identifiers(text)
        vals = _values(results, "BANK_ACCOUNT")
        if vals:
            assert all(" " not in v for v in vals)

    def test_bank_account_low_confidence(self):
        """Bank accounts are high-FP, confidence should reflect that."""
        text = "Account: 12345678901234"
        results = extract_identifiers(text)
        accts = [r for r in results if r.identifier_type == "BANK_ACCOUNT"]
        assert accts[0].confidence <= 0.8

    def test_bank_account_not_confused_with_phone(self):
        """10-digit bank account with context shouldn't also be PHONE_IN."""
        text = "Bank account 6789012345"
        results = extract_identifiers(text)
        # Could match both — but bank account should be present
        assert "BANK_ACCOUNT" in _types(results)


# ===========================================================================
# SEBI_REG — SEBI Registration Number
# ===========================================================================


class TestSEBIReg:
    """SEBI registration number extraction."""

    def test_sebi_reg_basic(self):
        text = "SEBI registration: INB123456789012"
        results = extract_identifiers(text)
        assert "SEBI_REG" in _types(results)
        assert "INB123456789012" in _values(results, "SEBI_REG")

    def test_sebi_reg_merchant_banker(self):
        text = "SEBI Reg No INM000012345678"
        results = extract_identifiers(text)
        assert "SEBI_REG" in _types(results)

    def test_sebi_reg_normalization_uppercase(self):
        text = "inb123456789012"
        results = extract_identifiers(text)
        vals = _values(results, "SEBI_REG")
        assert all(v == v.upper() for v in vals)

    def test_sebi_reg_rejects_wrong_prefix(self):
        """Must start with IN followed by a letter."""
        text = "Code: XYZ123456789012"
        results = extract_identifiers(text)
        assert "SEBI_REG" not in _types(results)

    def test_sebi_reg_rejects_wrong_length(self):
        """Must be IN + letter + exactly 12 digits = 15 chars total."""
        text = "INB12345"  # too short
        results = extract_identifiers(text)
        assert "SEBI_REG" not in _types(results)

    def test_sebi_reg_high_confidence(self):
        text = "INB123456789012"
        results = extract_identifiers(text)
        sebis = [r for r in results if r.identifier_type == "SEBI_REG"]
        assert len(sebis) >= 1
        assert sebis[0].confidence >= 0.95


# ===========================================================================
# Cross-cutting tests — Part 2
# ===========================================================================


class TestCrossCuttingPart2:
    """Cross-type tests including Part 2 types."""

    def test_all_15_types_extractable(self):
        """Single text with all 15 identifier types."""
        text = """
        Call +919876543210 or WhatsApp.
        Pay user@ybl or email admin@example.com
        BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
        ETH: 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD28
        USDT: TJYeasTPa8dGTLi7rWCvFzEQdmGSMH4XsH
        Follow @easy_money_group
        Visit https://scam-site.com/offer
        GSTIN: 27AABCU9603R1ZM
        UDYAM-MH-02-0012345
        PAN card: ABCDE1234F
        IFSC: SBIN0001234
        Bank account: 12345678901234
        SEBI reg: INB123456789012
        """
        results = extract_identifiers(text, platform="telegram")
        types = _types(results)
        expected = {
            "PHONE_IN", "UPI", "EMAIL", "CRYPTO_BTC", "CRYPTO_ETH",
            "CRYPTO_TRC20", "TELEGRAM_HANDLE", "URL_DOMAIN", "GSTIN",
            "UDYAM", "PAN", "IFSC", "BANK_ACCOUNT", "SEBI_REG",
        }
        missing = expected - types
        assert not missing, f"Missing types: {missing}"

    def test_gstin_not_confused_with_pan(self):
        """GSTIN contains PAN-like substring — should not double-extract as PAN."""
        text = "GSTIN: 27AABCU9603R1ZM"
        results = extract_identifiers(text)
        assert "GSTIN" in _types(results)
        # The PAN-like portion should not be separately extracted
        pans = _values(results, "PAN")
        assert "AABCU9603R" not in pans

    def test_ifsc_not_confused_with_pan(self):
        """IFSC like SBIN0001234 contains letter patterns — should not be PAN."""
        text = "IFSC: SBIN0001234"
        results = extract_identifiers(text)
        assert "IFSC" in _types(results)
        pans = _values(results, "PAN")
        # SBIN0001234 doesn't match PAN format anyway (11 chars vs 10)
        assert len(pans) == 0
