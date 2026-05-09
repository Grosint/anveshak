"""Unit tests for scraper fetch helpers — validate_onion_url and extract_article_links.

Catches real bugs:
  - validate_onion_url checks .onion suffix on netloc BEFORE scheme,
    so an ftp://*.onion URL passes the domain check but fails on scheme.
    The order matters for error messages: scheme error vs DNS leak error.
  - extract_article_links depends on settings.scraper_follow_same_domain
    and settings.scraper_max_links_per_page — tests must patch settings.

pytest.mark.unit — no network, no browser, no external deps.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# validate_onion_url
# ---------------------------------------------------------------------------


class TestValidateOnionUrl:

    def test_valid_http_onion(self):
        """http://<hash>.onion/page should not raise."""
        from anveshak.scraper.fetch import validate_onion_url

        validate_onion_url("http://abc123def456.onion/page")

    def test_valid_https_onion(self):
        """https .onion addresses are also valid."""
        from anveshak.scraper.fetch import validate_onion_url

        validate_onion_url("https://abc123def456.onion/secret")

    def test_invalid_not_onion_raises_valueerror(self):
        """A clearnet URL must raise ValueError mentioning DNS leak prevention."""
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError, match="(?i)dns leak"):
            validate_onion_url("http://example.com/page")

    def test_ftp_scheme_onion_raises_valueerror(self):
        """ftp:// scheme on a .onion address must raise — only http/https allowed.

        Bug caught: if the code checks netloc before scheme, an ftp .onion URL
        passes the domain check but must still fail on scheme.
        """
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError, match="(?i)scheme"):
            validate_onion_url("ftp://abc123.onion/file")

    def test_subdomain_of_onion_is_valid(self):
        """forum.abc123.onion should pass — netloc ends with .onion."""
        from anveshak.scraper.fetch import validate_onion_url

        validate_onion_url("http://forum.abc123.onion/thread/42")

    def test_onion_in_path_not_domain_raises(self):
        """example.com/path/to/.onion must NOT pass — .onion must be in netloc."""
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError):
            validate_onion_url("http://example.com/path/to/.onion")

    def test_empty_url_raises(self):
        """Empty string has no netloc → must raise."""
        from anveshak.scraper.fetch import validate_onion_url

        with pytest.raises(ValueError):
            validate_onion_url("")


# ---------------------------------------------------------------------------
# extract_article_links
# ---------------------------------------------------------------------------


class TestExtractArticleLinks:

    @patch("anveshak.scraper.fetch.settings")
    def test_same_domain_only(self, mock_settings):
        """Cross-domain links are excluded when scraper_follow_same_domain is True."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = """
        <a href="http://example.com/article1">A1</a>
        <a href="http://other.com/article2">A2</a>
        """
        links = extract_article_links(html, "http://example.com")
        assert "http://example.com/article1" in links
        assert all("other.com" not in link for link in links)

    @patch("anveshak.scraper.fetch.settings")
    def test_relative_href_resolved(self, mock_settings):
        """Relative hrefs must be resolved against the base URL."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = '<a href="/news/article">News</a>'
        links = extract_article_links(html, "http://example.com")
        assert "http://example.com/news/article" in links

    @patch("anveshak.scraper.fetch.settings")
    def test_skips_media_extensions(self, mock_settings):
        """Binary/media links (.jpg, .mp4, etc.) excluded. PDFs are now allowed."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = """
        <a href="/photo.jpg">Photo</a>
        <a href="/doc.pdf">Doc</a>
        <a href="/video.mp4">Video</a>
        <a href="/real-article">Article</a>
        """
        links = extract_article_links(html, "http://example.com")
        # .pdf is allowed (text extracted by pdf_extract.py), .jpg/.mp4 still skipped
        assert len(links) == 2
        urls_str = " ".join(links)
        assert "doc.pdf" in urls_str
        assert "real-article" in urls_str

    @patch("anveshak.scraper.fetch.settings")
    def test_caps_at_max_links(self, mock_settings):
        """More links than scraper_max_links_per_page → only first N returned.

        Bug caught: if the cap is not applied, downstream crawling
        could overwhelm a target site with hundreds of requests.
        """
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 5

        html = "".join(
            f'<a href="/article{i}">Art {i}</a>' for i in range(25)
        )
        links = extract_article_links(html, "http://example.com")
        assert len(links) == 5

    @patch("anveshak.scraper.fetch.settings")
    def test_skips_javascript_hrefs(self, mock_settings):
        """javascript: hrefs must not appear in output."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = '<a href="javascript:void(0)">Click</a><a href="/real">Real</a>'
        links = extract_article_links(html, "http://example.com")
        assert len(links) == 1
        assert "real" in links[0]

    @patch("anveshak.scraper.fetch.settings")
    def test_skips_fragment_only_hrefs(self, mock_settings):
        """Anchor-only (#section) hrefs must not produce links."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = '<a href="#top">Top</a><a href="/real">Real</a>'
        links = extract_article_links(html, "http://example.com")
        assert len(links) == 1

    @patch("anveshak.scraper.fetch.settings")
    def test_deduplicates_links(self, mock_settings):
        """Same URL appearing twice in HTML should only appear once in output."""
        from anveshak.scraper.fetch import extract_article_links

        mock_settings.scraper_follow_same_domain = True
        mock_settings.scraper_max_links_per_page = 20

        html = '<a href="/art">A</a><a href="/art">B</a>'
        links = extract_article_links(html, "http://example.com")
        assert len(links) == 1
