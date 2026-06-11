"""Unit tests for Engine C identifier extraction (Step 1, Part 1).

Tests 8 identifier types: PHONE_IN, UPI, EMAIL, CRYPTO_BTC, CRYPTO_ETH,
CRYPTO_TRC20, TELEGRAM_HANDLE, INSTAGRAM_HANDLE.

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
